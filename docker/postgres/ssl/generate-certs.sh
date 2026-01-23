#!/bin/bash
# Generate SSL certificates for PostgreSQL TLS encryption
# This script creates a self-signed CA and server certificate for development/production use

set -e

CERT_DIR="$(dirname "$0")"
cd "$CERT_DIR"

# Certificate validity (10 years for CA, 1 year for server)
CA_DAYS=3650
SERVER_DAYS=365

# Common Name for certificates
CA_CN="CaseManager-CA"
SERVER_CN="postgres"

echo "=== Generating SSL certificates for PostgreSQL TLS ==="

# 1. Generate CA private key
echo "[1/6] Generating CA private key..."
openssl genrsa -out ca.key 4096

# 2. Generate CA certificate
echo "[2/6] Generating CA certificate..."
openssl req -new -x509 -days $CA_DAYS -key ca.key -out ca.crt \
    -subj "/CN=$CA_CN/O=CaseManager/OU=Security"

# 3. Generate server private key
echo "[3/6] Generating server private key..."
openssl genrsa -out server.key 2048

# 4. Generate server certificate signing request
echo "[4/6] Generating server CSR..."
openssl req -new -key server.key -out server.csr \
    -subj "/CN=$SERVER_CN/O=CaseManager/OU=Database"

# 5. Create server certificate extensions file
echo "[5/6] Creating certificate extensions..."
cat > server.ext << EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = postgres
DNS.2 = localhost
DNS.3 = casemanager_postgres
IP.1 = 127.0.0.1
EOF

# 6. Sign server certificate with CA
echo "[6/6] Signing server certificate..."
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out server.crt -days $SERVER_DAYS -extfile server.ext

# Set proper permissions (PostgreSQL requires specific permissions)
chmod 600 server.key
chmod 644 server.crt ca.crt

# Clean up temporary files
rm -f server.csr server.ext ca.srl

echo ""
echo "=== SSL certificates generated successfully ==="
echo ""
echo "Files created:"
echo "  - ca.crt      : CA certificate (share with clients for verification)"
echo "  - ca.key      : CA private key (keep secure!)"
echo "  - server.crt  : Server certificate"
echo "  - server.key  : Server private key"
echo ""
echo "PostgreSQL configuration (postgresql.conf):"
echo "  ssl = on"
echo "  ssl_cert_file = '/var/lib/postgresql/ssl/server.crt'"
echo "  ssl_key_file = '/var/lib/postgresql/ssl/server.key'"
echo "  ssl_ca_file = '/var/lib/postgresql/ssl/ca.crt'"
echo ""
echo "To verify certificates:"
echo "  openssl verify -CAfile ca.crt server.crt"
echo ""
