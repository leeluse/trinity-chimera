-- Supabase Schema for Autonomous Evolution System
-- This schema defines the lineage and tracking for agent strategy evolution.

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Strategies Table
-- Must be created before agents for current_strategy_id FK, or using ALTER TABLE
CREATE TABLE strategies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL,
    version INTEGER NOT NULL,
    code TEXT NOT NULL,
    params JSONB DEFAULT '{}'::jsonb,
    rationale TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Ensure versioning is tracked per agent
    UNIQUE (agent_id, version)
);

-- 2. Agents Table
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    persona TEXT,
    current_strategy_id UUID REFERENCES strategies(id) ON DELETE SET NULL,
    status TEXT DEFAULT 'idle',
    last_evolution_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add foreign key constraint to strategies now that agents table exists
ALTER TABLE strategies
ADD CONSTRAINT fk_strategies_agent
FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE;

-- 3. Backtest Results Table
CREATE TABLE backtest_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    strategy_id UUID NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    trinity_score DECIMAL(10, 4),
    return_val DECIMAL(18, 8),
    sharpe DECIMAL(10, 4),
    mdd DECIMAL(10, 4),
    win_rate DECIMAL(10, 4),
    test_period JSONB, -- Store start/end dates or tick range
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Improvement Logs Table
CREATE TABLE improvement_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    prev_strategy_id UUID REFERENCES strategies(id) ON DELETE SET NULL,
    new_strategy_id UUID REFERENCES strategies(id) ON DELETE SET NULL,
    llm_analysis TEXT,
    expected_improvement JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_strategies_agent_id ON strategies(agent_id);
CREATE INDEX idx_backtest_strategy_id ON backtest_results(strategy_id);
CREATE INDEX idx_improvement_agent_id ON improvement_logs(agent_id);
