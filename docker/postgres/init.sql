-- PostgreSQL initialization script for Case Manager

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Set timezone
SET timezone = 'UTC';

-- This file will be executed on first container startup
-- Actual schema will be created via Flask-Migrate (Alembic)
