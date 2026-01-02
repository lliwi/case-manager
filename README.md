# Case Manager - Sistema de Gestión de Investigaciones Privadas

Sistema completo de gestión de casos para detectives privados en España, cumpliendo con la Ley 5/2014 de Seguridad Privada y el estándar forense UNE 71506.

## Características Principales

- **Libro-registro Digital**: Cumplimiento automático del artículo 25 de la Ley 5/2014
- **Gestión Forense de Evidencias**: Cadena de custodia con hashes SHA-256/SHA-512
- **Grafo de Relaciones**: Análisis de conexiones con Neo4j
- **Línea de Tiempo**: Visualización cronológica de eventos con Vis.js
- **Sistema de Plugins**: Extensible para herramientas OSINT y forenses
- **Autenticación MFA**: Seguridad con autenticación de dos factores
- **Cifrado AES-256**: Protección de evidencias en reposo
- **Auditoría Inmutable**: Logs forenses para validación judicial

## Tecnologías

- **Backend**: Flask 3.0 (Python 3.11)
- **Bases de Datos**: PostgreSQL 15 + Neo4j 5.14
- **Cola de Tareas**: Celery + Redis
- **Contenedorización**: Docker + Docker Compose
- **Frontend**: Bootstrap 5, Vis.js, Cytoscape.js
- **Servidor Web**: Nginx + Gunicorn

## Requisitos Previos

- Docker 20.10+
- Docker Compose 2.0+
- 4 GB RAM mínimo (8 GB recomendado)
- 20 GB espacio en disco

## Instalación y Configuración

### 1. Clonar el repositorio

```bash
git clone <repository-url>
cd case-manager
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
```

Editar `.env` y configurar:

- `SECRET_KEY`: Clave secreta de Flask (generar con `python -c "import secrets; print(secrets.token_hex(32))"`)
- `POSTGRES_PASSWORD`: Contraseña de PostgreSQL
- `NEO4J_PASSWORD`: Contraseña de Neo4j
- `REDIS_PASSWORD`: Contraseña de Redis
- `EVIDENCE_ENCRYPTION_KEY`: Clave de cifrado de evidencias (generar con `python -c "import secrets; print(secrets.token_hex(32))"`)

### 3. Construir y levantar contenedores

```bash
cd docker
docker-compose up -d --build
```

Esto iniciará todos los servicios:
- **Web**: http://localhost (Flask + Nginx)
- **Flower**: http://localhost:5555 (Monitoreo de Celery)
- **Neo4j Browser**: http://localhost:7474 (opcional, si se expone el puerto)

### 4. Inicializar la base de datos

```bash
# Crear las tablas de PostgreSQL
docker-compose exec web flask db upgrade

# Crear constraints e índices en Neo4j
docker-compose exec web flask init-neo4j

# Crear usuario administrador
docker-compose exec web flask create-admin \
  --email admin@example.com \
  --password YourSecurePassword \
  --tip TIP123456
```

### 5. Acceder a la aplicación

Abrir navegador en http://localhost e iniciar sesión con las credenciales del administrador.

## Estructura del Proyecto

```
case-manager/
├── app/                      # Aplicación Flask
│   ├── blueprints/          # Módulos funcionales (casos, evidencias, etc.)
│   ├── models/              # Modelos de base de datos
│   ├── services/            # Lógica de negocio
│   ├── plugins/             # Sistema de plugins (OSINT, forense)
│   ├── tasks/               # Tareas asíncronas de Celery
│   ├── utils/               # Utilidades (crypto, hashing, etc.)
│   ├── static/              # CSS, JS, imágenes
│   └── templates/           # Plantillas Jinja2
├── docker/                  # Configuración de contenedores
├── data/                    # Volúmenes de datos (evidencias, etc.)
├── migrations/              # Migraciones de Alembic
├── scripts/                 # Scripts de utilidad
└── tests/                   # Tests

```

## Uso

### Gestión de Casos

1. **Crear Caso**: Dashboard → Nuevo Caso
2. **Validar Legitimidad**: Adjuntar documento que acredite el interés legítimo
3. **Subir Evidencias**: Caso → Añadir Evidencia (se calculan hashes automáticamente)
4. **Visualizar Timeline**: Ver eventos cronológicamente
5. **Analizar Grafo**: Explorar relaciones entre entidades
6. **Generar Informe**: Exportar informe pericial en PDF

### Plugins Disponibles

- **DNI/NIE Validator**: Validación de documentos españoles (algoritmo módulo 23)
- **Image EXIF Extractor**: Extracción de metadatos de imágenes (GPS, fecha, cámara)
- **Email OSINT**: Verificación de correos y brechas de seguridad (Holehe)
- **PDF Metadata**: Extracción de autoría y metadatos de documentos

### Comandos CLI Útiles

```bash
# Ver logs
docker-compose logs -f web

# Acceder al shell de Flask
docker-compose exec web flask shell

# Crear nueva migración
docker-compose exec web flask db migrate -m "Descripción"

# Aplicar migraciones
docker-compose exec web flask db upgrade

# Ver estado de tareas Celery
# Abrir http://localhost:5555
```

## Seguridad

### Cumplimiento Legal (Ley 5/2014)

- ✅ Libro-registro inmutable con sellado de tiempo
- ✅ Validación de interés legítimo antes de investigar
- ✅ Identificación profesional (TIP) obligatoria
- ✅ Detección automática de delitos perseguibles de oficio

### Estándar Forense (UNE 71506)

- ✅ Cálculo de hashes SHA-256 y SHA-512 en carga
- ✅ Cadena de custodia inmutable
- ✅ Cifrado AES-256-GCM de evidencias
- ✅ Análisis no destructivo (copias de trabajo)
- ✅ Sellado de tiempo confiable (RFC 3161)

### Buenas Prácticas

- Autenticación multifactor (TOTP) obligatoria
- Cifrado de volúmenes Docker
- Red interna aislada para bases de datos
- Rate limiting en endpoints críticos
- CSRF protection habilitado
- Logs de auditoría centralizados

## Desarrollo

### Requisitos de Desarrollo

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Ejecutar Tests

```bash
docker-compose exec web pytest
docker-compose exec web pytest --cov=app
```

### Estilo de Código

```bash
# Formatear código
docker-compose exec web black app/

# Linter
docker-compose exec web flake8 app/
```

## Arquitectura

### Microservicios Docker

- **web**: Aplicación Flask (Gunicorn)
- **postgres**: Base de datos relacional (casos, evidencias)
- **neo4j**: Base de datos de grafos (relaciones)
- **redis**: Broker de mensajes
- **celery_worker**: Procesamiento asíncrono (plugins, análisis)
- **celery_beat**: Tareas programadas
- **flower**: Monitoreo de Celery
- **nginx**: Proxy inverso y servidor estático

### Base de Datos Dual

- **PostgreSQL**: Datos transaccionales con integridad ACID
- **Neo4j**: Relaciones entre entidades (grafos)

Sincronización: Los nodos de evidencia en Neo4j referencian IDs de PostgreSQL.

## Troubleshooting

### Error: "Database connection failed"

```bash
# Verificar que PostgreSQL está corriendo
docker-compose ps postgres

# Ver logs de PostgreSQL
docker-compose logs postgres
```

### Error: "Neo4j connection refused"

```bash
# Esperar a que Neo4j termine de iniciar (puede tardar 30-60s)
docker-compose logs neo4j

# Verificar health check
docker-compose ps neo4j
```

### Error: "Redis connection error"

```bash
# Reiniciar Redis
docker-compose restart redis
```

## Contribución

1. Fork el proyecto
2. Crear feature branch (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -m 'Añadir nueva funcionalidad'`)
4. Push al branch (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## Licencia

Copyright © 2026. Sistema para uso profesional en investigación privada.

## Soporte

Para soporte técnico o consultas sobre cumplimiento legal, consultar la documentación en `docs/` o contactar al equipo de desarrollo.

---

**Advertencia Legal**: Este sistema está diseñado para uso exclusivo de detectives privados habilitados conforme a la Ley 5/2014. El uso indebido puede constituir delito. Consulte siempre con su asesor legal antes de iniciar cualquier investigación.
