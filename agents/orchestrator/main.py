import asyncio
import json
from faststream import FastStream
from faststream.redis import RedisBroker
from agents.orchestrator.graph import orchestrator_graph
from loguru import logger

broker = RedisBroker("redis://khaval_redis:6379")
app = FastStream(broker)

# Buffering for window-based aggregation
# {symbol: {"price": float, "outputs": []}}
signal_buffer = {}
buffer_locks = {}

async def execute_graph(symbol: str):
    """
    Invokes the LangGraph debate and publishes to execution_signal_stream.
    """
    await asyncio.sleep(1.0) # 1s window

    async with buffer_locks.get(symbol, asyncio.Lock()):
        data = signal_buffer.pop(symbol, None)
        if not data or not data["outputs"]:
            return

        logger.info(f"Triggering debate for {symbol}...")

        # Initial State
        state = {
            "symbol": symbol,
            "current_price": data["price"],
            "agent_outputs": data["outputs"],
            "mode": "paper" # Defaulting to paper
        }

        # Execute Graph
        result = await orchestrator_graph.ainvoke(state)

        # Publish to execution_signal_stream
        output_payload = {
            "symbol": symbol,
            "decision": result["consensus_signal"],
            "reasoning": result["final_reasoning"],
            "confidence": result["confidence_score"],
            "risk_veto": result["risk_veto"],
            "risk_reason": result["risk_reason"],
            "mode": result["mode"]
        }

        await broker.publish(
            output_payload,
            stream="execution:signal:stream"
        )
        logger.info(f"Consensus reached for {symbol}: {result['consensus_signal']}")

@broker.subscriber("agent:signals:stream")
async def on_agent_signal(msg):
    """
    Collects signals into the buffer.
    """
    symbol = msg.get("symbol")
    if not symbol: return

    # In a real flow, we'd get the latest price from the state or Redis
    price = msg.get("indicators", {}).get("price", 0.0)

    if symbol not in buffer_locks:
        buffer_locks[symbol] = asyncio.Lock()

    async with buffer_locks[symbol]:
        if symbol not in signal_buffer:
            signal_buffer[symbol] = {"price": price, "outputs": []}
            asyncio.create_task(execute_graph(symbol))

        signal_buffer[symbol]["outputs"].append({
            "agent": msg.get("agent"),
            "symbol": symbol,
            "signal": msg.get("signal"),
            "confidence": msg.get("confidence", 0.0),
            "reasoning": msg.get("reasoning", ""),
            "timestamp": msg.get("timestamp")
        })

if __name__ == "__main__":
    asyncio.run(app.run())
