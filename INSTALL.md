# Guía de Instalación - Case Manager

Sistema de gestión de investigaciones privadas conforme a la Ley 5/2014 de Seguridad Privada y estándar forense UNE 71506.

## Requisitos Previos

- Docker 20.10 o superior
- Docker Compose 2.0 o superior
- Al menos 4GB de RAM disponible
- 10GB de espacio en disco

## Instalación para Nuevas Instancias

### 1. Clonar el Repositorio

```bash
git clone <repository-url>
cd case-manager
```

### 2. Configurar Variables de Entorno

```bash
cd docker
cp .env.example .env
# Editar .env con tus configuraciones (contraseñas, claves secretas, etc.)
```

**Variables importantes a configurar:**
- `POSTGRES_PASSWORD`: Contraseña de PostgreSQL
- `SECRET_KEY`: Clave secreta de Flask (generar con `python -c "import secrets; print(secrets.token_hex(32))"`)
- `NEO4J_PASSWORD`: Contraseña de Neo4j

### 3. Iniciar Contenedores

```bash
docker-compose up -d
```

Esto iniciará:
- **PostgreSQL**: Base de datos transaccional
- **Neo4j**: Base de datos de grafos para análisis de relaciones
- **Redis**: Cola de mensajes para tareas asíncronas
- **Flask Web**: Aplicación web principal
- **Celery Worker**: Procesamiento de tareas en segundo plano
- **Flower**: Monitor de tareas Celery

### 4. Inicializar Base de Datos

Ejecutar el script de configuración:

```bash
cd ..
./setup_database.sh
```

Este script:
- Verifica que los contenedores estén ejecutándose
- Espera a que PostgreSQL esté listo
- Aplica todas las migraciones de base de datos
- Crea todas las tablas necesarias

**Tablas creadas:**
- `users`, `roles`: Gestión de usuarios y permisos
- `audit_logs`: Registro de auditoría inmutable
- `cases`, `legitimacy_types_custom`: Gestión de casos
- `evidences`, `chain_of_custody`: Evidencias y cadena de custodia
- `evidence_analyses`: Resultados de análisis forenses (NUEVO)
- `graph_nodes`, `graph_relationships`: Análisis de relaciones
- `timeline_events`: Línea temporal de investigaciones
- `reports`: Informes periciales

### 5. Crear Usuario Inicial

```bash
docker exec casemanager_web python create_test_user.py
```

Credenciales por defecto:
- **Email**: admin@casemanager.com
- **Contraseña**: admin123
- **Roles**: Admin, Detective
- **TIP**: TIP-00001

**⚠️ IMPORTANTE**: Cambiar estas credenciales en producción.

### 6. Acceder a la Aplicación

- **Aplicación Web**: http://localhost
- **Neo4j Browser**: http://localhost:7474
- **Flower (Monitor Celery)**: http://localhost:5555

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

## Respaldo y Recuperación

```bash
# Backup PostgreSQL
docker exec casemanager_postgres pg_dump -U postgres case_manager > backup_$(date +%Y%m%d).sql

# Backup Neo4j
docker exec casemanager_neo4j neo4j-admin dump --to=/backups/neo4j_$(date +%Y%m%d).dump

# Restaurar PostgreSQL
cat backup_20260109.sql | docker exec -i casemanager_postgres psql -U postgres -d case_manager
```

## Soporte

Para reportar problemas o solicitar ayuda:
- Revisar logs: `docker-compose logs`
- Verificar estado del sistema en `/admin/` (requiere rol admin)
- Consultar documentación técnica en [Requisitos App Investigación Privada Flask.md](Requisitos App Investigación Privada Flask.md)
