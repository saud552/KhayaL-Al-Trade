import json
import pandas as pd
import pandas_ta as ta
from sqlalchemy import create_all, create_engine, text
from openai import AsyncOpenAI
from agents.common.base_agent import BaseAgent, AgentSettings
from loguru import logger
from datetime import datetime

class TechnicalAgent(BaseAgent):
    def __init__(self, settings: AgentSettings):
        super().__init__(settings)
        self.engine = create_engine(settings.db_url)
        self.llm_client = AsyncOpenAI(base_url=settings.ollama_url, api_key="ollama")

    def fetch_history(self, symbol: str, limit: int = 100):
        query = text(f"""
            SELECT time, open, high, low, close, volume
            FROM market_candles
            WHERE symbol = :symbol
            ORDER BY time DESC
            LIMIT :limit
        """)
        df = pd.read_sql(query, self.engine, params={"symbol": symbol, "limit": limit})
        return df.sort_values('time')

    def calculate_indicators(self, df):
        df.ta.rsi(append=True)
        df.ta.macd(append=True)
        df.ta.ema(length=20, append=True)
        df.ta.ema(length=50, append=True)
        return df

    async def get_llm_reasoning(self, symbol, signal, indicators):
        prompt = f"""
        Asset: {symbol}
        Technical Signal: {signal}
        Current Indicators: {indicators}

        As a Senior Technical Analyst, provide a one-sentence professional reasoning for this signal.
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

    async def process_market_data(self, data: dict):
        payload = json.loads(data.get("payload", "{}"))
        symbol = payload.get("symbol")
        if not symbol: return

        # 1. Fetch History for Warmup
        df = self.fetch_history(symbol)

        # 2. Add current tick to DF (simplified for now, ideally resampled)
        # In production, we'd use the Continuous Aggregates from TimescaleDB

        # 3. Calculate Indicators
        df = self.calculate_indicators(df)
        last_row = df.iloc[-1]

        # 4. Signal Logic (Simplified)
        rsi = last_row.get('RSI_14', 50)
        signal = "NEUTRAL"
        if rsi < 30: signal = "STRONG BUY"
        elif rsi < 45: signal = "BUY"
        elif rsi > 70: signal = "STRONG SELL"
        elif rsi > 55: signal = "SELL"

        # 5. Get AI Reasoning
        indicators_summary = {
            "RSI": round(rsi, 2),
            "EMA_20": round(last_row.get('EMA_20', 0), 2),
            "Close": payload.get("price")
        }
        reasoning = await self.get_llm_reasoning(symbol, signal, indicators_summary)

        # 6. Publish Signal
        await self.publish_signal({
            "agent": "technical",
            "symbol": symbol,
            "signal": signal,
            "confidence": 0.7, # Static for now
            "reasoning": reasoning,
            "timestamp": datetime.now().isoformat()
        })

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
