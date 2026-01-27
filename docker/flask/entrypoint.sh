#!/bin/bash

set -e

echo "Waiting for PostgreSQL..."
while ! pg_isready -h postgres -p 5432 -U ${POSTGRES_USER:-postgres}; do
  sleep 1
done
echo "PostgreSQL is ready!"

echo "Waiting for Neo4j..."
# Wait for Neo4j port to be available
while ! nc -z neo4j 7687 2>/dev/null; do
  sleep 2
done
echo "Neo4j is ready!"

# Ensure data directories exist (they should already exist from Dockerfile)
echo "Checking data directories..."
mkdir -p /app/data/uploads /app/data/evidence /app/data/exports /app/data/reports 2>/dev/null || true
echo "Data directories ready!"

# Run database migrations
echo "Running database migrations..."
flask db upgrade || echo "No migrations to run"

# Initialize Neo4j constraints and indexes
echo "Initializing Neo4j indexes..."
flask init_neo4j || echo "Neo4j initialization skipped"

# Execute the main command
exec "$@"
