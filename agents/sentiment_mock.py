import asyncio
import json
from faststream import FastStream
from faststream.redis import RedisBroker
from datetime import datetime

broker = RedisBroker("redis://khaval_redis:6379")
app = FastStream(broker)

@broker.subscriber("market:data:stream")
async def handle_market_data(data):
    payload = json.loads(data.get("payload", "{}"))
    symbol = payload.get("symbol")

    # Mock Sentiment Signal
    signal = {
        "agent": "sentiment",
        "symbol": symbol,
        "signal": "NEUTRAL",
        "confidence": 0.5,
        "reasoning": "Mixed social media sentiment for this asset.",
        "timestamp": datetime.now().isoformat()
    }

    await broker.publish(signal, stream="agent:signals:stream")

if __name__ == "__main__":
    asyncio.run(app.run())
