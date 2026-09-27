-- SIH26174 Space Monitoring Database Schema
-- PostgreSQL 15+

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    role VARCHAR(50) DEFAULT 'researcher',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS experiments (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    category VARCHAR(100) DEFAULT 'General',
    environment VARCHAR(100) DEFAULT 'Microgravity',
    estimated_duration VARCHAR(20) DEFAULT '00:00:00',
    total_steps INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS experiment_steps (
    id SERIAL PRIMARY KEY,
    experiment_id INTEGER NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    step_number INTEGER NOT NULL,
    title VARCHAR(255),
    expected_activity VARCHAR(100) NOT NULL,
    description TEXT,
    safety_critical BOOLEAN DEFAULT FALSE,
    UNIQUE(experiment_id, step_number)
);

CREATE TABLE IF NOT EXISTS experiment_sessions (
    id SERIAL PRIMARY KEY,
    experiment_id INTEGER NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    astronaut_id INTEGER REFERENCES users(id),
    status VARCHAR(50) DEFAULT 'IN_PROGRESS',
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS activities (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES experiment_sessions(id) ON DELETE CASCADE,
    detected_activity VARCHAR(100) NOT NULL,
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES experiment_sessions(id) ON DELETE SET NULL,
    astronaut_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    severity VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    acknowledged BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS experiment_logs (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES experiment_sessions(id) ON DELETE CASCADE,
    step_number INTEGER,
    activity_id INTEGER REFERENCES activities(id) ON DELETE SET NULL,
    validation_status VARCHAR(50) NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_metadata (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(255) UNIQUE NOT NULL,
    version VARCHAR(50),
    is_active BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sessions_status ON experiment_sessions(status);
CREATE INDEX IF NOT EXISTS idx_activities_session ON activities(session_id);
CREATE INDEX IF NOT EXISTS idx_activities_timestamp ON activities(timestamp);
CREATE INDEX IF NOT EXISTS idx_alerts_session ON alerts(session_id);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_acknowledged ON alerts(acknowledged);
CREATE INDEX IF NOT EXISTS idx_experiment_logs_session ON experiment_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_experiment_logs_step ON experiment_logs(step_number);
CREATE INDEX IF NOT EXISTS idx_experiment_steps_experiment ON experiment_steps(experiment_id);
