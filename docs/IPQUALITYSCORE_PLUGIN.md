# Plugin IPQualityScore - Validación de Emails y Teléfonos

## Descripción

Este plugin OSINT permite validar correos electrónicos y números de teléfono utilizando la API de IPQualityScore. Proporciona detección de fraude, análisis de riesgo y verificación de contactos para investigaciones privadas.

## Características

### Validación de Emails
- **Validación de formato y existencia**: Verifica que el email sea válido y esté activo
- **Detección de emails temporales/desechables**: Identifica servicios como Guerrilla Mail, 10 Minute Mail, etc.
- **Detección de spam traps**: Identifica emails conocidos como trampas de spam
- **Verificación SMTP**: Comprueba si el servidor de correo acepta mensajes
- **Análisis de dominio**: Edad del dominio, registros DNS, etc.
- **Puntuación de fraude**: Riesgo de fraude de 0-100 (90+ = alto riesgo)
- **Detección de fugas de datos**: Verifica si el email ha aparecido en brechas de seguridad
- **Sugerencias de corrección**: Detecta errores tipográficos en dominios (ej: gmial.com → gmail.com)

### Validación de Teléfonos
- **Validación de formato y existencia**: Verifica que el número sea válido
- **Detección de línea activa**: Comprueba si el número está actualmente activo
- **Detección de VOIP**: Identifica números de VoIP (Skype, Google Voice, etc.)
- **Detección de números prepago**: Identifica tarjetas prepago
- **Información del operador**: Nombre del carrier, MCC, MNC
- **Geolocalización**: País, región, ciudad, código postal, zona horaria
- **Tipo de línea**: Móvil, fijo, VOIP, etc.
- **Puntuación de fraude**: Riesgo de fraude de 0-100 (90+ = alto riesgo)
- **Detección de SMS pumping**: Protección contra ataques de SMS pumping
- **Emails asociados**: Direcciones de email vinculadas al número (si están disponibles)

## Instalación y Configuración

### 1. Obtener API Key de IPQualityScore

1. Regístrate en [IPQualityScore](https://www.ipqualityscore.com/create-account)
2. Navega a tu panel de control
3. Copia tu API Key (formato: `bhjeKwHmvOOLLPSjqs3MdxVnXQXDKuqG`)

### 2. Configurar API Key en Case Manager

1. Inicia sesión como **administrador**
2. Ve al **Panel de Administración** (`/admin/`)
3. Haz clic en **"Gestionar API Keys"**
4. Clic en **"Nueva API Key"**
5. Completa el formulario:
   - **Servicio**: Selecciona "IPQualityScore (Email/Phone Validation)"
   - **Nombre**: Ej: "IPQualityScore - Producción"
   - **API Key**: Pega tu clave API
   - **Descripción**: Opcional, describe el propósito
   - **Activa**: Marca el checkbox para activarla
6. Haz clic en **"Crear API Key"**

### 3. Probar la Conexión

Después de crear la API Key:
1. En la lista de API Keys, haz clic en el botón **"⚡"** (Probar conexión)
2. Si todo está correcto, verás un mensaje de éxito
3. El contador de uso se incrementará en 1

## Uso del Plugin

### Desde la Interfaz Web

#### Opción 1: Plugins > IPQualityScore Validator

1. Ve a **Plugins** en el menú principal
2. Busca **"IPQualityScore - Validador Email/Teléfono"**
3. Haz clic en **"Usar Plugin"**
4. Introduce el email o teléfono a validar
5. Selecciona el tipo (o deja en "Auto-detectar")
6. Haz clic en **"Validar"**

#### Opción 2: Desde un Caso

1. Abre un caso existente
2. Ve a la sección **"Análisis OSINT"**
3. Selecciona el plugin **"IPQualityScore Validator"**
4. Introduce el contacto a validar
5. Los resultados se guardarán vinculados al caso

### Desde Código Python

```python
from app.plugins.osint.ipqualityscore_validator import IPQualityScoreValidatorPlugin

# Inicializar plugin
plugin = IPQualityScoreValidatorPlugin()

# Validar email
email_result = plugin.lookup('usuario@example.com', query_type='email')
print(f"Email válido: {email_result['valid']}")
print(f"Riesgo de fraude: {email_result['fraud_score']}/100")
print(f"Recomendación: {email_result['interpretation']['recommendation']}")

# Validar teléfono
phone_result = plugin.lookup('+34612345678', query_type='phone')
print(f"Teléfono válido: {phone_result['valid']}")
print(f"Línea activa: {phone_result['active']}")
print(f"Operador: {phone_result['carrier']}")
print(f"Tipo: {phone_result['line_type']}")
```

### API Service Directamente

```python
from app.models.api_key import ApiKey
from app.services.ipqualityscore_service import IPQualityScoreService

# Obtener API key activa
api_key = ApiKey.get_active_key('ipqualityscore')

# Inicializar servicio
service = IPQualityScoreService(api_key)

# Validar email
email_result = service.validate_email('test@example.com', strict=True)

# Validar teléfono
phone_result = service.validate_phone('+34612345678', country='ES')
```

## Interpretación de Resultados

### Niveles de Riesgo

| Puntuación | Nivel | Color | Acción Recomendada |
|------------|-------|-------|-------------------|
| 0-74 | Bajo | Verde (success) | Aceptar |
| 75-84 | Medio | Amarillo (warning) | Precaución - Monitorear |
| 85-89 | Alto | Naranja (warning) | Revisar - Verificación adicional |
| 90-100 | Muy Alto | Rojo (danger) | Rechazar |

### Campos Importantes

#### Emails
- **valid**: `true/false` - Si el formato y existencia son válidos
- **disposable**: `true/false` - Email temporal/desechable
- **fraud_score**: `0-100` - Puntuación de riesgo de fraude
- **smtp_score**: `0-3` - Calidad de entrega (3 = mejor)
- **deliverability**: `high/medium/low` - Probabilidad de entrega
- **recent_abuse**: `true/false` - Reportado recientemente por abuso
- **leaked**: `true/false` - Encontrado en brechas de datos

#### Teléfonos
- **valid**: `true/false` - Si el número es válido
- **active**: `true/false` - Si la línea está activa
- **fraud_score**: `0-100` - Puntuación de riesgo de fraude
- **VOIP**: `true/false` - Es un número VOIP
- **risky**: `true/false` - Considerado de alto riesgo
- **line_type**: `Mobile/Landline/VOIP/etc.` - Tipo de línea
- **carrier**: Nombre del operador
- **prepaid**: `true/false` - Es prepago
- **recent_abuse**: `true/false` - Reportado por abuso

## Ejemplos de Uso para Investigaciones

### Caso 1: Verificación de Denunciante

```python
# Validar el email del denunciante antes de aceptar el caso
result = plugin.lookup('denunciante@empresa.com', query_type='email')

if result['fraud_score'] > 85:
    print("⚠️ Alto riesgo - Email sospechoso, solicitar verificación adicional")
elif result['disposable']:
    print("⚠️ Email temporal - Solicitar email corporativo o personal permanente")
else:
    print("✓ Email válido - Proceder con el caso")
```

### Caso 2: Investigación de Contactos Sospechosos

```python
# Analizar un teléfono encontrado en evidencia
result = plugin.lookup('+34666123456', query_type='phone')

if not result['active']:
    print("❌ Número inactivo - Posible línea desechada")
elif result['VOIP']:
    print("⚠️ Número VOIP - Puede dificultar rastreo")
else:
    print(f"✓ Número activo - Operador: {result['carrier']}, Tipo: {result['line_type']}")

# Agregar a timeline del caso
timeline.add_event(
    event_type='CONTACT_VALIDATION',
    description=f"Teléfono validado: {result['formatted']}",
    metadata=result
)
```

### Caso 3: Validación Masiva

```python
# Validar lista de contactos encontrados en evidencia
contacts = [
    'contact1@example.com',
    '+34611222333',
    'contact2@tempmail.com',
    '+34622333444'
]

risky_contacts = []

for contact in contacts:
    result = plugin.lookup(contact, query_type='auto')

    if result['fraud_score'] >= 75:
        risky_contacts.append({
            'contact': contact,
            'fraud_score': result['fraud_score'],
            'reason': result['interpretation']['recommendation']
        })

# Generar informe de contactos sospechosos
for risky in risky_contacts:
    print(f"⚠️ {risky['contact']}: {risky['reason']} (score: {risky['fraud_score']})")
```

## Consideraciones Legales

### Ley 5/2014 de Seguridad Privada

- **Proporcionalidad**: Solo valida contactos cuando existe interés legítimo del cliente
- **No intrusivo**: No constituye una medida de seguimiento activo (permitido)
- **Trazabilidad**: Todos los análisis quedan registrados en auditoría
- **Privacidad**: Los datos se almacenan encriptados (AES-256)

### RGPD / LOPD-GDD

- **Finalidad**: Validación para prevención de fraude en investigaciones legítimas
- **Minimización**: Solo se solicitan los datos necesarios (email o teléfono)
- **Seguridad**: API keys encriptadas, transmisión TLS
- **Auditoría**: Log completo de todas las validaciones

### Buenas Prácticas

1. **Documenta la necesidad**: Justifica por qué necesitas validar el contacto
2. **Informa al cliente**: Incluye en el contrato que se usarán servicios de validación
3. **No abuses del servicio**: Las API keys tienen límites de uso
4. **Protege las API keys**: Solo administradores pueden verlas y gestionarlas
5. **Revisa periódicamente**: Verifica que solo se usen API keys autorizadas

## Gestión de API Keys

### Ver API Keys Activas

```bash
# Desde Flask shell
from app.models.api_key import ApiKey

active_keys = ApiKey.query.filter_by(
    service_name='ipqualityscore',
    is_active=True,
    is_deleted=False
).all()

for key in active_keys:
    print(f"{key.key_name}: {key.usage_count} usos")
```

### Rotar API Keys

1. Crea una nueva API Key en IPQualityScore
2. En Case Manager, crea una nueva API Key con la nueva clave
3. Marca la nueva como "Activa"
4. Desactiva o elimina la API Key antigua
5. Verifica que el sistema usa la nueva clave

### Monitorear Uso

```sql
-- Ver uso por API Key (PostgreSQL)
SELECT
    key_name,
    usage_count,
    last_used_at,
    created_at
FROM api_keys
WHERE service_name = 'ipqualityscore'
    AND is_deleted = false
ORDER BY usage_count DESC;
```

## Troubleshooting

### Error: "No hay API Key activa configurada"

**Causa**: No existe una API Key activa para IPQualityScore

**Solución**:
1. Ve a `/admin/api-keys`
2. Verifica que existe una API Key con servicio "ipqualityscore"
3. Asegúrate de que está marcada como "Activa"
4. Si no existe, créala

### Error: "Invalid API key"

**Causa**: La API Key es incorrecta o ha sido revocada

**Solución**:
1. Verifica en el panel de IPQualityScore que la API Key es válida
2. Copia la API Key correcta
3. Edita la API Key en Case Manager y actualízala
4. Prueba la conexión

### Error: "Rate limit exceeded"

**Causa**: Has superado el límite de consultas de tu plan de IPQualityScore

**Solución**:
1. Verifica tu plan en IPQualityScore
2. Considera actualizar a un plan superior
3. Implementa caché local para evitar consultas duplicadas

### Email/Teléfono inválido pero parece correcto

**Causa**: Puede ser un formato no estándar o un error temporal de la API

**Solución**:
1. Verifica el formato del contacto
2. Para teléfonos, usa formato internacional (ej: +34612345678)
3. Prueba con el modo "fast" para validación rápida
4. Si persiste, valida manualmente

## Recursos Adicionales

- **Documentación IPQualityScore**: https://www.ipqualityscore.com/documentation
- **Panel de Control**: https://www.ipqualityscore.com/user/settings
- **Soporte**: https://www.ipqualityscore.com/contact
- **Precios**: https://www.ipqualityscore.com/plans

## Changelog

### v1.0.0 (2026-01-11)
- ✨ Implementación inicial del plugin
- ✨ Validación de emails con 20+ indicadores
- ✨ Validación de teléfonos con geolocalización
- ✨ Gestión de API keys en panel de administración
- ✨ Sistema de interpretación de riesgos
- ✨ Integración con sistema de auditoría
- ✨ Migraciones de base de datos
- 📝 Documentación completa

## Licencia

Este plugin es parte del sistema Case Manager y está sujeto a la misma licencia del proyecto principal.

## Soporte

Para problemas o preguntas:
1. Revisa esta documentación
2. Consulta los logs de auditoría en `/admin/audit-logs`
3. Contacta al administrador del sistema
