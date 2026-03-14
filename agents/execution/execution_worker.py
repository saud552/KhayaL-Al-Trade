import os
import json
import asyncio
from datetime import datetime, timedelta
from faststream import FastStream
from faststream.redis import RedisBroker
from sqlalchemy import create_engine, text
from loguru import logger

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://khaval_redis:6379")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://khaval_admin:khaval_password@localhost:5432/khaval_trade")
TRADING_MODE = os.getenv("TRADING_MODE", "PAPER") # PAPER or REAL
DERIV_API_TOKEN = os.getenv("DERIV_API_TOKEN", "")

broker = RedisBroker(REDIS_URL)
app = FastStream(broker)
engine = create_engine(DATABASE_URL)

class ExecutionWorker:
    def __init__(self):
        self.mode = TRADING_MODE
        logger.info(f"Execution Worker initialized in {self.mode} mode")
        if self.mode not in ["PAPER", "REAL"]:
            raise ValueError("TRADING_MODE must be PAPER or REAL")

    def log_lifecycle(self, trade_id, symbol, event, details=None):
        """Helper to log trade lifecycle events to DB."""
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO trade_lifecycle_logs (trade_id, symbol, event, details)
                VALUES (:trade_id, :symbol, :event, :details)
            """), {
                "trade_id": trade_id,
                "symbol": symbol,
                "event": event,
                "details": json.dumps(details) if details else None
            })
            conn.commit()

    async def execute_real_trade(self, signal):
        """
        Deriv Execution Client (Real Mode)
        """
        # THE GUARDRAIL: Kill switch for real trading in paper mode
        if self.mode == "PAPER":
            logger.critical("GUARDRAIL TRIGGERED: Attempted real execution in PAPER mode!")
            raise PermissionError("Safety Violation: Real trade blocked in PAPER mode.")

        if not DERIV_API_TOKEN:
            logger.error("DERIV_API_TOKEN missing for real execution")
            return

        logger.warning(f"PLACING REAL ORDER: {signal['symbol']} {signal['action']}")
        self.log_lifecycle(None, signal['symbol'], "ORDER_PLACED", {"mode": "real", "signal": signal})

        # Real Deriv API logic would go here (PAT Authentication)
        # For now, we log the intent as per the roadmap

    async def execute_paper_trade(self, signal):
        """
        Paper Trading Engine
        """
        symbol = signal['symbol']
        action = signal['action']
        price = signal.get('price', 0.0)

        logger.info(f"SIGNAL RECEIVED: Opening Paper Trade for {symbol}")

        expiry = datetime.now() + timedelta(minutes=5)
        commission = 0.50 # Mock fixed commission

        with engine.connect() as conn:
            # 1. Open Trade
            result = conn.execute(text("""
                INSERT INTO paper_trades (symbol, direction, amount, entry_price, status, expiry_time, commission)
                VALUES (:symbol, :direction, :amount, :price, 'OPEN', :expiry, :commission)
                RETURNING trade_id
            """), {
                "symbol": symbol,
                "direction": action,
                "amount": 10.0,
                "price": price,
                "expiry": expiry,
                "commission": commission
            })
            trade_id = result.fetchone()[0]
            conn.commit()

            self.log_lifecycle(trade_id, symbol, "ORDER_FILLED", {"price": price, "commission": commission})
            return trade_id

    async def handle_signal(self, signal):
        if signal.get("decision") == "WAIT":
            return

        try:
            if self.mode == "REAL":
                await self.execute_real_trade(signal)
            else:
                await self.execute_paper_trade(signal)
        except Exception as e:
            logger.error(f"Execution Error: {e}")

    async def monitor_paper_trades(self, current_prices):
        """
        Closes expired trades and logs the final state.
        """
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT trade_id, symbol, direction, entry_price, commission
                FROM paper_trades
                WHERE status = 'OPEN' AND expiry_time <= NOW()
            """))

            for row in result:
                trade_id, symbol, direction, entry_price, commission = row
                exit_price = current_prices.get(symbol, entry_price)

                # PnL Logic
                profit = -10.0 - commission # Initial loss including fee
                if direction == "CALL" and exit_price > entry_price:
                    profit = 9.5 - commission
                elif direction == "PUT" and exit_price < entry_price:
                    profit = 9.5 - commission

                conn.execute(text("""
                    UPDATE paper_trades
                    SET status = 'CLOSED', exit_price = :exit_price, profit = :profit
                    WHERE trade_id = :trade_id
                """), {"exit_price": exit_price, "profit": profit, "trade_id": trade_id})

                conn.execute(text("UPDATE virtual_wallet SET balance = balance + :profit"), {"profit": profit})

                self.log_lifecycle(trade_id, symbol, "TRADE_CLOSED", {"exit_price": exit_price, "profit": profit})

            conn.commit()

worker = ExecutionWorker()
current_prices = {}

@broker.subscriber("execution:signal:stream")
async def on_execution_signal(msg):
    msg['price'] = current_prices.get(msg['symbol'], 0.0)
    await worker.handle_signal(msg)

@broker.subscriber("market:data:stream")
async def on_market_data(data):
    payload = json.loads(data.get("payload", "{}"))
    symbol = payload.get("symbol")
    price = payload.get("price")
    if symbol and price:
        current_prices[symbol] = price
        await worker.monitor_paper_trades(current_prices)

if __name__ == "__main__":
    import asyncio
    asyncio.run(app.run())
