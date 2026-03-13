# KhavaL Al Trade - Infrastructure Documentation

## Redis Stream Topology

To ensure high performance and zero data loss, we use a structured Redis Stream topology.

### 1. Market Data Stream
**Key:** `market:data:stream`
- **Source:** Go Orchestrator (Deriv/CCXT Connectors)
- **Data Payload:** `{"symbol": "R_100", "price": 1234.56, "type": "tick", "timestamp": 1678901234}`
- **Consumer Groups:**
  - `timescale_ingestor_group`: Persists every tick to TimescaleDB.
  - `agent_analysis_group`: Consumed by AI agents for real-time triggers.

### 2. Agent Signal Stream
**Key:** `agent:signals:stream`
- **Source:** Individual AI Agents (Technical, News, etc.)
- **Data Payload:** `{"agent": "technical", "symbol": "R_100", "signal": "BUY", "confidence": 0.85}`
- **Consumer Groups:**
  - `langgraph_consensus_group`: Consumed by the LangGraph orchestrator to start a debate.

### 3. Execution Stream
**Key:** `trade:execution:stream`
- **Source:** LangGraph Orchestrator (Final Decision)
- **Data Payload:** `{"symbol": "R_100", "action": "CALL", "mode": "paper", "amount": 10}`
- **Consumer Groups:**
  - `execution_engine_group`: Responsible for calling Deriv API or updating Paper Wallet.

---

## TimescaleDB Strategy

- **Hypertables:** Used for `market_candles` and `agent_signals` to ensure performance remains constant as data grows.
- **Continuous Aggregates:** Automates the resampling of tick data into 1m, 5m, and 1h candles, reducing the load on the Go/Python services.
- **Compression:** Data older than 7 days is automatically compressed, saving up to 90% disk space.

## LLM Inference (Ollama)

- **Default Port:** 11434
- **Usage:** Python agents will call the Ollama API (`http://khaval_ollama:11434`) to process sentiment and reach consensus.
