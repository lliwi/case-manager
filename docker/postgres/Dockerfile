# PostgreSQL with SSL/TLS support for Case Manager
# Compliant with UNE 71506 and Ley 5/2014 security requirements
FROM postgres:15-alpine

# Install openssl for certificate generation
RUN apk add --no-cache openssl

# Create SSL directory
RUN mkdir -p /var/lib/postgresql/ssl

# Copy certificate generation script
COPY ssl/generate-certs.sh /usr/local/bin/generate-certs.sh
RUN chmod +x /usr/local/bin/generate-certs.sh

# Generate a UNIQUE self-signed CA + server certificate at build time.
# IMPORTANT: private keys are NEVER copied from the build context / repository.
# Each image build produces its own keypair so no secret is shared across
# installations or committed to version control.
RUN cd /var/lib/postgresql/ssl && \
        # Generate CA key and certificate
        openssl genrsa -out ca.key 4096 && \
        openssl req -new -x509 -days 3650 -key ca.key -out ca.crt \
            -subj "/CN=CaseManager-CA/O=CaseManager/OU=Security" && \
        # Generate server key and certificate
        openssl genrsa -out server.key 4096 && \
        openssl req -new -key server.key -out server.csr \
            -subj "/CN=postgres/O=CaseManager/OU=Database" && \
        openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
            -out server.crt -days 365 && \
        rm -f server.csr ca.srl && \
    chown -R postgres:postgres /var/lib/postgresql/ssl && \
    chmod 600 /var/lib/postgresql/ssl/server.key && \
    chmod 644 /var/lib/postgresql/ssl/server.crt && \
    chmod 644 /var/lib/postgresql/ssl/ca.crt

# Expose PostgreSQL port
EXPOSE 5432
