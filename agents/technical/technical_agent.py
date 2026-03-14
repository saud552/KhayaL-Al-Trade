import json
import pandas as pd
import pandas_ta as ta
from sqlalchemy import create_engine, text
from openai import AsyncOpenAI
from agents.common.base_agent import BaseAgent, AgentSettings
from loguru import logger
from datetime import datetime

class TechnicalAgent(BaseAgent):
    def __init__(self, settings: AgentSettings):
        super().__init__(settings)
        self.engine = create_engine(settings.db_url)
        self.llm_client = AsyncOpenAI(base_url=settings.ollama_url, api_key="ollama")

    def fetch_history(self, symbol: str, limit: int = 200):
        query = text("""
            SELECT time, open, high, low, close, volume
            FROM market_candles
            WHERE symbol = :symbol
            ORDER BY time DESC
            LIMIT :limit
        """)
        df = pd.read_sql(query, self.engine, params={"symbol": symbol, "limit": limit})
        return df.sort_values('time')

    def calculate_indicators(self, df):
        # RSI
        df.ta.rsi(length=14, append=True)
        # MACD
        df.ta.macd(append=True)
        # Bollinger Bands
        df.ta.bbands(length=20, std=2, append=True)
        # EMAs
        df.ta.ema(length=20, append=True)
        df.ta.ema(length=50, append=True)
        df.ta.ema(length=200, append=True)
        return df

    async def get_llm_reasoning(self, symbol, signal, indicators):
        prompt = f"""
        Role: Senior Quantitative Technical Analyst
        Asset: {symbol}
        Generated Signal: {signal}
        Current Technical Indicators: {json.dumps(indicators, indent=2)}

        Provide a concise (1-2 sentences) professional reasoning for this signal based on the technical data provided.
        """
        try:
            response = await self.llm_client.chat.completions.create(
                model="deepseek-r1:7b",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM Error: {e}")
            return "Reasoning unavailable due to LLM error."

    def determine_signal(self, row):
        rsi = row.get('RSI_14', 50)
        # Simplified crossover / threshold logic
        if rsi < 25: return "STRONG BUY"
        if rsi < 40: return "BUY"
        if rsi > 75: return "STRONG SELL"
        if rsi > 60: return "SELL"
        return "NEUTRAL"

    async def process_market_data(self, data: dict):
        try:
            payload = json.loads(data.get("payload", "{}"))
            symbol = payload.get("symbol")
            if not symbol: return

            # 1. Fetch 200 periods for warmup
            df = self.fetch_history(symbol, limit=200)
            if df.empty:
                logger.warning(f"No historical data found for {symbol}")
                return

            # 2. Calculate Indicators
            df = self.calculate_indicators(df)
            last_row = df.iloc[-1]

            # 3. Decision Logic
            signal = self.determine_signal(last_row)

            # 4. Indicators Summary for LLM/Signal Payload
            indicators_summary = {
                "price": payload.get("price"),
                "rsi": round(last_row.get('RSI_14', 50), 2),
                "ema_20": round(last_row.get('EMA_20', 0), 2),
                "ema_50": round(last_row.get('EMA_50', 0), 2),
                "ema_200": round(last_row.get('EMA_200', 0), 2),
                "bb_upper": round(last_row.get('BBU_20_2.0', 0), 2),
                "bb_lower": round(last_row.get('BBL_20_2.0', 0), 2)
            }

            # 5. AI Reasoning
            reasoning = "Neutral state, no reasoning required."
            if signal != "NEUTRAL":
                reasoning = await self.get_llm_reasoning(symbol, signal, indicators_summary)

            # 6. Publish to agent_signals_stream
            await self.publish_signal({
                "agent": "technical",
                "symbol": symbol,
                "signal": signal,
                "indicators": indicators_summary,
                "reasoning": reasoning,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.exception(f"Error processing market data: {e}")

    def run(self):
        @self.broker.subscriber("market:data:stream")
        async def handle_market_data(data):
            await self.process_market_data(data)

        import asyncio
        asyncio.run(self.start())

if __name__ == "__main__":
    settings = AgentSettings(agent_name="technical_analyst")
    agent = TechnicalAgent(settings)
    agent.run()
