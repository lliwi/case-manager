FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy entrypoint script and make it executable (as root)
COPY docker/flask/entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Create data directories
RUN mkdir -p /app/data/evidence /app/data/uploads /app/data/exports && \
    chown -R appuser:appuser /app/data

# Expose port
EXPOSE 5000

# Switch to non-root user
USER appuser

ENTRYPOINT ["/entrypoint.sh"]
