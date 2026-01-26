# Guia de Instalacion - Case Manager

Sistema de gestion de investigaciones privadas conforme a la Ley 5/2014 de Seguridad Privada y estandar forense UNE 71506.

## Requisitos Previos

- Docker 20.10 o superior
- Docker Compose 2.0 o superior
- OpenSSL (para generar certificados SSL)
- Al menos 4GB de RAM disponible
- 10GB de espacio en disco

## Instalacion Rapida (Recomendado)

Para una instalacion limpia y automatica:

```bash
# Clonar el repositorio
git clone <repository-url>
cd case-manager

# Ejecutar instalacion completa
./setup.sh
```

El script `setup.sh` realiza automaticamente:
1. Verifica requisitos (Docker, Docker Compose)
2. Genera certificados SSL para PostgreSQL
3. Crea archivo `.env` con contraseñas seguras aleatorias
4. Construye las imagenes Docker
5. Inicia todos los contenedores
6. Inicializa la base de datos desde los modelos
7. Crea el usuario administrador inicial

### Credenciales por defecto

- **Email**: admin@casemanager.com
- **Contraseña**: admin123
- **TIP**: TIP-00001

**IMPORTANTE**: Cambiar la contraseña despues del primer inicio de sesion.

### URLs de acceso

- **Aplicacion Web**: http://localhost
- **Neo4j Browser**: http://localhost:7474
- **Flower (Monitor Celery)**: http://localhost:5555

---

## Instalacion Manual (Avanzado)

Si prefieres control total sobre el proceso:

### 1. Clonar el Repositorio

```bash
git clone <repository-url>
cd case-manager
```

### 2. Configurar Variables de Entorno

```bash
cp .env.example docker/.env
# Editar docker/.env con tus configuraciones
```

**Variables importantes:**
- `SECRET_KEY`: Clave secreta de Flask
- `POSTGRES_PASSWORD`: Contraseña de PostgreSQL
- `NEO4J_PASSWORD`: Contraseña de Neo4j
- `REDIS_PASSWORD`: Contraseña de Redis
- `EVIDENCE_ENCRYPTION_KEY`: Clave de cifrado (64 caracteres hex)

Generar valores seguros:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Generar Certificados SSL

```bash
mkdir -p docker/postgres/ssl
cd docker/postgres/ssl

# CA
openssl genrsa -out ca.key 4096
openssl req -new -x509 -days 3650 -key ca.key -out ca.crt \
    -subj "/CN=CaseManager-CA"

# Server
openssl genrsa -out server.key 4096
openssl req -new -key server.key -out server.csr -subj "/CN=postgres"
openssl x509 -req -days 3650 -in server.csr -CA ca.crt -CAkey ca.key \
    -CAcreateserial -out server.crt

chmod 600 server.key
cd ../../..
```

### 4. Iniciar Contenedores

```bash
cd docker
docker-compose up -d
```

Servicios iniciados:
- **PostgreSQL**: Base de datos transaccional con SSL
- **Neo4j**: Base de datos de grafos
- **Redis**: Broker para Celery
- **Flask Web**: Aplicacion principal
- **Celery Worker**: Procesamiento asincrono
- **Celery Beat**: Tareas programadas
- **Flower**: Monitor de tareas
- **Nginx**: Proxy inverso

### 5. Inicializar Base de Datos

```bash
docker exec casemanager_web python init_database.py
```

### 6. Crear Usuario Inicial

```bash
docker exec casemanager_web python create_test_user.py
```

## Estructura de la Base de Datos

### Nueva Tabla: evidence_analyses

Almacena resultados de análisis forenses ejecutados sobre evidencias:

```sql
CREATE TABLE evidence_analyses (
    id SERIAL PRIMARY KEY,
    evidence_id INTEGER REFERENCES evidences(id) ON DELETE CASCADE,
    plugin_name VARCHAR(100) NOT NULL,
    plugin_version VARCHAR(20),
    success BOOLEAN NOT NULL DEFAULT FALSE,
    result_data JSONB NOT NULL,  -- Resultados del análisis (formato flexible)
    error_message TEXT,
    analyzed_by_id INTEGER REFERENCES users(id),
    analyzed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_evidence_analyses_evidence_id ON evidence_analyses(evidence_id);
CREATE INDEX ix_evidence_analyses_analyzed_at ON evidence_analyses(analyzed_at);
```

**Características:**
- Almacenamiento inmutable de análisis
- Formato JSONB para flexibilidad y consultas eficientes
- Trazabilidad forense completa (quién, cuándo, qué)
- Soporte para versionado de plugins

## Migraciones de Base de Datos

### Para Instalaciones Nuevas

Las migraciones se aplican automáticamente con `./setup_database.sh`

### Para Instalaciones Existentes

Si ya tienes una instalación y necesitas actualizar:

```bash
# Aplicar nuevas migraciones
docker exec casemanager_web flask db upgrade
```

### Crear Nuevas Migraciones

Cuando modifiques modelos de base de datos:

```bash
# Generar migración automáticamente
docker exec casemanager_web flask db revision --autogenerate -m "Descripción del cambio"

# Revisar el archivo generado en migrations/versions/

# Aplicar migración
docker exec casemanager_web flask db upgrade
```

## Plugins Forenses

El sistema incluye plugins de análisis forense:

1. **EXIF Extractor**: Extrae metadatos de imágenes (GPS, cámara, fecha)
2. **PDF Metadata**: Analiza metadatos de documentos PDF
3. **DNI Validator**: Valida DNI/NIE españoles (algoritmo módulo 23)

Los resultados se almacenan automáticamente en `evidence_analyses`.

## Verificación de la Instalación

```bash
# Verificar estado de contenedores
docker-compose ps

# Verificar logs de la aplicación
docker logs casemanager_web --tail=50

# Verificar conexión a PostgreSQL
docker exec casemanager_postgres psql -U postgres -d case_manager -c "\dt"

# Verificar conexión a Neo4j
docker exec casemanager_neo4j cypher-shell -u neo4j -p <password> "MATCH (n) RETURN count(n);"
```

## Solución de Problemas

### PostgreSQL no inicia

```bash
docker-compose logs postgres
# Verificar permisos del volumen de datos
```

### Migraciones fallan

```bash
# Ver estado actual
docker exec casemanager_web flask db current

# Ver historial
docker exec casemanager_web flask db history

# Marcar como aplicada sin ejecutar (solo si tablas ya existen)
docker exec casemanager_web flask db stamp head
```

### Error "Can't locate revision"

```bash
# Limpiar versión incorrecta
docker exec casemanager_postgres psql -U postgres -d case_manager -c "DELETE FROM alembic_version;"

# Reinicializar
docker exec casemanager_web flask db upgrade
```

## Actualización desde Versiones Anteriores

Si actualizas desde una versión sin `evidence_analyses`:

```bash
# La tabla se crea automáticamente al aplicar migraciones
docker exec casemanager_web flask db upgrade

# Verificar que la tabla existe
docker exec casemanager_postgres psql -U postgres -d case_manager -c "\d evidence_analyses"
```

## Seguridad

- Cambiar todas las contraseñas por defecto
- Usar certificados SSL en producción
- Configurar firewall para exponer solo puertos necesarios
- Habilitar MFA para todos los usuarios
- Rotar claves periódicamente
- Revisar logs de auditoría regularmente

## Respaldo y Recuperacion

Los backups se gestionan mediante scripts de shell para mayor fiabilidad:

```bash
# Crear backup completo (PostgreSQL + Neo4j + Volumenes)
./backup/backup.sh

# Listar backups disponibles
./backup/list.sh

# Restaurar un backup (detiene servicios temporalmente)
./backup/restore.sh backup_YYYYMMDD_HHMMSS.tar.gz
```

Los backups se almacenan en `data/backups/` e incluyen:
- Dump de PostgreSQL
- Datos de Neo4j
- Volumenes de evidencias, uploads, exports y reports
- Checksum SHA-256 para verificacion

## Soporte

Para reportar problemas o solicitar ayuda:
- Revisar logs: `docker-compose logs`
- Verificar estado del sistema en `/admin/` (requiere rol admin)
- Consultar documentación técnica en [Requisitos App Investigación Privada Flask.md](Requisitos App Investigación Privada Flask.md)
