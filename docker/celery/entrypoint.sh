#!/bin/bash

set -e

echo "Waiting for Redis..."
until redis-cli -h redis -p 6379 -a ${REDIS_PASSWORD} ping 2>/dev/null; do
  sleep 1
done
echo "Redis is ready!"

# Execute the main command
exec "$@"
