import asyncio
import json
from datetime import datetime, timedelta
from faststream import FastStream
from faststream.redis import RedisBroker
from agents.orchestrator.graph import orchestrator_graph
from loguru import logger

broker = RedisBroker("redis://khaval_redis:6379")
app = FastStream(broker)

# Buffering signals for the aggregation window
signal_buffer = {} # {symbol: [signals]}
buffer_locks = {}

async def process_consensus(symbol: str):
    """
    Triggers the LangGraph debate for a specific symbol after the aggregation window.
    """
    await asyncio.sleep(1.0) # 1s Aggregation Window

    async with buffer_locks.get(symbol, asyncio.Lock()):
        signals = signal_buffer.pop(symbol, [])
        if not signals:
            return

        logger.info(f"Starting consensus debate for {symbol} with {len(signals)} reports.")

        # Initialize LangGraph State
        initial_state = {
            "symbol": symbol,
            "signals": signals,
            "mode": "paper" # Defaulting to paper for now
        }

        # Run the Graph
        final_state = await orchestrator_graph.ainvoke(initial_state)

        # Post-process final action
        if final_state["final_action"] == "EXECUTE":
            logger.info(f"DECISION: {final_state['consensus_decision']} for {symbol}. Pushing to execution.")
            await broker.publish(
                {
                    "symbol": symbol,
                    "action": final_state["consensus_decision"],
                    "confidence": final_state["confidence_score"],
                    "reasoning": final_state["consensus_reasoning"],
                    "mode": final_state["mode"]
                },
                stream="trade:execution:stream"
            )
        else:
            logger.warning(f"ABORTED: {symbol} - {final_state.get('risk_reason', 'Unknown reason')}")

@broker.subscriber("agent:signals:stream")
async def handle_agent_signal(data):
    """
    Receives signals from individual agents and buffers them.
    """
    try:
        # FastStream provides the data directly if it's JSON
        signal = data
        symbol = signal.get("symbol")
        if not symbol: return

        if symbol not in buffer_locks:
            buffer_locks[symbol] = asyncio.Lock()

        async with buffer_locks[symbol]:
            if symbol not in signal_buffer:
                signal_buffer[symbol] = []
                # Start the aggregation timer for this symbol
                asyncio.create_task(process_consensus(symbol))

            signal_buffer[symbol].append(signal)
            logger.debug(f"Buffered {signal['agent']} signal for {symbol}")

    except Exception as e:
        logger.error(f"Orchestrator Error: {e}")

if __name__ == "__main__":
    asyncio.run(app.run())
