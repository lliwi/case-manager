#!/bin/bash

# Case Manager - Startup Script
# Este script prepara y levanta todo el sistema

set -e

echo "=================================================="
echo "Case Manager - Sistema de Gestión de Casos"
echo "=================================================="
echo ""

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Verificar que existe .env
if [ ! -f .env ]; then
    echo -e "${RED}ERROR: Archivo .env no encontrado${NC}"
    echo "Por favor, copia .env.example a .env y configura las variables:"
    echo "  cp .env.example .env"
    echo "  nano .env"
    exit 1
fi

# Verificar que Docker está corriendo
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Docker no está corriendo${NC}"
    echo "Por favor, inicia Docker primero"
    exit 1
fi

echo -e "${GREEN}✓${NC} Docker está corriendo"
echo ""

# Crear directorios necesarios
echo "Creando directorios de datos..."
mkdir -p data/evidence
mkdir -p data/uploads
mkdir -p data/exports
mkdir -p logs
echo -e "${GREEN}✓${NC} Directorios creados"
echo ""

# Detener contenedores existentes si los hay
echo "Deteniendo contenedores existentes..."
cd docker
docker-compose down 2>/dev/null || true
echo -e "${GREEN}✓${NC} Contenedores detenidos"
echo ""

# Construir imágenes
echo "Construyendo imágenes Docker (esto puede tardar varios minutos la primera vez)..."
docker-compose build
echo -e "${GREEN}✓${NC} Imágenes construidas"
echo ""

# Levantar servicios
echo "Levantando servicios..."
docker-compose up -d postgres neo4j redis
echo "Esperando a que las bases de datos estén listas..."
sleep 15

# Verificar que los servicios están healthy
echo "Verificando servicios..."
docker-compose ps

# Levantar el resto de servicios
echo ""
echo "Levantando aplicación web y workers..."
docker-compose up -d web celery_worker celery_beat flower nginx
echo -e "${GREEN}✓${NC} Todos los servicios levantados"
echo ""

# Esperar a que Flask esté listo
echo "Esperando a que la aplicación esté lista..."
sleep 10

# Inicializar base de datos
echo "Inicializando base de datos PostgreSQL..."
docker-compose exec -T web flask db upgrade 2>/dev/null || echo "Migraciones pendientes"

# Inicializar Neo4j constraints
echo "Inicializando constraints de Neo4j..."
docker-compose exec -T web flask init-neo4j 2>/dev/null || echo "Neo4j ya inicializado"

echo ""
echo "=================================================="
echo -e "${GREEN}✓ Sistema iniciado correctamente${NC}"
echo "=================================================="
echo ""
echo "Servicios disponibles:"
echo ""
echo "  🌐 Aplicación Web:      http://localhost"
echo "  📊 Flower (Celery):     http://localhost:5555"
echo "  🗄️  Neo4j Browser:       http://localhost:7474"
echo ""
echo "Para crear un usuario administrador:"
echo "  docker-compose exec web flask create-admin"
echo ""
echo "Para ver logs:"
echo "  docker-compose logs -f web"
echo ""
echo "Para detener el sistema:"
echo "  docker-compose down"
echo ""
echo "=================================================="
