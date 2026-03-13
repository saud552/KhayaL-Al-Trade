-- Extension setup (TimescaleDB usually comes with it enabled in the HA image, but good to be explicit)
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
    source VARCHAR(20) -- e.g., 'deriv', 'ccxt'
);

-- Convert to Hypertable
SELECT create_hypertable('market_candles', 'time', chunk_time_interval => INTERVAL '1 day');

-- Indexing for performance
CREATE INDEX idx_symbol_time ON market_candles (symbol, time DESC);

-- 2. Agent Signals Table
CREATE TABLE agent_signals (
    time TIMESTAMPTZ NOT NULL,
    signal_id UUID DEFAULT gen_random_uuid(),
    symbol VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL, -- CALL, PUT, WAIT
    confidence DOUBLE PRECISION,
    consensus_log TEXT,
    metadata JSONB -- Store agent-specific votes here
);

-- Convert to Hypertable
SELECT create_hypertable('agent_signals', 'time', chunk_time_interval => INTERVAL '7 days');

-- 3. Continuous Aggregates for Resampling

-- 1 Minute Candles
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

-- 5 Minute Candles
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

-- 1 Hour Candles
CREATE MATERIALIZED VIEW market_candles_1h
WITH (timescaledb.continuous = true) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    symbol,
    first(open, time) as open,
    max(high) as high,
    min(low) as low,
    last(close, time) as close,
    sum(volume) as volume
FROM market_candles
GROUP BY bucket, symbol;

-- Refresh Policies (Ensure data is up to date)
SELECT add_continuous_aggregate_policy('market_candles_1m',
    start_offset => INTERVAL '2 minutes',
    end_offset => INTERVAL '0 seconds',
    schedule_interval => INTERVAL '1 minute');

SELECT add_continuous_aggregate_policy('market_candles_5m',
    start_offset => INTERVAL '10 minutes',
    end_offset => INTERVAL '0 seconds',
    schedule_interval => INTERVAL '5 minutes');

SELECT add_continuous_aggregate_policy('market_candles_1h',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '0 seconds',
    schedule_interval => INTERVAL '1 hour');

-- 4. Trades Tables (Separation of State)

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
    status VARCHAR(20) -- OPEN, CLOSED
);

-- Optimization: Compression (Save disk space on old data)
ALTER TABLE market_candles SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol'
);

SELECT add_compression_policy('market_candles', INTERVAL '7 days');
