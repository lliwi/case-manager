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

# Copy the host-generated certificates into the image. These are produced per
# installation by setup.sh (or generate-certs.sh), are UNIQUE per install and
# are NOT committed to version control (see .gitignore). The same ca.crt is
# mounted into the web/celery containers, so the CA matches and TLS verifies.
# The glob keeps the build working even if a particular file is absent.
COPY ssl/server.crt* ssl/server.key* ssl/ca.crt* /var/lib/postgresql/ssl/

# Fallback: if no certificates were provided, generate a self-signed set so the
# image still works standalone. Then fix ownership/permissions (PostgreSQL
# requires the private key to be owned by the db user and not group/world
# readable).
RUN if [ ! -f /var/lib/postgresql/ssl/server.key ]; then \
        cd /var/lib/postgresql/ssl && \
        openssl genrsa -out ca.key 4096 && \
        openssl req -new -x509 -days 3650 -key ca.key -out ca.crt \
            -subj "/CN=CaseManager-CA/O=CaseManager/OU=Security" && \
        openssl genrsa -out server.key 4096 && \
        openssl req -new -key server.key -out server.csr \
            -subj "/CN=postgres/O=CaseManager/OU=Database" && \
        openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
            -out server.crt -days 365 && \
        rm -f server.csr ca.srl; \
    fi && \
    chown -R postgres:postgres /var/lib/postgresql/ssl && \
    chmod 600 /var/lib/postgresql/ssl/server.key && \
    chmod 644 /var/lib/postgresql/ssl/server.crt && \
    chmod 644 /var/lib/postgresql/ssl/ca.crt

# Expose PostgreSQL port
EXPOSE 5432
