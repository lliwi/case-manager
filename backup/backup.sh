#!/bin/bash
#
# Case Manager - Docker Volume Backup Script
#
# Creates a complete backup of all Docker volumes including:
# - PostgreSQL database (via pg_dump for consistency)
# - Neo4j database
# - Evidence files
# - Uploads, exports, reports
#
# Usage: ./backup.sh [backup_name]
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DOCKER_DIR="$PROJECT_DIR/docker"
BACKUP_DIR="$PROJECT_DIR/data/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="${1:-backup_$TIMESTAMP}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Create backup directory
mkdir -p "$BACKUP_DIR"
TEMP_DIR=$(mktemp -d)
BACKUP_WORK_DIR="$TEMP_DIR/$BACKUP_NAME"
mkdir -p "$BACKUP_WORK_DIR"

log_info "Starting backup: $BACKUP_NAME"
log_info "Temporary directory: $TEMP_DIR"

# Change to docker directory for docker-compose
cd "$DOCKER_DIR"

# Load environment variables (the real env lives in docker/.env)
ENV_FILE=""
for candidate in "$DOCKER_DIR/.env" "$PROJECT_DIR/.env"; do
    if [ -f "$candidate" ]; then ENV_FILE="$candidate"; break; fi
done

# Read a single value from the env file (safe with +,/,= in values)
get_env() {
    [ -n "$ENV_FILE" ] && grep -E "^$1=" "$ENV_FILE" | head -1 | cut -d= -f2- || true
}

# Export the variables this script needs without xargs/source pitfalls
for _k in POSTGRES_USER POSTGRES_DB NEO4J_USER NEO4J_PASSWORD \
          SECRET_KEY EVIDENCE_ENCRYPTION_KEY API_KEY_ENCRYPTION_KEY; do
    _v=$(get_env "$_k")
    [ -n "$_v" ] && export "$_k=$_v"
done

# 1. Backup PostgreSQL (using pg_dump for consistent backup while running)
log_info "Backing up PostgreSQL database..."
docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-case_manager}" \
    --no-owner --no-acl -F c -f /tmp/database.dump 2>/dev/null || {
    log_error "Failed to create PostgreSQL dump"
    exit 1
}

# Copy dump from container
docker compose cp postgres:/tmp/database.dump "$BACKUP_WORK_DIR/database.dump"
docker compose exec -T postgres rm /tmp/database.dump

# Get database stats
DB_SIZE=$(docker compose exec -T postgres psql -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-case_manager}" -t -c "SELECT pg_size_pretty(pg_database_size('${POSTGRES_DB:-case_manager}'));" 2>/dev/null | tr -d ' ')
log_info "PostgreSQL backup complete (DB size: $DB_SIZE)"

# 2. Backup Neo4j (dump while running)
log_info "Backing up Neo4j database..."
# Neo4j community doesn't support online backup, so we copy the data directory
# First, create a consistent snapshot by stopping writes temporarily
docker compose exec -T neo4j cypher-shell -u "${NEO4J_USER:-neo4j}" -p "${NEO4J_PASSWORD}" \
    "CALL db.checkpoint()" 2>/dev/null || log_warn "Neo4j checkpoint failed (may not affect backup)"

# Create tar of neo4j data inside the container
docker compose exec -T neo4j tar -czf /tmp/neo4j_data.tar.gz -C /data . 2>/dev/null || {
    log_warn "Neo4j backup skipped (container may not be running)"
}

if docker compose exec -T neo4j test -f /tmp/neo4j_data.tar.gz 2>/dev/null; then
    docker compose cp neo4j:/tmp/neo4j_data.tar.gz "$BACKUP_WORK_DIR/neo4j_data.tar.gz"
    docker compose exec -T neo4j rm /tmp/neo4j_data.tar.gz
    log_info "Neo4j backup complete"
else
    log_warn "Neo4j backup not created"
fi

# 3. Backup file volumes using a temporary backup container
log_info "Backing up data volumes..."

# Create backups of each data volume
VOLUMES=(
    "evidence_data:/data/evidence"
    "upload_data:/data/uploads"
    "export_data:/data/exports"
    "report_data:/data/reports"
)

# Get the project name for volume naming
PROJECT_NAME=$(basename "$PROJECT_DIR" | tr '[:upper:]' '[:lower:]' | tr ' ' '_')
# Detect the effective Compose project name (used to build volume names).
# Compose may print "name": "..." with a space, so parse robustly.
COMPOSE_PROJECT=$(docker compose config --format json 2>/dev/null \
    | python3 -c "import json,sys; print(json.load(sys.stdin).get('name',''))" 2>/dev/null || true)
if [ -z "$COMPOSE_PROJECT" ]; then
    COMPOSE_PROJECT=$(docker compose config --format json 2>/dev/null \
        | grep -oE '"name": *"[^"]*"' | head -1 | sed -E 's/.*: *"([^"]*)".*/\1/')
fi
COMPOSE_PROJECT=${COMPOSE_PROJECT:-$PROJECT_NAME}
log_info "Compose project: $COMPOSE_PROJECT"

for vol_map in "${VOLUMES[@]}"; do
    vol_name="${vol_map%%:*}"
    vol_path="${vol_map##*:}"
    dir_name=$(basename "$vol_path")

    full_vol_name="${COMPOSE_PROJECT}_${vol_name}"

    log_info "Backing up volume: $vol_name..."

    # Check if volume exists and has data
    if docker volume inspect "$full_vol_name" >/dev/null 2>&1; then
        # Use alpine container to create tar
        docker run --rm \
            -v "${full_vol_name}:/source:ro" \
            -v "$BACKUP_WORK_DIR:/backup" \
            alpine:3.19 \
            sh -c "cd /source && tar -czf /backup/${dir_name}.tar.gz . 2>/dev/null || true"

        if [ -f "$BACKUP_WORK_DIR/${dir_name}.tar.gz" ]; then
            SIZE=$(du -h "$BACKUP_WORK_DIR/${dir_name}.tar.gz" | cut -f1)
            log_info "  $dir_name: $SIZE"
        else
            log_warn "  $dir_name: empty or failed"
        fi
    else
        log_warn "Volume $full_vol_name not found"
    fi
done

# 4. Export API keys (from database). Values stay ENCRYPTED; they are only
#    usable together with the encryption secret exported in step 4b.
log_info "Exporting API keys..."
docker compose exec -T postgres psql -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-case_manager}" -t -A -c \
    "SELECT COALESCE(json_agg(row_to_json(t)), '[]'::json) FROM (
        SELECT service_name, key_name, api_key_encrypted, description, is_active, created_at, last_used_at, usage_count
        FROM api_keys WHERE is_deleted = false
    ) t;" > "$BACKUP_WORK_DIR/api_keys.json" 2>/dev/null || log_warn "API keys export failed"

# 4b. Export encryption secrets (gpg-encrypted) so the backup is self-sufficient.
#     Without these, the API keys AND all evidence cannot be decrypted after a
#     restore on another host. Set BACKUP_SECRETS_PASSPHRASE to enable.
log_info "Exporting encryption secrets..."
if [ -z "${BACKUP_SECRETS_PASSPHRASE:-}" ]; then
    log_warn "BACKUP_SECRETS_PASSPHRASE not set -> encryption keys NOT included."
    log_warn "  Run with: BACKUP_SECRETS_PASSPHRASE='your-strong-pass' ./backup.sh"
    log_warn "  Otherwise API keys/evidence can't be decrypted on a fresh restore."
elif ! command -v gpg >/dev/null 2>&1; then
    log_warn "gpg not installed -> encryption keys NOT included (apt/pacman install gnupg)."
else
    SECRETS_TMP=$(mktemp)
    {
        echo "# Case Manager encryption secrets - $(date -Iseconds)"
        echo "SECRET_KEY=${SECRET_KEY:-}"
        echo "EVIDENCE_ENCRYPTION_KEY=${EVIDENCE_ENCRYPTION_KEY:-}"
        echo "API_KEY_ENCRYPTION_KEY=${API_KEY_ENCRYPTION_KEY:-}"
    } > "$SECRETS_TMP"
    if gpg --batch --yes --pinentry-mode loopback \
           --passphrase "$BACKUP_SECRETS_PASSPHRASE" \
           -c -o "$BACKUP_WORK_DIR/secrets.env.gpg" "$SECRETS_TMP" 2>/dev/null; then
        log_info "Encryption secrets exported (secrets.env.gpg, AES-256 / gpg)"
    else
        log_warn "Failed to encrypt secrets with gpg"
    fi
    shred -u "$SECRETS_TMP" 2>/dev/null || rm -f "$SECRETS_TMP"
fi

# 5. Create manifest
log_info "Creating manifest..."
cat > "$BACKUP_WORK_DIR/manifest.json" << EOF
{
    "version": "2.0",
    "backup_name": "$BACKUP_NAME",
    "created_at": "$(date -Iseconds)",
    "created_by": "$(whoami)@$(cat /etc/hostname 2>/dev/null || echo 'localhost')",
    "docker_compose_project": "$COMPOSE_PROJECT",
    "components": {
        "database": $([ -f "$BACKUP_WORK_DIR/database.dump" ] && echo "true" || echo "false"),
        "neo4j": $([ -f "$BACKUP_WORK_DIR/neo4j_data.tar.gz" ] && echo "true" || echo "false"),
        "evidence": $([ -f "$BACKUP_WORK_DIR/evidence.tar.gz" ] && echo "true" || echo "false"),
        "uploads": $([ -f "$BACKUP_WORK_DIR/uploads.tar.gz" ] && echo "true" || echo "false"),
        "exports": $([ -f "$BACKUP_WORK_DIR/exports.tar.gz" ] && echo "true" || echo "false"),
        "reports": $([ -f "$BACKUP_WORK_DIR/reports.tar.gz" ] && echo "true" || echo "false"),
        "api_keys": $([ -s "$BACKUP_WORK_DIR/api_keys.json" ] && echo "true" || echo "false"),
        "secrets": $([ -f "$BACKUP_WORK_DIR/secrets.env.gpg" ] && echo "true" || echo "false")
    },
    "sizes": {
        "database": "$(du -h "$BACKUP_WORK_DIR/database.dump" 2>/dev/null | cut -f1 || echo "0")",
        "neo4j": "$(du -h "$BACKUP_WORK_DIR/neo4j_data.tar.gz" 2>/dev/null | cut -f1 || echo "0")",
        "evidence": "$(du -h "$BACKUP_WORK_DIR/evidence.tar.gz" 2>/dev/null | cut -f1 || echo "0")",
        "uploads": "$(du -h "$BACKUP_WORK_DIR/uploads.tar.gz" 2>/dev/null | cut -f1 || echo "0")",
        "exports": "$(du -h "$BACKUP_WORK_DIR/exports.tar.gz" 2>/dev/null | cut -f1 || echo "0")",
        "reports": "$(du -h "$BACKUP_WORK_DIR/reports.tar.gz" 2>/dev/null | cut -f1 || echo "0")"
    }
}
EOF

# 6. Create final backup archive
log_info "Creating final backup archive..."
BACKUP_FILE="$BACKUP_DIR/${BACKUP_NAME}.tar.gz"
cd "$TEMP_DIR"
tar -czf "$BACKUP_FILE" "$BACKUP_NAME"

# Calculate checksum
CHECKSUM=$(sha256sum "$BACKUP_FILE" | cut -d' ' -f1)
echo "$CHECKSUM  ${BACKUP_NAME}.tar.gz" > "$BACKUP_DIR/${BACKUP_NAME}.sha256"

# Cleanup
rm -rf "$TEMP_DIR"

# Final report
FINAL_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
log_info "======================================"
log_info "Backup completed successfully!"
log_info "======================================"
log_info "File: $BACKUP_FILE"
log_info "Size: $FINAL_SIZE"
log_info "SHA256: $CHECKSUM"
log_info ""
log_info "To restore, run:"
if [ -f "$BACKUP_WORK_DIR/secrets.env.gpg" ] 2>/dev/null || [ -n "${BACKUP_SECRETS_PASSPHRASE:-}" ]; then
    log_info "  BACKUP_SECRETS_PASSPHRASE='your-pass' ./restore.sh ${BACKUP_NAME}.tar.gz"
else
    log_info "  ./restore.sh ${BACKUP_NAME}.tar.gz"
fi
