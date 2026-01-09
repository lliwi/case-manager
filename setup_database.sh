#!/bin/bash
##
# Database Setup Script for Case Manager
#
# This script initializes the database for a new Case Manager installation.
# It creates all tables using Flask-Migrate migrations.
#
# Usage:
#   ./setup_database.sh
#
# Prerequisites:
#   - Docker containers must be running (docker-compose up -d)
#   - PostgreSQL container must be healthy
##

set -e

echo "🔍 Checking if Docker containers are running..."
if ! docker ps | grep -q casemanager_web; then
    echo "❌ Error: casemanager_web container is not running"
    echo "   Please start containers with: cd docker && docker-compose up -d"
    exit 1
fi

if ! docker ps | grep -q casemanager_postgres; then
    echo "❌ Error: casemanager_postgres container is not running"
    echo "   Please start containers with: cd docker && docker-compose up -d"
    exit 1
fi

echo "✅ Docker containers are running"
echo ""

echo "🔍 Checking PostgreSQL health..."
for i in {1..30}; do
    if docker exec casemanager_postgres pg_isready -U postgres -d case_manager >/dev/null 2>&1; then
        echo "✅ PostgreSQL is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Error: PostgreSQL did not become ready in time"
        exit 1
    fi
    echo "   Waiting for PostgreSQL... ($i/30)"
    sleep 1
done

echo ""
echo "🗄️  Applying database migrations..."
docker exec casemanager_web flask db upgrade

if [ $? -eq 0 ]; then
    echo "✅ Database migrations applied successfully"
    echo ""
    echo "📋 Database tables created:"
    echo "   - users, roles, audit_logs"
    echo "   - cases, evidences, chain_of_custody"
    echo "   - evidence_analyses (forensic plugin results)"
    echo "   - graph nodes and relationships"
    echo "   - timeline events, reports"
    echo "   - custom legitimacy and relationship types"
    echo ""
    echo "✅ Database setup complete!"
    echo ""
    echo "Next steps:"
    echo "1. Create a test user: docker exec casemanager_web python create_test_user.py"
    echo "2. Access the application at http://localhost"
else
    echo "❌ Error: Failed to apply database migrations"
    exit 1
fi
