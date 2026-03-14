-- Extension setup
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- 1. Market Candles Table (OHLCV)
CREATE TABLE market_candles (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION,
    source VARCHAR(20)
);

SELECT create_hypertable('market_candles', 'time', chunk_time_interval => INTERVAL '1 day');
CREATE INDEX idx_symbol_time ON market_candles (symbol, time DESC);

-- 2. Agent Signals Table (Logs from the individual agents)
CREATE TABLE agent_signals (
    time TIMESTAMPTZ NOT NULL,
    signal_id UUID DEFAULT gen_random_uuid(),
    symbol VARCHAR(20) NOT NULL,
    agent_name VARCHAR(50),
    direction VARCHAR(10) NOT NULL,
    confidence DOUBLE PRECISION,
    reasoning TEXT,
    metadata JSONB
);

SELECT create_hypertable('agent_signals', 'time', chunk_time_interval => INTERVAL '7 days');

-- 3. Consensus Decisions Table (Output from Orchestrator)
CREATE TABLE consensus_decisions (
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol VARCHAR(20) NOT NULL,
    decision VARCHAR(10) NOT NULL, -- CALL, PUT, WAIT
    confidence DOUBLE PRECISION,
    reasoning TEXT,
    risk_veto BOOLEAN,
    risk_reason TEXT
);

SELECT create_hypertable('consensus_decisions', 'time', chunk_time_interval => INTERVAL '7 days');

-- 4. Trades Tables

-- Real Trades
CREATE TABLE real_trades (
    trade_id SERIAL PRIMARY KEY,
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    entry_price DOUBLE PRECISION,
    exit_price DOUBLE PRECISION,
    profit DOUBLE PRECISION,
    status VARCHAR(20), -- OPEN, CLOSED, FAILED
    deriv_contract_id VARCHAR(100)
);

-- Paper Trades
CREATE TABLE paper_trades (
    trade_id SERIAL PRIMARY KEY,
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    entry_price DOUBLE PRECISION,
    exit_price DOUBLE PRECISION,
    profit DOUBLE PRECISION,
    status VARCHAR(20), -- OPEN, CLOSED
    expiry_time TIMESTAMPTZ
);

-- Virtual Wallet
CREATE TABLE virtual_wallet (
    id SERIAL PRIMARY KEY,
    balance DOUBLE PRECISION DEFAULT 10000.0,
    currency VARCHAR(10) DEFAULT 'USD',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Continuous Aggregates
CREATE MATERIALIZED VIEW market_candles_1m
WITH (timescaledb.continuous = true) AS
SELECT
    time_bucket('1 minute', time) AS bucket,
    symbol,
    first(open, time) as open,
    max(high) as high,
    min(low) as low,
    last(close, time) as close,
    sum(volume) as volume
FROM market_candles
GROUP BY bucket, symbol;

CREATE MATERIALIZED VIEW market_candles_5m
WITH (timescaledb.continuous = true) AS
SELECT
    time_bucket('5 minutes', time) AS bucket,
    symbol,
    first(open, time) as open,
    max(high) as high,
    min(low) as low,
    last(close, time) as close,
    sum(volume) as volume
FROM market_candles
GROUP BY bucket, symbol;

-- Compression
ALTER TABLE market_candles SET (timescaledb.compress, timescaledb.compress_segmentby = 'symbol');
SELECT add_compression_policy('market_candles', INTERVAL '7 days');

-- 6. Trade Lifecycle Logs
CREATE TABLE trade_lifecycle_logs (
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    trade_id INTEGER, -- Link to real_trades or paper_trades
    symbol VARCHAR(20),
    event VARCHAR(50), -- SIGNAL_RECEIVED, ORDER_PLACED, ORDER_FILLED, TRADE_CLOSED
    details JSONB
);
SELECT create_hypertable('trade_lifecycle_logs', 'time');

-- 7. Commissions and Balances updates
ALTER TABLE paper_trades ADD COLUMN commission DOUBLE PRECISION DEFAULT 0.0;
ALTER TABLE real_trades ADD COLUMN commission DOUBLE PRECISION DEFAULT 0.0;
