# Deployment Guide - Case Manager

## Overview

This guide provides comprehensive instructions for deploying Case Manager to production environments, ensuring security, performance, and legal compliance.

## Prerequisites

### System Requirements

- **OS**: Ubuntu 22.04 LTS or Debian 11+ (recommended)
- **CPU**: 4+ cores
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: 100GB+ SSD (evidence storage requirements vary)
- **Network**: Static IP with HTTPS support

### Software Requirements

- Docker 24.0+
- Docker Compose 2.20+
- PostgreSQL 15
- Neo4j 5.14
- Redis 7
- Python 3.11+
- Nginx (for reverse proxy)

## Architecture

Production deployment uses Docker Compose with the following services:

```
┌─────────────┐
│   Nginx     │  (Reverse Proxy + SSL)
└──────┬──────┘
       │
┌──────▼──────────────────────────────────────┐
│           Internal Network                   │
│                                              │
│  ┌──────┐  ┌──────────┐  ┌──────┐          │
│  │Flask │  │PostgreSQL│  │ Neo4j│          │
│  │ App  │◄─┤          │  │      │          │
│  └───┬──┘  └──────────┘  └──────┘          │
│      │                                       │
│      │     ┌───────┐  ┌────────┐  ┌──────┐│
│      └────►│ Redis │◄─┤ Celery │◄─┤Flower││
│            │       │  │Workers │  │      ││
│            └───────┘  └────────┘  └──────┘│
└───────────────────────────────────────────┘
```

## Step 1: Server Preparation

### 1.1 Update System

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl wget git vim htop
```

### 1.2 Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version
```

### 1.3 Configure Firewall

```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

## Step 2: Application Setup

### 2.1 Clone Repository

```bash
cd /opt
sudo git clone https://github.com/yourorg/case-manager.git
cd case-manager
sudo chown -R $USER:$USER .
```

### 2.2 Configure Environment

Create production `.env` file:

```bash
cd docker
cp .env.example .env
vim .env
```

**Production Environment Variables:**

```bash
# Flask Configuration
FLASK_ENV=production
SECRET_KEY=<generate-strong-random-key>  # Use: python -c "import secrets; print(secrets.token_hex(32))"
DEBUG=False

# Database URLs
DATABASE_URL=postgresql://casemanager:STRONG_PASSWORD@postgres:5432/casemanager_prod
SQLALCHEMY_DATABASE_URI=postgresql://casemanager:STRONG_PASSWORD@postgres:5432/casemanager_prod

# Neo4j Configuration
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=STRONG_NEO4J_PASSWORD

# Redis Configuration
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# Security
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Strict
PERMANENT_SESSION_LIFETIME=3600  # 1 hour

# Evidence Storage
EVIDENCE_UPLOAD_FOLDER=/data/evidence
EVIDENCE_ENCRYPTION_KEY=<generate-256-bit-key>  # Use: python -c "import secrets; print(secrets.token_urlsafe(32))"
MAX_CONTENT_LENGTH=524288000  # 500MB

# Email Configuration (for notifications)
MAIL_SERVER=smtp.yourdomain.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=noreply@yourdomain.com
MAIL_PASSWORD=EMAIL_PASSWORD

# Application URL
APP_URL=https://casemanager.yourdomain.com

# Legal Compliance
ORGANIZATION_NAME=Your Detective Agency
ORGANIZATION_CIF=A12345678
REGISTRO_NUMERO=12345  # Your registration number with Ministerio del Interior
```

### 2.3 Generate Strong Passwords

```bash
# Generate SECRET_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"

# Generate EVIDENCE_ENCRYPTION_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate database passwords
openssl rand -base64 32
```

## Step 3: SSL/TLS Configuration

### 3.1 Obtain SSL Certificate

Using Let's Encrypt (recommended):

```bash
sudo apt install -y certbot python3-certbot-nginx

# Obtain certificate
sudo certbot certonly --standalone -d casemanager.yourdomain.com
```

Certificates will be stored in:
- `/etc/letsencrypt/live/casemanager.yourdomain.com/fullchain.pem`
- `/etc/letsencrypt/live/casemanager.yourdomain.com/privkey.pem`

### 3.2 Configure Nginx

Create `/etc/nginx/sites-available/casemanager`:

```nginx
# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name casemanager.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

# HTTPS Configuration
server {
    listen 443 ssl http2;
    server_name casemanager.yourdomain.com;

    # SSL Certificates
    ssl_certificate /etc/letsencrypt/live/casemanager.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/casemanager.yourdomain.com/privkey.pem;

    # SSL Configuration (Modern)
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
    ssl_prefer_server_ciphers off;

    # HSTS
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;

    # Proxy to Flask App
    location / {
        proxy_pass http://localhost:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Flower (Celery Monitoring) - Restricted Access
    location /flower/ {
        auth_basic "Restricted Access";
        auth_basic_user_file /etc/nginx/.htpasswd;

        proxy_pass http://localhost:5555/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # File Upload Size
    client_max_body_size 500M;

    # Logging
    access_log /var/log/nginx/casemanager_access.log;
    error_log /var/log/nginx/casemanager_error.log;
}
```

Enable site:

```bash
sudo ln -s /etc/nginx/sites-available/casemanager /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 3.3 Auto-Renew SSL Certificates

```bash
# Test renewal
sudo certbot renew --dry-run

# Add to crontab
sudo crontab -e

# Add line:
0 3 * * * certbot renew --quiet && systemctl reload nginx
```

## Step 4: Database Setup

### 4.1 Initialize PostgreSQL

The database will be automatically created by Docker Compose, but you can backup/restore:

```bash
# Backup
docker exec casemanager_postgres pg_dump -U casemanager casemanager_prod > backup.sql

# Restore
cat backup.sql | docker exec -i casemanager_postgres psql -U casemanager casemanager_prod
```

### 4.2 Run Migrations

```bash
docker exec casemanager_web flask db upgrade
```

### 4.3 Create Admin User

```bash
docker exec -it casemanager_web flask shell

>>> from app.models import User, Role, db
>>> from app.extensions import bcrypt
>>>
>>> # Create admin role if not exists
>>> admin_role = Role.query.filter_by(name='admin').first()
>>> if not admin_role:
>>>     admin_role = Role(name='admin', description='Administrator')
>>>     db.session.add(admin_role)
>>>
>>> # Create admin user
>>> admin = User(
...     email='admin@youragency.com',
...     name='System Administrator',
...     tip_number='TIP-00001',
...     is_active=True,
...     mfa_enabled=False
... )
>>> admin.password = 'ChangeThisPassword123!'
>>> admin.roles.append(admin_role)
>>> db.session.add(admin)
>>> db.session.commit()
>>> exit()
```

## Step 5: Launch Application

### 5.1 Start Services

```bash
cd /opt/case-manager/docker
docker-compose up -d
```

### 5.2 Verify Services

```bash
docker-compose ps

# Should show:
# - casemanager_web (running)
# - casemanager_postgres (healthy)
# - casemanager_neo4j (healthy)
# - casemanager_redis (healthy)
# - casemanager_celery_worker (running)
# - casemanager_celery_beat (running)
# - casemanager_flower (running)
# - casemanager_nginx (running)
```

### 5.3 Check Logs

```bash
# All logs
docker-compose logs -f

# Specific service
docker-compose logs -f web
```

## Step 6: Monitoring & Maintenance

### 6.1 Log Rotation

Configure logrotate for Docker logs:

```bash
sudo vim /etc/logrotate.d/docker-casemanager
```

```
/var/lib/docker/containers/*/*.log {
    rotate 7
    daily
    compress
    size=10M
    missingok
    delaycompress
    copytruncate
}
```

### 6.2 Automated Backups

Create backup script `/opt/case-manager/backup.sh`:

```bash
#!/bin/bash
# Case Manager Backup Script

BACKUP_DIR="/backup/casemanager"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup PostgreSQL
docker exec casemanager_postgres pg_dump -U casemanager casemanager_prod | gzip > $BACKUP_DIR/postgres_$DATE.sql.gz

# Backup Neo4j
docker exec casemanager_neo4j neo4j-admin dump --database=neo4j --to=/tmp/neo4j_backup.dump
docker cp casemanager_neo4j:/tmp/neo4j_backup.dump $BACKUP_DIR/neo4j_$DATE.dump

# Backup Evidence Files
tar -czf $BACKUP_DIR/evidence_$DATE.tar.gz /data/evidence

# Delete backups older than 30 days
find $BACKUP_DIR -type f -mtime +30 -delete

echo "Backup completed: $DATE"
```

Schedule daily backups:

```bash
chmod +x /opt/case-manager/backup.sh

# Add to crontab
0 2 * * * /opt/case-manager/backup.sh >> /var/log/casemanager_backup.log 2>&1
```

### 6.3 Monitoring

Install monitoring tools:

```bash
# Prometheus + Grafana (optional)
docker run -d --name=prometheus -p 9090:9090 prom/prometheus
docker run -d --name=grafana -p 3000:3000 grafana/grafana
```

### 6.4 Health Checks

Create health check script:

```bash
#!/bin/bash
# Health Check Script

curl -f http://localhost/health || exit 1
docker-compose ps | grep -q "unhealthy" && exit 1

echo "All services healthy"
```

## Step 7: Security Hardening

### 7.1 Database Security

```sql
-- Connect to PostgreSQL
docker exec -it casemanager_postgres psql -U postgres

-- Revoke public schema privileges
REVOKE ALL ON SCHEMA public FROM PUBLIC;

-- Create dedicated user with minimal privileges
CREATE USER readonly WITH PASSWORD 'readonly_password';
GRANT CONNECT ON DATABASE casemanager_prod TO readonly;
GRANT USAGE ON SCHEMA public TO readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly;
```

### 7.2 File System Security

```bash
# Set ownership
sudo chown -R www-data:www-data /data/evidence

# Set permissions
sudo chmod 750 /data/evidence

# Enable full disk encryption (LUKS)
sudo cryptsetup luksFormat /dev/sdb
sudo cryptsetup open /dev/sdb evidence_encrypted
sudo mkfs.ext4 /dev/mapper/evidence_encrypted
sudo mount /dev/mapper/evidence_encrypted /data/evidence
```

### 7.3 Network Security

```bash
# Configure iptables
sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
sudo iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
sudo iptables -P INPUT DROP

# Save rules
sudo iptables-save > /etc/iptables/rules.v4
```

### 7.4 Intrusion Detection

```bash
# Install Fail2ban
sudo apt install fail2ban

# Configure for Nginx
sudo vim /etc/fail2ban/jail.local
```

```ini
[nginx-http-auth]
enabled = true
port = http,https
logpath = /var/log/nginx/casemanager_error.log

[nginx-limit-req]
enabled = true
port = http,https
logpath = /var/log/nginx/casemanager_error.log
```

## Step 8: Legal Compliance (Ley 5/2014)

### 8.1 Audit Log Retention

Ensure audit logs are immutable and retained:

```sql
-- PostgreSQL: Prevent deletion of audit logs
CREATE RULE audit_log_no_delete AS ON DELETE TO audit_logs DO INSTEAD NOTHING;
CREATE RULE audit_log_no_update AS ON UPDATE TO audit_logs DO INSTEAD NOTHING;
```

### 8.2 Data Protection Officer

Configure DPO contact information:

```bash
# In .env
DPO_NAME=Your DPO Name
DPO_EMAIL=dpo@youragency.com
DPO_PHONE=+34600000000
```

### 8.3 Privacy Policy

Create and link privacy policy at `/templates/legal/privacy.html`

## Step 9: Performance Optimization

### 9.1 Database Tuning

PostgreSQL configuration (`/docker/postgres/postgresql.conf`):

```ini
shared_buffers = 2GB
effective_cache_size = 6GB
maintenance_work_mem = 512MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 10MB
min_wal_size = 1GB
max_wal_size = 4GB
max_worker_processes = 4
max_parallel_workers_per_gather = 2
max_parallel_workers = 4
```

### 9.2 Redis Tuning

```bash
# Increase max memory
docker exec casemanager_redis redis-cli CONFIG SET maxmemory 2gb
docker exec casemanager_redis redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

### 9.3 Gunicorn Workers

Adjust worker count in `docker/flask/entrypoint.sh`:

```bash
# Formula: (2 x $num_cores) + 1
gunicorn --workers 9 --bind 0.0.0.0:5000 "app:create_app()"
```

## Step 10: Disaster Recovery

### 10.1 Create Recovery Plan

Document recovery procedures:

1. Restore from last backup
2. Verify data integrity
3. Restart services
4. Validate functionality
5. Notify users

### 10.2 Test Recovery

Regularly test backup restoration:

```bash
# Test database restore
docker exec -i casemanager_postgres psql -U postgres -c "CREATE DATABASE test_restore;"
zcat backup.sql.gz | docker exec -i casemanager_postgres psql -U casemanager test_restore
```

## Troubleshooting

### Common Issues

**Service won't start:**
```bash
docker-compose logs service_name
docker-compose down && docker-compose up -d
```

**Database connection errors:**
```bash
docker exec -it casemanager_postgres psql -U casemanager -d casemanager_prod
# Verify connection
```

**SSL certificate issues:**
```bash
sudo certbot renew --force-renewal
sudo systemctl restart nginx
```

## Support

For production support:
- Documentation: `/docs`
- Issue Tracker: GitHub Issues
- Emergency Contact: [Your contact]

## Compliance Checklist

- [ ] SSL/TLS enabled with valid certificates
- [ ] Audit logs immutable and retained
- [ ] Full disk encryption on evidence storage
- [ ] Firewall configured and active
- [ ] Automated backups running daily
- [ ] Admin user created with strong password
- [ ] MFA enabled for all users
- [ ] Privacy policy accessible
- [ ] DPO contact information configured
- [ ] Intrusion detection active
- [ ] Log rotation configured
- [ ] Health monitoring active
- [ ] Disaster recovery plan documented
- [ ] Regular security audits scheduled
