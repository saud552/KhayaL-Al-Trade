import asyncio
import json
from faststream.redis import RedisBroker

async def main():
    broker = RedisBroker("redis://khaval_redis:6379")
    await broker.connect()

    # Mock Market Data to set current price
    await broker.publish(
        {"payload": json.dumps({"symbol": "R_100", "price": 1250.0})},
        stream="market:data:stream"
    )

    # Mock Execution Signal
    signal = {
        "symbol": "R_100",
        "decision": "CALL",
        "confidence": 0.88,
        "reasoning": "Strong bullish trend identified by Technical Agent.",
        "mode": "paper"
    }

    print(f"Sending mock signal for {signal['symbol']}...")
    await broker.publish(signal, stream="execution:signal:stream")
    print("Signal sent. Check the database for trade entry.")

    await broker.close()

if __name__ == "__main__":
    asyncio.run(main())
