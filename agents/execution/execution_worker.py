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
DB_URL = os.getenv("DB_URL", "postgresql://khaval_admin:khaval_password@localhost:5432/khaval_trade")
TRADING_MODE = os.getenv("TRADING_MODE", "PAPER") # PAPER or REAL

broker = RedisBroker(REDIS_URL)
app = FastStream(broker)
engine = create_engine(DB_URL)

class ExecutionWorker:
    def __init__(self):
        self.mode = TRADING_MODE
        logger.info(f"Execution Worker initialized in {self.mode} mode")
        if self.mode not in ["PAPER", "REAL"]:
            raise ValueError("TRADING_MODE must be PAPER or REAL")

    async def execute_real_trade(self, signal):
        """
        FAIL-SAFE: Hard block for real trading in paper mode.
        """
        if self.mode == "PAPER":
            raise PermissionError("CRITICAL: Attempted REAL trade execution while in PAPER mode!")

        logger.warning(f"EXECUTING REAL TRADE on Deriv: {signal['symbol']} {signal['action']}")
        # TODO: Implement Deriv PAT API call here
        # payload = {
        #     "buy": 1,
        #     "price": 10,
        #     "parameters": {
        #         "amount": 10,
        #         "basis": "stake",
        #         "contract_type": "CALL" if signal['action'] == "CALL" else "PUT",
        #         "currency": "USD",
        #         "duration": 5,
        #         "duration_unit": "m",
        #         "symbol": signal['symbol']
        #     }
        # }

    async def execute_paper_trade(self, signal):
        """
        Paper Trading Logic: Save to DB.
        """
        symbol = signal['symbol']
        action = signal['action']
        price = signal.get('price', 0.0) # Should be passed from consensus

        logger.info(f"Opening PAPER TRADE: {symbol} {action}")

        expiry = datetime.now() + timedelta(minutes=5)

        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO paper_trades (symbol, direction, amount, entry_price, status, expiry_time)
                VALUES (:symbol, :direction, :amount, :price, 'OPEN', :expiry)
            """), {
                "symbol": symbol,
                "direction": action,
                "amount": 10.0, # Default stake
                "price": price,
                "expiry": expiry
            })
            conn.commit()

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
        Background task to close expired paper trades.
        """
        with engine.connect() as conn:
            # Get open trades that have expired
            result = conn.execute(text("""
                SELECT trade_id, symbol, direction, entry_price
                FROM paper_trades
                WHERE status = 'OPEN' AND expiry_time <= NOW()
            """))

            for row in result:
                trade_id, symbol, direction, entry_price = row
                exit_price = current_prices.get(symbol, entry_price)

                # Simple Binary Option Logic:
                # CALL wins if exit > entry. PUT wins if exit < entry.
                profit = -10.0 # Loss (Stake)
                if direction == "CALL" and exit_price > entry_price:
                    profit = 9.5 # Profit (approx 95% payout)
                elif direction == "PUT" and exit_price < entry_price:
                    profit = 9.5

                conn.execute(text("""
                    UPDATE paper_trades
                    SET status = 'CLOSED', exit_price = :exit_price, profit = :profit
                    WHERE trade_id = :trade_id
                """), {"exit_price": exit_price, "profit": profit, "trade_id": trade_id})

                # Update Wallet
                conn.execute(text("UPDATE virtual_wallet SET balance = balance + :profit"), {"profit": profit})

            conn.commit()

worker = ExecutionWorker()
current_prices = {}

@broker.subscriber("execution:signal:stream")
async def on_execution_signal(msg):
    # Ensure current price is available for paper entry
    msg['price'] = current_prices.get(msg['symbol'], 0.0)
    await worker.handle_signal(msg)

@broker.subscriber("market:data:stream")
async def on_market_data(data):
    payload = json.loads(data.get("payload", "{}"))
    symbol = payload.get("symbol")
    price = payload.get("price")
    if symbol and price:
        current_prices[symbol] = price
        # Run paper trade monitor periodically (simplified trigger)
        await worker.monitor_paper_trades(current_prices)

if __name__ == "__main__":
    import asyncio
    asyncio.run(app.run())
