# API Documentation - Case Manager

## Overview

This document provides comprehensive API documentation for the Case Manager application, including all endpoints, request/response formats, and usage examples.

## Base URL

```
http://localhost (production will use HTTPS)
```

## Authentication

All API endpoints require authentication via Flask-Login session cookies. Users must log in through the web interface before accessing API endpoints.

### Login

```http
POST /auth/login
Content-Type: application/x-www-form-urlencoded

email=user@example.com&password=SecurePassword123!
```

**Response:**
```http
302 Found
Location: /dashboard/
Set-Cookie: session=...
```

### Logout

```http
GET /auth/logout
```

**Response:**
```http
302 Found
Location: /auth/login
```

---

## Cases API

### List All Cases

```http
GET /cases/
```

**Response:**
```json
{
  "cases": [
    {
      "id": 1,
      "numero_orden": "2026-0001",
      "title": "Investigation Title",
      "status": "ACTIVO",
      "priority": "ALTA",
      "fecha_apertura": "2026-01-01T10:00:00Z"
    }
  ]
}
```

### Get Case Details

```http
GET /cases/{case_id}
```

**Response:**
```json
{
  "id": 1,
  "numero_orden": "2026-0001",
  "title": "Investigation Title",
  "description": "Case description",
  "client_name": "Client Name",
  "client_contact": "client@example.com",
  "subject_name": "Subject Name",
  "legitimacy_type": "INFIDELIDAD_CONYUGAL",
  "legitimacy_justification": "Justification text",
  "status": "ACTIVO",
  "priority": "ALTA",
  "is_confidential": true,
  "fecha_apertura": "2026-01-01T10:00:00Z",
  "detective": {
    "id": 1,
    "name": "Detective Name",
    "tip_number": "TIP-00001"
  }
}
```

### Create Case

```http
POST /cases/create
Content-Type: application/x-www-form-urlencoded

title=Investigation+Title&
description=Case+description&
client_name=Client+Name&
client_contact=client@example.com&
subject_name=Subject+Name&
legitimacy_type=INFIDELIDAD_CONYUGAL&
legitimacy_justification=Detailed+justification&
priority=ALTA&
is_confidential=true
```

**Response:**
```http
302 Found
Location: /cases/1
```

### Validate Case

```http
POST /cases/{case_id}/validate

approved=true&
notes=Case+approved+for+investigation
```

**Response:**
```http
302 Found
Location: /cases/1
```

### Close Case

```http
POST /cases/{case_id}/close

conclusion=Investigation+completed&
outcome=Evidence+gathered+successfully
```

---

## Evidence API

### Upload Evidence

```http
POST /evidence/case/{case_id}/upload
Content-Type: multipart/form-data

------WebKitFormBoundary
Content-Disposition: form-data; name="file"; filename="evidence.jpg"
Content-Type: image/jpeg

[binary data]
------WebKitFormBoundary
Content-Disposition: form-data; name="description"

Photo evidence from surveillance
------WebKitFormBoundary
Content-Disposition: form-data; name="evidence_type"

IMAGE
------WebKitFormBoundary--
```

**Response:**
```json
{
  "success": true,
  "evidence_id": 42,
  "sha256": "a1b2c3...",
  "sha512": "d4e5f6..."
}
```

### Get Evidence Details

```http
GET /evidence/{evidence_id}
```

**Response:**
```json
{
  "id": 42,
  "case_id": 1,
  "original_filename": "evidence.jpg",
  "file_size": 1048576,
  "mime_type": "image/jpeg",
  "evidence_type": "IMAGE",
  "sha256_hash": "a1b2c3...",
  "sha512_hash": "d4e5f6...",
  "uploaded_by": {
    "id": 1,
    "name": "Detective Name"
  },
  "upload_date": "2026-01-01T14:30:00Z",
  "is_encrypted": true,
  "description": "Photo evidence from surveillance"
}
```

### Download Evidence

```http
GET /evidence/{evidence_id}/download
```

**Response:**
```http
200 OK
Content-Type: image/jpeg
Content-Disposition: attachment; filename="evidence.jpg"

[binary data]
```

### Verify Evidence Integrity

```http
POST /evidence/{evidence_id}/verify
```

**Response:**
```json
{
  "success": true,
  "sha256_match": true,
  "sha512_match": true,
  "integrity_ok": true
}
```

---

## Timeline API

### Get Case Timeline

```http
GET /timeline/case/{case_id}
```

**Response:**
```json
{
  "events": [
    {
      "id": 1,
      "event_type": "SURVEILLANCE",
      "title": "Subject observed at location",
      "description": "Subject arrived at 14:30",
      "event_date": "2026-01-01T14:30:00Z",
      "location": "Cafe Central, Madrid",
      "latitude": 40.4168,
      "longitude": -3.7038,
      "subjects": ["Subject Name"],
      "tags": ["surveillance", "observation"],
      "confidence": 0.95
    }
  ]
}
```

### Create Timeline Event

```http
POST /timeline/case/{case_id}/create

event_type=SURVEILLANCE&
title=Subject+observed&
description=Details&
event_date=2026-01-01T14:30&
location=Madrid&
latitude=40.4168&
longitude=-3.7038&
subjects=Subject+Name&
tags=surveillance,observation&
confidence=0.95
```

### Export Timeline (JSON)

```http
GET /timeline/case/{case_id}/export/json
```

**Response:**
```json
[
  {
    "id": 1,
    "title": "Event Title",
    "start": "2026-01-01T14:30:00Z",
    "content": "Event description",
    "className": "event-surveillance"
  }
]
```

### Detect Timeline Patterns

```http
GET /timeline/case/{case_id}/patterns
```

**Response:**
```json
{
  "recurring_locations": [
    {
      "location": "Cafe Central, Madrid",
      "count": 5,
      "coordinates": [40.4168, -3.7038]
    }
  ],
  "peak_hours": [14, 15, 16],
  "weekday_activity": {
    "monday": 3,
    "tuesday": 5,
    "wednesday": 2
  }
}
```

---

## Reports API

### List Case Reports

```http
GET /reports/case/{case_id}/reports
```

**Response:**
```json
{
  "reports": [
    {
      "id": 1,
      "title": "Final Investigation Report",
      "report_type": "FINAL",
      "status": "COMPLETED",
      "version": 1,
      "created_at": "2026-01-15T10:00:00Z"
    }
  ]
}
```

### Create Report

```http
POST /reports/case/{case_id}/create

title=Final+Report&
report_type=FINAL&
introduction=Introduction+text&
methodology=Methodology+description&
findings=Findings+details&
conclusions=Conclusions&
recommendations=Recommendations
```

### Generate PDF Report

```http
POST /reports/{report_id}/generate-pdf
```

**Response:**
```http
200 OK
Content-Type: application/pdf
Content-Disposition: attachment; filename="report_2026-0001.pdf"

[PDF binary data]
```

### Export Report (JSON)

```http
GET /reports/{report_id}/export/json
```

**Response:**
```json
{
  "id": 1,
  "case": {
    "numero_orden": "2026-0001",
    "title": "Investigation Title"
  },
  "title": "Final Investigation Report",
  "report_type": "FINAL",
  "content": {
    "introduction": "...",
    "methodology": "...",
    "findings": "...",
    "conclusions": "..."
  },
  "evidence_list": [...],
  "timeline_events": [...],
  "created_at": "2026-01-15T10:00:00Z"
}
```

---

## Graph API (Neo4j)

### Get Case Graph

```http
GET /graph/case/{case_id}
```

**Response:**
```json
{
  "nodes": [
    {
      "id": "person_1",
      "label": "Person",
      "properties": {
        "name": "John Doe",
        "dni": "12345678Z"
      }
    }
  ],
  "relationships": [
    {
      "id": "rel_1",
      "type": "FAMILIAR_DE",
      "from": "person_1",
      "to": "person_2",
      "properties": {
        "relationship": "spouse",
        "confidence": 0.95
      }
    }
  ]
}
```

### Create Node

```http
POST /graph/case/{case_id}/node/create

node_type=Person&
name=John+Doe&
dni=12345678Z&
phone=+34600000000&
email=john@example.com
```

### Create Relationship

```http
POST /graph/case/{case_id}/relationship/create

from_node_id=person_1&
to_node_id=person_2&
relationship_type=FAMILIAR_DE&
confidence=0.95&
notes=Confirmed+family+relationship
```

### Search Graph

```http
POST /graph/case/{case_id}/search

query=MATCH+(p:Person)-[r]->(n)+WHERE+p.name+CONTAINS+'John'+RETURN+p,r,n
```

---

## Admin API

### List Users

```http
GET /admin/users
```

**Response:**
```json
{
  "users": [
    {
      "id": 1,
      "email": "detective@example.com",
      "name": "Detective Name",
      "tip_number": "TIP-00001",
      "is_active": true,
      "roles": ["detective", "admin"]
    }
  ]
}
```

### Get Audit Logs

```http
GET /admin/audit-logs?action=LOGIN&user_id=1&page=1&per_page=50
```

**Response:**
```json
{
  "logs": [
    {
      "id": 1,
      "action": "LOGIN",
      "resource_type": "user",
      "user": {
        "id": 1,
        "name": "Detective Name"
      },
      "ip_address": "192.168.1.100",
      "timestamp": "2026-01-01T09:00:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "per_page": 50
}
```

### Export Audit Logs (CSV)

```http
GET /admin/audit-logs/export/csv
```

**Response:**
```http
200 OK
Content-Type: text/csv
Content-Disposition: attachment; filename="audit_logs.csv"

id,action,resource_type,user_id,ip_address,timestamp
1,LOGIN,user,1,192.168.1.100,2026-01-01T09:00:00Z
```

---

## Tasks API (Celery Monitoring)

### List Active Tasks

```http
GET /tasks/api/list
```

**Response:**
```json
{
  "success": true,
  "tasks": [
    {
      "id": "task-id-12345",
      "name": "app.tasks.evidence.process_evidence",
      "worker": "celery@worker1",
      "state": "ACTIVE",
      "args": [42, "/data/evidence.jpg"],
      "kwargs": {}
    }
  ]
}
```

### Get Task Status

```http
GET /tasks/api/status/{task_id}
```

**Response:**
```json
{
  "task_id": "task-id-12345",
  "state": "PROGRESS",
  "ready": false,
  "progress": 60,
  "current": 60,
  "total": 100,
  "status_message": "Encriptando archivo con AES-256-GCM..."
}
```

### Get Task Result

```http
GET /tasks/api/result/{task_id}
```

**Response:**
```json
{
  "success": true,
  "state": "SUCCESS",
  "result": {
    "evidence_id": 42,
    "sha256": "a1b2c3...",
    "sha512": "d4e5f6...",
    "encrypted_path": "/data/encrypted/evidence.enc"
  }
}
```

### Revoke Task

```http
POST /tasks/api/revoke/{task_id}
Content-Type: application/json

{
  "terminate": false
}
```

**Response:**
```json
{
  "success": true,
  "message": "Task task-id-12345 revoked",
  "terminated": false
}
```

### Get Worker Statistics

```http
GET /tasks/api/stats
```

**Response:**
```json
{
  "success": true,
  "total_workers": 2,
  "total_active_tasks": 3,
  "workers": [
    {
      "name": "celery@worker1",
      "pool": "prefork",
      "max_concurrency": 4,
      "active_tasks": 2
    }
  ]
}
```

---

## Plugin Execution API

### Execute DNI Validator

```http
POST /plugins/api/execute/dni_validator
Content-Type: application/json

{
  "dni": "12345678Z"
}
```

**Response:**
```json
{
  "valid": true,
  "dni": "12345678Z",
  "expected_letter": "Z",
  "actual_letter": "Z"
}
```

### Execute EXIF Extractor

```http
POST /plugins/api/execute/exif_extractor
Content-Type: application/json

{
  "evidence_id": 42
}
```

**Response:**
```json
{
  "success": true,
  "metadata": {
    "Make": "Canon",
    "Model": "EOS 5D Mark IV",
    "DateTime": "2026:01:01 14:30:25",
    "GPS": {
      "latitude": 40.4168,
      "longitude": -3.7038
    }
  }
}
```

---

## Error Responses

All API endpoints may return the following error responses:

### 400 Bad Request
```json
{
  "error": "Invalid input data",
  "details": {
    "field": "legitimacy_justification",
    "message": "Justification too short"
  }
}
```

### 401 Unauthorized
```json
{
  "error": "Authentication required",
  "message": "Please log in to access this resource"
}
```

### 403 Forbidden
```json
{
  "error": "Access denied",
  "message": "You do not have permission to access this resource"
}
```

### 404 Not Found
```json
{
  "error": "Resource not found",
  "message": "Case with ID 999 not found"
}
```

### 500 Internal Server Error
```json
{
  "error": "Internal server error",
  "message": "An unexpected error occurred"
}
```

---

## Rate Limiting

API endpoints are rate-limited to prevent abuse:

- **Authentication endpoints**: 5 requests per minute
- **General API**: 100 requests per minute
- **File uploads**: 10 requests per minute

Rate limit headers are included in responses:
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1704110400
```

---

## Legal Compliance

All API operations are audit-logged per Ley 5/2014 requirements. Logs include:
- User ID and name
- Action performed
- Resource accessed
- IP address
- Timestamp
- User agent

Audit logs are immutable and retained for legal purposes.

---

## Security Headers

All API responses include security headers:
```http
X-Content-Type-Options: nosniff
X-Frame-Options: SAMEORIGIN
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

---

## Pagination

List endpoints support pagination:

```http
GET /cases/?page=2&per_page=25
```

**Response includes pagination metadata:**
```json
{
  "cases": [...],
  "pagination": {
    "page": 2,
    "per_page": 25,
    "total": 150,
    "pages": 6,
    "has_next": true,
    "has_prev": true
  }
}
```

---

## Webhooks (Future Enhancement)

Webhook support for real-time notifications is planned for future releases.
