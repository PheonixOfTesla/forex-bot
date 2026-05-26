-- Initialize database schema for Lightning Forex Bot
-- This script runs on first container start

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create trades table
CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    entry_price DECIMAL(20, 8) NOT NULL,
    exit_price DECIMAL(20, 8),
    quantity DECIMAL(20, 8) NOT NULL,
    stop_loss DECIMAL(20, 8),
    take_profit DECIMAL(20, 8),
    entry_time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    exit_time TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED', 'CANCELLED')),
    pnl DECIMAL(20, 8),
    pnl_pips DECIMAL(10, 2),
    confidence DECIMAL(5, 4),
    strategy VARCHAR(50),
    broker VARCHAR(20) NOT NULL CHECK (broker IN ('OANDA', 'BINANCE')),
    external_id VARCHAR(100),
    exit_reason VARCHAR(50),
    features JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_broker ON trades(broker);

-- Create signals table
CREATE TABLE IF NOT EXISTS signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    signal_type VARCHAR(10) NOT NULL CHECK (signal_type IN ('BUY', 'SELL', 'SKIP')),
    confidence DECIMAL(5, 4) NOT NULL,
    price DECIMAL(20, 8) NOT NULL,
    features JSONB,
    model_version VARCHAR(20),
    acted_upon BOOLEAN DEFAULT FALSE,
    trade_id UUID REFERENCES trades(id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol);
CREATE INDEX IF NOT EXISTS idx_signals_created_at ON signals(created_at);

-- Create performance metrics table
CREATE TABLE IF NOT EXISTS daily_performance (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    date DATE NOT NULL UNIQUE,
    starting_balance DECIMAL(20, 8) NOT NULL,
    ending_balance DECIMAL(20, 8) NOT NULL,
    daily_pnl DECIMAL(20, 8) NOT NULL,
    daily_pnl_pct DECIMAL(8, 4) NOT NULL,
    total_trades INT NOT NULL DEFAULT 0,
    winning_trades INT NOT NULL DEFAULT 0,
    losing_trades INT NOT NULL DEFAULT 0,
    win_rate DECIMAL(5, 4),
    max_drawdown DECIMAL(8, 4),
    sharpe_ratio DECIMAL(8, 4),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_daily_performance_date ON daily_performance(date);

-- Create price history table for analysis
CREATE TABLE IF NOT EXISTS price_history (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    open_time TIMESTAMP WITH TIME ZONE NOT NULL,
    open DECIMAL(20, 8) NOT NULL,
    high DECIMAL(20, 8) NOT NULL,
    low DECIMAL(20, 8) NOT NULL,
    close DECIMAL(20, 8) NOT NULL,
    volume DECIMAL(20, 8),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(symbol, timeframe, open_time)
);

CREATE INDEX IF NOT EXISTS idx_price_history_symbol_time ON price_history(symbol, timeframe, open_time);

-- Create model metrics table
CREATE TABLE IF NOT EXISTS model_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_name VARCHAR(50) NOT NULL,
    model_version VARCHAR(20) NOT NULL,
    accuracy DECIMAL(5, 4),
    precision_score DECIMAL(5, 4),
    recall DECIMAL(5, 4),
    f1_score DECIMAL(5, 4),
    training_samples INT,
    feature_importance JSONB,
    hyperparameters JSONB,
    trained_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_model_metrics_name ON model_metrics(model_name);

-- Create system logs table
CREATE TABLE IF NOT EXISTS system_logs (
    id BIGSERIAL PRIMARY KEY,
    level VARCHAR(10) NOT NULL,
    module VARCHAR(100),
    message TEXT NOT NULL,
    extra JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_system_logs_level ON system_logs(level);
CREATE INDEX IF NOT EXISTS idx_system_logs_created_at ON system_logs(created_at);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger for trades table
DROP TRIGGER IF EXISTS update_trades_updated_at ON trades;
CREATE TRIGGER update_trades_updated_at
    BEFORE UPDATE ON trades
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO lightning;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO lightning;

-- Insert initial system log
INSERT INTO system_logs (level, module, message)
VALUES ('INFO', 'init-db', 'Database initialized successfully');
