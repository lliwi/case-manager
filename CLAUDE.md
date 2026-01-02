# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Flask-based case management system for private investigators (detectives privados) in Spain, designed to comply with Spanish Law 5/2014 on Private Security. The application provides forensically sound evidence management, relationship analysis, and timeline visualization for investigative work.

## Architecture

### Technology Stack

- **Web Framework**: Flask (Application Factory pattern with Blueprints)
- **Databases**:
  - PostgreSQL: Structured data (case registry, user profiles, audit logs)
  - Neo4j: Relationship graphs between entities (people, vehicles, locations, evidence)
- **Task Queue**: Celery with Redis broker for asynchronous processing
- **Containerization**: Docker with docker-compose for multi-service orchestration
- **Monitoring**: Flower for Celery task monitoring

### Microservices Architecture

The system is designed as a multi-container ecosystem:

1. **Flask Web Container**: User interface and REST API
2. **PostgreSQL**: Transactional data requiring ACID compliance
3. **Neo4j**: Graph database for entity relationships and link analysis
4. **Redis**: Message broker for async tasks
5. **Celery Workers**: Process-intensive operations (OSINT queries, metadata extraction, forensic analysis)
6. **Flower**: Real-time task queue monitoring

All services communicate through an isolated internal Docker network with encrypted connections.

## Core Features

### 1. Legal Compliance (Ley 5/2014)

- **Libro-registro (Case Registry)**: Mandatory chronological log of all investigations with immutable audit trails
- **Legitimacy Validation**: Each case must document the client's legitimate interest before accepting evidence
- **Professional Identification**: Detective must provide their TIP (Tarjeta de Identidad Profesional) number
- **Duty of Confidentiality**: End-to-end encryption for data at rest and in transit (AES-256, TLS)
- **Crime Reporting**: System must detect and block investigations into crimes prosecutable ex officio

### 2. Evidence Management (Forensic Standard UNE 71506)

- **Chain of Custody**: Immutable audit trail for every evidence interaction (who, when, from where)
- **Hash Verification**: Automatic calculation of SHA-256/SHA-512 hashes on upload with trusted timestamps
- **Non-destructive Analysis**: Work only on copies; original evidence remains unmodified
- **Metadata Preservation**: Capture acquisition context (device state, tools used, incident location)

Evidence lifecycle phases:
1. Preservation (encrypted storage, initial hash)
2. Acquisition (cloning documentation, device state)
3. Documentation (immutable audit trail)
4. Analysis (plugin-based processing)
5. Presentation (legally formatted reports)

### 3. Relationship Graph (Neo4j)

Graph database models investigations as property graphs:

- **Nodes**: Person, Company, Phone, Email, Social_Profile, Vehicle, Address, Bank_Account, Evidence
- **Relationships**: FAMILIAR_DE, SOCIO_DE, UTILIZA_VEHICULO, VISTO_EN, VINCULADO_A_EVIDENCIA, PUBLICADO_DESDE

Use Cypher queries for traversal analysis to discover indirect connections (e.g., two subjects sharing Wi-Fi access points or frequenting the same location).

### 4. Timeline Visualization

Interactive chronological visualization using Vis.js or Plotly:
- Multi-subject parallel timelines
- Pattern detection (routines, geographic recurrences)
- Multimedia synchronization (video/photo playback from timeline points)
- Cross-reference to supporting evidence

### 5. Plugin System

Modular architecture using `pluggy` or `stevedore` for dynamic loading:

**Plugin Categories**:
- **Forensic (Images)**: Pillow, ExifTool → GPS, camera model, original date extraction
- **Forensic (Documents)**: PyPDF2, OleFileIO_PL → authorship, edit history, XMP metadata
- **OSINT (Identity)**: python-stdnum, spanish-dni → DNI/NIE/CIF validation (modulo 23 algorithm)
- **OSINT (Social)**: Holehe, Sherlock → email-to-profile mapping, username searches
- **Multimedia**: Mutagen → audio/video metadata extraction

Plugins register at startup via entry points and execute in Celery workers for heavy processing.

## Security Requirements

### Container Hardening

- Database containers: No exposed ports; accessible only via internal Docker network
- Minimal base images: Alpine or Debian Slim
- Non-root execution: All containers run with unprivileged users
- Regular CVE scanning of images

### Authentication & Authorization

- Multi-factor authentication (MFA) for detectives
- Role-based access control (RBAC)
- Certificate-based authentication preferred
- Zero-knowledge architecture for sensitive evidence when possible

### Encryption

- **At Rest**: AES-256 encryption on Docker volumes mapped to encrypted host partitions
- **In Transit**: TLS for all service-to-service communication
- **Evidence Storage**: Full disk encryption on `/data` volumes

### Audit Logging

Centralized, write-protected logs capturing every action:
- Case opening/closing
- Evidence uploads/views/exports
- User authentication events
- System configuration changes

Logs must be immutable and suitable for judicial audit.

## Legal & Ethical Constraints

### GPS Tracking Prohibition

Per Spanish jurisprudence (STS 278/2021), automatic GPS tracking of non-consenting individuals violates privacy rights. System must:
- Prioritize manual location logging based on visual observation
- Require justification for any surveillance measure (proportionality and necessity)
- Never automate intrusive tracking that could invalidate investigations

### Identity Validation

DNI/NIE validation algorithm (modulo 23):
```
Given 8-digit number N:
Index I = N mod 23
Letter = "TRWAGMYFPDXBNJZSQVHLCKE"[I]
```

System validates in real-time to detect false identities or typographical errors.

## Report Generation

Final investigative reports must be legally admissible and follow this structure:

1. **Investigator Identification**: Name, TIP number, agency
2. **Client & Legitimacy**: Documented legitimate interest
3. **Investigation Objective**: Clear description of facts to clarify
4. **Methodology**: Technical details, hashes of evidence files, tools used
5. **Chronological Narrative**: Timeline-backed, cross-referenced to evidence
6. **Technical Annexes**: Evidence list with timestamps and digital signatures

Reports export as PDF with integrity metadata for judicial ratification. Language must be comprehensible to non-technical judges.

## Development Principles

1. **Evidence Integrity First**: Never modify original files; maintain cryptographic hashes
2. **Legal Compliance**: Every feature must respect Ley 5/2014 constraints
3. **Forensic Soundness**: Follow UNE 71506 methodology for all evidence handling
4. **Modular Extensions**: Use plugin architecture for new capabilities
5. **Reproducibility**: Docker ensures consistent environments for forensic defensibility
6. **Audit Everything**: Immutable logs for judicial transparency

## Reference Documentation

See [Requisitos App Investigación Privada Flask.md](Requisitos App Investigación Privada Flask.md) for complete technical and legal requirements (in Spanish).
