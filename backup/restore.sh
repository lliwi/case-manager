#!/bin/bash
#
# Case Manager - Docker Volume Restore Script
#
# Restores a complete backup including:
# - PostgreSQL database
# - Neo4j database
# - Evidence files
# - Uploads, exports, reports
#
# WARNING: This will stop the application during restore!
#
# Usage: ./restore.sh <backup_file.tar.gz> [--no-confirm]
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DOCKER_DIR="$PROJECT_DIR/docker"
BACKUP_DIR="$PROJECT_DIR/data/backups"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

# Check arguments
BACKUP_FILE="$1"
NO_CONFIRM="$2"

if [ -z "$BACKUP_FILE" ]; then
    log_error "Usage: $0 <backup_file.tar.gz> [--no-confirm]"
    log_info "Available backups:"
    ls -lh "$BACKUP_DIR"/*.tar.gz 2>/dev/null || echo "  No backups found in $BACKUP_DIR"
    exit 1
fi

# Resolve backup file path
if [ ! -f "$BACKUP_FILE" ]; then
    # Try in backup directory
    if [ -f "$BACKUP_DIR/$BACKUP_FILE" ]; then
        BACKUP_FILE="$BACKUP_DIR/$BACKUP_FILE"
    else
        log_error "Backup file not found: $BACKUP_FILE"
        exit 1
    fi
fi

# Verify checksum if available
BACKUP_BASENAME=$(basename "$BACKUP_FILE" .tar.gz)
CHECKSUM_FILE="$BACKUP_DIR/${BACKUP_BASENAME}.sha256"
if [ -f "$CHECKSUM_FILE" ]; then
    log_info "Verifying backup checksum..."
    cd "$(dirname "$BACKUP_FILE")"
    if sha256sum -c "$CHECKSUM_FILE" >/dev/null 2>&1; then
        log_info "Checksum verified OK"
    else
        log_error "Checksum verification FAILED!"
        if [ "$NO_CONFIRM" != "--no-confirm" ]; then
            read -p "Continue anyway? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 1
            fi
        fi
    fi
fi

# Confirmation
if [ "$NO_CONFIRM" != "--no-confirm" ]; then
    echo ""
    echo -e "${YELLOW}WARNING: This will restore the backup and OVERWRITE current data!${NC}"
    echo -e "${YELLOW}The application will be stopped during the restore process.${NC}"
    echo ""
    echo "Backup file: $BACKUP_FILE"
    echo ""
    read -p "Are you sure you want to continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Restore cancelled"
        exit 0
    fi
fi

# Create temporary directory for extraction
TEMP_DIR=$(mktemp -d)
log_info "Extracting backup to: $TEMP_DIR"

# Extract backup
tar -xzf "$BACKUP_FILE" -C "$TEMP_DIR"

# Find the backup directory
BACKUP_CONTENT_DIR=$(find "$TEMP_DIR" -maxdepth 1 -type d -name "backup_*" | head -1)
if [ -z "$BACKUP_CONTENT_DIR" ]; then
    log_error "Invalid backup structure"
    rm -rf "$TEMP_DIR"
    exit 1
fi

log_info "Backup content directory: $BACKUP_CONTENT_DIR"

# Read manifest
if [ -f "$BACKUP_CONTENT_DIR/manifest.json" ]; then
    log_info "Reading manifest..."
    cat "$BACKUP_CONTENT_DIR/manifest.json"
    echo ""
fi

# Change to docker directory
cd "$DOCKER_DIR"

# Load environment variables
if [ -f "$PROJECT_DIR/.env" ]; then
    export $(grep -v '^#' "$PROJECT_DIR/.env" | xargs)
fi

# Get compose project name
COMPOSE_PROJECT=$(docker compose config --format json 2>/dev/null | grep -o '"name":"[^"]*"' | head -1 | cut -d'"' -f4)
COMPOSE_PROJECT=${COMPOSE_PROJECT:-docker}

log_step "Stopping application containers..."
docker compose stop web celery_worker celery_beat flower nginx 2>/dev/null || true

# Wait for containers to stop
sleep 3

# 1. Restore PostgreSQL
if [ -f "$BACKUP_CONTENT_DIR/database.dump" ]; then
    log_step "Restoring PostgreSQL database..."

    # Make sure postgres is running
    docker compose up -d postgres
    sleep 5

    # Wait for postgres to be ready
    for i in {1..30}; do
        if docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-postgres}" >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done

    # Terminate existing connections
    docker compose exec -T postgres psql -U "${POSTGRES_USER:-postgres}" -d postgres -c \
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${POSTGRES_DB:-case_manager}' AND pid <> pg_backend_pid();" \
        2>/dev/null || true

    # Drop and recreate database
    docker compose exec -T postgres psql -U "${POSTGRES_USER:-postgres}" -d postgres -c \
        "DROP DATABASE IF EXISTS \"${POSTGRES_DB:-case_manager}\";" 2>/dev/null || true

    docker compose exec -T postgres psql -U "${POSTGRES_USER:-postgres}" -d postgres -c \
        "CREATE DATABASE \"${POSTGRES_DB:-case_manager}\";" 2>/dev/null

    # Copy dump to container and restore
    docker compose cp "$BACKUP_CONTENT_DIR/database.dump" postgres:/tmp/database.dump

    docker compose exec -T postgres pg_restore -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-case_manager}" \
        --no-owner --no-acl --clean --if-exists /tmp/database.dump 2>/dev/null || {
        log_warn "Some restore warnings (this is often normal)"
    }

    docker compose exec -T postgres rm /tmp/database.dump

    log_info "PostgreSQL restore complete"
else
    log_warn "No PostgreSQL backup found"
fi

# 2. Restore Neo4j
if [ -f "$BACKUP_CONTENT_DIR/neo4j_data.tar.gz" ]; then
    log_step "Restoring Neo4j database..."

    # Stop neo4j
    docker compose stop neo4j 2>/dev/null || true
    sleep 2

    # Get the volume name
    NEO4J_VOLUME="${COMPOSE_PROJECT}_neo4j_data"

    # Clear and restore volume
    docker run --rm \
        -v "${NEO4J_VOLUME}:/data" \
        -v "$BACKUP_CONTENT_DIR:/backup:ro" \
        alpine:3.19 \
        sh -c "rm -rf /data/* && tar -xzf /backup/neo4j_data.tar.gz -C /data"

    # Start neo4j
    docker compose up -d neo4j
    sleep 5

    log_info "Neo4j restore complete"
else
    log_warn "No Neo4j backup found"
fi

# 3. Restore file volumes
VOLUMES=(
    "evidence_data:evidence"
    "upload_data:uploads"
    "export_data:exports"
    "report_data:reports"
)

for vol_map in "${VOLUMES[@]}"; do
    vol_name="${vol_map%%:*}"
    dir_name="${vol_map##*:}"
    tar_file="$BACKUP_CONTENT_DIR/${dir_name}.tar.gz"

    if [ -f "$tar_file" ]; then
        log_step "Restoring volume: $vol_name..."

        full_vol_name="${COMPOSE_PROJECT}_${vol_name}"

        # Check if volume exists
        if docker volume inspect "$full_vol_name" >/dev/null 2>&1; then
            # Clear and restore volume
            docker run --rm \
                -v "${full_vol_name}:/data" \
                -v "$BACKUP_CONTENT_DIR:/backup:ro" \
                alpine:3.19 \
                sh -c "rm -rf /data/* && tar -xzf /backup/${dir_name}.tar.gz -C /data"

            log_info "  $vol_name restored"
        else
            log_warn "  Volume $full_vol_name not found, skipping"
        fi
    else
        log_warn "No backup found for $dir_name"
    fi
done

# 4. Restore API keys (if encrypted keys in backup)
if [ -f "$BACKUP_CONTENT_DIR/api_keys.json" ] && [ -s "$BACKUP_CONTENT_DIR/api_keys.json" ]; then
    log_step "API keys are included in the database backup (no separate restore needed)"
fi

# Cleanup
log_step "Cleaning up..."
rm -rf "$TEMP_DIR"

# Restart all services
log_step "Starting all services..."
docker compose up -d

# Wait for services to be healthy
log_info "Waiting for services to start..."
sleep 10

# Check service status
log_info "======================================"
log_info "Restore completed!"
log_info "======================================"
echo ""
docker compose ps
echo ""
log_info "Please verify the application is working correctly."
log_warn "Note: You may need to log in again as sessions were reset."
