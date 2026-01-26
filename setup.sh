#!/bin/bash
##
# Complete Setup Script for Case Manager
#
# This script performs a complete clean installation:
#   1. Generates SSL certificates for PostgreSQL
#   2. Creates .env file from template if needed
#   3. Builds and starts all Docker containers
#   4. Initializes the database (tables from models)
#   5. Creates the initial admin user
#
# Usage:
#   ./setup.sh
#
# For production, edit .env file before running this script.
##

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo ""
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

print_header "Case Manager - Complete Setup"

echo "This script will perform a complete clean installation."
echo "Make sure you have Docker and Docker Compose installed."
echo ""

# Step 1: Check prerequisites
print_header "Step 1: Checking Prerequisites"

if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi
print_success "Docker is installed"

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi
print_success "Docker Compose is installed"

# Step 2: Setup environment file
print_header "Step 2: Environment Configuration"

if [ ! -f "docker/.env" ]; then
    if [ -f ".env.example" ]; then
        print_info "Creating docker/.env from .env.example..."
        cp .env.example docker/.env

        # Generate secure random values
        SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32)
        POSTGRES_PASSWORD=$(python3 -c "import secrets; print(secrets.token_hex(16))" 2>/dev/null || openssl rand -hex 16)
        NEO4J_PASSWORD=$(python3 -c "import secrets; print(secrets.token_hex(16))" 2>/dev/null || openssl rand -hex 16)
        REDIS_PASSWORD=$(python3 -c "import secrets; print(secrets.token_hex(16))" 2>/dev/null || openssl rand -hex 16)
        ENCRYPTION_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32)

        # Update .env file with generated values
        sed -i "s/SECRET_KEY=.*/SECRET_KEY=${SECRET_KEY}/" docker/.env
        sed -i "s/POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=${POSTGRES_PASSWORD}/" docker/.env
        sed -i "s/NEO4J_PASSWORD=.*/NEO4J_PASSWORD=${NEO4J_PASSWORD}/" docker/.env
        sed -i "s/REDIS_PASSWORD=.*/REDIS_PASSWORD=${REDIS_PASSWORD}/" docker/.env
        sed -i "s/EVIDENCE_ENCRYPTION_KEY=.*/EVIDENCE_ENCRYPTION_KEY=${ENCRYPTION_KEY}/" docker/.env

        # Update DATABASE_URL with new postgres password
        sed -i "s|DATABASE_URL=.*|DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD}@postgres:5432/case_manager|" docker/.env

        # Update REDIS_URL and CELERY URLs with new redis password
        sed -i "s|REDIS_URL=.*|REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0|" docker/.env
        sed -i "s|CELERY_BROKER_URL=.*|CELERY_BROKER_URL=redis://:${REDIS_PASSWORD}@redis:6379/0|" docker/.env
        sed -i "s|CELERY_RESULT_BACKEND=.*|CELERY_RESULT_BACKEND=redis://:${REDIS_PASSWORD}@redis:6379/1|" docker/.env

        print_success "Environment file created with secure random passwords"
        print_warning "Review docker/.env before production deployment"
    else
        print_error ".env.example not found. Cannot create environment file."
        exit 1
    fi
else
    print_success "Environment file already exists (docker/.env)"
fi

# Step 3: Generate SSL certificates for PostgreSQL
print_header "Step 3: SSL Certificates"

SSL_DIR="docker/postgres/ssl"
mkdir -p "$SSL_DIR"

if [ ! -f "$SSL_DIR/server.key" ] || [ ! -f "$SSL_DIR/server.crt" ]; then
    print_info "Generating SSL certificates for PostgreSQL..."

    # Generate CA key and certificate
    openssl genrsa -out "$SSL_DIR/ca.key" 4096 2>/dev/null
    openssl req -new -x509 -days 3650 -key "$SSL_DIR/ca.key" -out "$SSL_DIR/ca.crt" \
        -subj "/C=ES/ST=Spain/L=Madrid/O=CaseManager/CN=CaseManager-CA" 2>/dev/null

    # Generate server key and certificate
    openssl genrsa -out "$SSL_DIR/server.key" 4096 2>/dev/null
    openssl req -new -key "$SSL_DIR/server.key" -out "$SSL_DIR/server.csr" \
        -subj "/C=ES/ST=Spain/L=Madrid/O=CaseManager/CN=postgres" 2>/dev/null
    openssl x509 -req -days 3650 -in "$SSL_DIR/server.csr" -CA "$SSL_DIR/ca.crt" -CAkey "$SSL_DIR/ca.key" \
        -CAcreateserial -out "$SSL_DIR/server.crt" 2>/dev/null

    # Set proper permissions
    chmod 600 "$SSL_DIR/server.key"
    chmod 644 "$SSL_DIR/server.crt" "$SSL_DIR/ca.crt"

    # Clean up CSR
    rm -f "$SSL_DIR/server.csr"

    print_success "SSL certificates generated"
else
    print_success "SSL certificates already exist"
fi

# Step 4: Create required directories
print_header "Step 4: Directory Structure"

DIRS=(
    "data/evidence"
    "data/uploads"
    "data/exports"
    "data/reports"
    "data/backups"
    "data/monitoring"
    "logs"
)

for dir in "${DIRS[@]}"; do
    mkdir -p "$dir"
    touch "$dir/.gitkeep" 2>/dev/null || true
done

print_success "Directory structure created"

# Step 5: Build and start containers
print_header "Step 5: Building Docker Images"

cd docker
print_info "Building Docker images (this may take a few minutes)..."
docker-compose build --quiet

print_success "Docker images built"

print_header "Step 6: Starting Services"

print_info "Starting all containers..."
docker-compose up -d

print_success "Containers started"

# Wait for services to be healthy
print_info "Waiting for services to be ready..."

# Wait for PostgreSQL
for i in {1..60}; do
    if docker exec casemanager_postgres pg_isready -U postgres -d case_manager >/dev/null 2>&1; then
        print_success "PostgreSQL is ready"
        break
    fi
    if [ $i -eq 60 ]; then
        print_error "PostgreSQL did not become ready in time"
        docker-compose logs postgres
        exit 1
    fi
    sleep 2
done

# Wait for Neo4j
for i in {1..60}; do
    if docker exec casemanager_neo4j cypher-shell -u neo4j -p "$(grep NEO4J_PASSWORD ../.env 2>/dev/null | cut -d'=' -f2 || echo 'neo4j')" "RETURN 1" >/dev/null 2>&1; then
        print_success "Neo4j is ready"
        break
    fi
    if [ $i -eq 60 ]; then
        print_warning "Neo4j health check timed out (may still be starting)"
        break
    fi
    sleep 2
done

# Wait for Redis
for i in {1..30}; do
    if docker exec casemanager_redis redis-cli ping >/dev/null 2>&1; then
        print_success "Redis is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        print_error "Redis did not become ready in time"
        exit 1
    fi
    sleep 1
done

cd ..

# Step 7: Initialize database
print_header "Step 7: Database Initialization"

print_info "Creating database tables from models..."

# Run the init_database.py script
docker exec casemanager_web python init_database.py

if [ $? -eq 0 ]; then
    print_success "Database initialized"
else
    print_error "Database initialization failed"
    exit 1
fi

# Step 8: Create initial admin user
print_header "Step 8: Creating Admin User"

docker exec casemanager_web python create_test_user.py

if [ $? -eq 0 ]; then
    print_success "Admin user created"
else
    print_warning "Admin user creation may have failed or user already exists"
fi

# Final summary
print_header "Setup Complete!"

echo -e "${GREEN}Case Manager has been installed successfully!${NC}"
echo ""
echo "Services running:"
echo "  - Web Application: http://localhost"
echo "  - Neo4j Browser:   http://localhost:7474"
echo "  - Flower Monitor:  http://localhost:5555"
echo ""
echo "Default credentials:"
echo "  - Email:    admin@casemanager.com"
echo "  - Password: admin123"
echo ""
echo -e "${YELLOW}IMPORTANT: Change the default password after first login!${NC}"
echo ""
echo "Useful commands:"
echo "  - View logs:        cd docker && docker-compose logs -f"
echo "  - Stop services:    cd docker && docker-compose down"
echo "  - Start services:   cd docker && docker-compose up -d"
echo "  - Create backup:    ./backup/backup.sh"
echo ""
