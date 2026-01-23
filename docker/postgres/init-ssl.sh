#!/bin/bash
# Initialize SSL certificates with correct permissions for PostgreSQL
set -e

SSL_SOURCE="/docker-entrypoint-initdb.d/ssl"
SSL_DEST="/var/lib/postgresql/ssl"

# Create SSL directory if it doesn't exist
mkdir -p "$SSL_DEST"

# Copy SSL files with correct permissions
if [ -f "$SSL_SOURCE/server.key" ]; then
    cp "$SSL_SOURCE/server.key" "$SSL_DEST/server.key"
    cp "$SSL_SOURCE/server.crt" "$SSL_DEST/server.crt"
    cp "$SSL_SOURCE/ca.crt" "$SSL_DEST/ca.crt"

    # Set correct ownership and permissions
    chown postgres:postgres "$SSL_DEST"/*
    chmod 600 "$SSL_DEST/server.key"
    chmod 644 "$SSL_DEST/server.crt"
    chmod 644 "$SSL_DEST/ca.crt"

    echo "SSL certificates configured successfully"
else
    echo "Warning: SSL certificates not found in $SSL_SOURCE"
fi
