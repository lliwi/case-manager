#!/bin/bash
##
# Database Setup Script for Case Manager
#
# Initializes database for a new installation or applies pending migrations.
# For fresh installs, creates tables directly from models (no migration needed).
# For existing installs, applies any pending migrations.
#
# Usage:
#   ./setup_database.sh
#
# Prerequisites:
#   - Docker containers must be running (docker-compose up -d)
##

set -e

echo "=========================================="
echo "  Case Manager - Database Setup"
echo "=========================================="
echo ""

# Check containers
if ! docker ps | grep -q casemanager_web; then
    echo "Error: casemanager_web container is not running"
    echo "Start containers: cd docker && docker-compose up -d"
    exit 1
fi

if ! docker ps | grep -q casemanager_postgres; then
    echo "Error: casemanager_postgres container is not running"
    exit 1
fi

echo "Containers are running"

# Wait for PostgreSQL
echo "Waiting for PostgreSQL..."
for i in {1..30}; do
    if docker exec casemanager_postgres pg_isready -U postgres -d case_manager >/dev/null 2>&1; then
        echo "PostgreSQL is ready"
        break
    fi
    [ $i -eq 30 ] && { echo "PostgreSQL timeout"; exit 1; }
    sleep 1
done

echo ""

# Check database state
TABLE_COUNT=$(docker exec casemanager_postgres psql -U postgres -d case_manager -t -c \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ')

if [ "$TABLE_COUNT" = "0" ] || [ -z "$TABLE_COUNT" ]; then
    echo "Fresh database - initializing from models..."
    docker exec casemanager_web python init_database.py
else
    echo "Existing database ($TABLE_COUNT tables) - checking for updates..."
    docker exec casemanager_web flask db upgrade
fi

echo ""
echo "Database setup complete!"
echo ""
echo "Next: docker exec casemanager_web python create_test_user.py"
