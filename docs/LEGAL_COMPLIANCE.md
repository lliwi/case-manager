# Legal Compliance Documentation - Ley 5/2014

## Overview

This document details how the Case Manager application complies with Spanish Law 5/2014 on Private Security (Ley de Seguridad Privada) and related regulations governing private investigation activities in Spain.

## Legal Framework

### Primary Legislation

**Ley 5/2014, de 4 de abril, de Seguridad Privada**
- Regulates private security activities in Spain
- Establishes requirements for private investigators
- Defines prohibited activities and legal boundaries

**Real Decreto 2364/1994**
- Reglamento de Seguridad Privada
- Detailed implementation regulations

### Key Principles

1. **Legality**: Investigations must have legitimate legal basis
2. **Proportionality**: Methods must be proportionate to objectives
3. **Confidentiality**: Professional secrecy obligation
4. **Transparency**: Proper identification and registration

## Article-by-Article Compliance

### Article 25: Libro-Registro (Case Registry)

**Legal Requirement:**
> Private investigators must maintain a chronological registry (libro-registro) of all investigations.

**Implementation:**
```
- Table: cases
- Fields:
  - numero_orden (sequential: 2026-0001, 2026-0002, ...)
  - fecha_apertura (opening date)
  - cliente (client information)
  - detective_tip (investigator TIP number)
  - legitimacy_type (investigation basis)
  - legitimacy_justification (detailed justification)
```

**Database Schema:**
```python
class Case(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_orden = db.Column(db.String(20), unique=True, nullable=False)  # Sequential number
    fecha_apertura = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    client_name = db.Column(db.String(200), nullable=False)
    client_contact = db.Column(db.String(200))
    detective_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    detective_tip = db.Column(db.String(20), nullable=False)  # Denormalized for audit
    legitimacy_type = db.Column(db.Enum(LegitimacyType), nullable=False)
    legitimacy_justification = db.Column(db.Text, nullable=False)
```

**Access:**
- Route: `/libro-registro/`
- Export: CSV and PDF formats
- Retention: Permanent (immutable records)

### Article 48: Interés Legítimo (Legitimate Interest)

**Legal Requirement:**
> Investigations must be justified by legitimate interest of the client.

**Implementation:**

Legitimacy types (enum `LegitimacyType`):
```python
class LegitimacyType(enum.Enum):
    INFIDELIDAD_CONYUGAL = "Infidelidad conyugal"          # Marital infidelity
    BAJAS_LABORALES = "Control de bajas laborales"          # Sick leave monitoring
    INVESTIGACION_PATRIMONIAL = "Investigación patrimonial" # Asset investigation
    COMPETENCIA_DESLEAL = "Competencia desleal"             # Unfair competition
    LOCALIZACION_PERSONAS = "Localización de personas"      # Missing persons
    SOLVENCIA_PATRIMONIAL = "Solvencia patrimonial"         # Credit worthiness
    CUSTODIA_MENORES = "Custodia de menores"                # Child custody
    OTROS = "Otros (justificar)"                             # Other (must justify)
```

**Validation Service:**
```python
# app/services/legitimacy_service.py
class LegitimacyService:
    @staticmethod
    def validate_legitimacy(legitimacy_type, justification, case_description):
        # Checks:
        # 1. Justification length (min 50 characters)
        # 2. No prohibited keywords (criminal activities)
        # 3. Legitimate interest documented
```

**Prohibited Investigations:**
```python
# app/services/legitimacy_service.py
CRIME_KEYWORDS = [
    'homicidio', 'asesinato', 'violación', 'secuestro',
    'narcotráfico', 'terrorismo', 'trata', 'extorsión',
    'murder', 'rape', 'kidnapping', 'drug trafficking'
]
```

### Article 49: Duty of Confidentiality

**Legal Requirement:**
> Private investigators have professional secrecy obligations similar to lawyers.

**Implementation:**

1. **Encryption at Rest:**
```python
# All evidence files encrypted with AES-256-GCM
from app.utils.crypto import encrypt_file, decrypt_file

encryption_key = os.getenv('EVIDENCE_ENCRYPTION_KEY')
encrypted_path = encrypt_file(file_path, encryption_key)
```

2. **HTTPS/TLS:**
```nginx
# Nginx configuration
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:...';
add_header Strict-Transport-Security "max-age=31536000" always;
```

3. **Access Control:**
```python
# RBAC decorators
@require_role('detective')
def view_case(case_id):
    case = Case.query.get_or_404(case_id)
    if case.detective_id != current_user.id and not current_user.is_admin():
        abort(403)  # Forbidden
```

4. **Confidentiality Flags:**
```python
# High-sensitivity cases
case.is_confidential = True  # Extra access restrictions
```

### Article 50: Crime Reporting Obligation

**Legal Requirement:**
> Private investigators must report crimes prosecutable ex officio (de oficio) to authorities.

**Implementation:**

**Crime Detection:**
```python
# app/services/legitimacy_service.py
def _contains_crime_keywords(text):
    """Detect references to serious crimes."""
    for keyword in CRIME_KEYWORDS:
        if keyword.lower() in text.lower():
            return True
    return False

# Used in case validation
if _contains_crime_keywords(case_description):
    return {
        'is_valid': False,
        'error': 'Cannot investigate crimes prosecutable ex officio'
    }
```

**Automated Detection:**
- Case creation validates description
- Rejects cases with criminal investigation indicators
- Audit logs all attempted prohibited investigations

### Article 52: Professional Identification

**Legal Requirement:**
> Private investigators must identify themselves with TIP (Tarjeta de Identidad Profesional).

**Implementation:**

**User Model:**
```python
class User(db.Model):
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    tip_number = db.Column(db.String(20), unique=True, nullable=False)  # Required
```

**Registration Validation:**
```python
# TIP format: TIP-XXXXX (5 digits)
import re

def validate_tip_number(tip):
    pattern = r'^TIP-\d{5}$'
    return bool(re.match(pattern, tip))
```

**Case Assignment:**
```python
# Detective TIP denormalized to case for audit trail
case.detective_id = current_user.id
case.detective_tip = current_user.tip_number
```

### Additional Compliance Requirements

#### UNE 71506: Forensic Methodology

**Chain of Custody Implementation:**

```python
class ChainOfCustody(db.Model):
    """Immutable audit trail for evidence handling."""

    id = db.Column(db.Integer, primary_key=True)
    evidence_id = db.Column(db.Integer, db.ForeignKey('evidence.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)  # UPLOADED, VIEWED, DOWNLOADED, VERIFIED
    performed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    performed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(256))
    notes = db.Column(db.Text)
    hash_verified = db.Column(db.Boolean, default=False)
    hash_match = db.Column(db.Boolean)
    sha256 = db.Column(db.String(64))
    sha512 = db.Column(db.String(128))
    extra_data = db.Column(JSON)

# Immutability enforced at database level:
# CREATE RULE chain_no_update AS ON UPDATE TO chain_of_custody DO INSTEAD NOTHING;
# CREATE RULE chain_no_delete AS ON DELETE TO chain_of_custody DO INSTEAD NOTHING;
```

**Evidence Integrity:**
```python
# Automatic hash calculation on upload
hashes = calculate_file_hashes(file_path)
evidence.sha256_hash = hashes['sha256']
evidence.sha512_hash = hashes['sha512']

# Verification before access
current_hashes = calculate_file_hashes(file_path)
if current_hashes['sha256'] != evidence.sha256_hash:
    log_integrity_failure(evidence.id)
```

#### GDPR/LOPDGDD Compliance

**Data Protection Requirements:**

1. **Legal Basis:** Legitimate interest (Art. 6.1.f GDPR)
2. **Data Minimization:** Only necessary data collected
3. **Purpose Limitation:** Data used only for investigation
4. **Storage Limitation:** Retention policies implemented
5. **Integrity and Confidentiality:** Encryption + access control

**Privacy Implementation:**
```python
# Data retention policy
RETENTION_PERIOD_YEARS = 10  # Legal requirement in Spain

# Automatic anonymization after retention period
@celery.task
def anonymize_expired_cases():
    cutoff_date = datetime.utcnow() - timedelta(days=RETENTION_PERIOD_YEARS * 365)
    expired_cases = Case.query.filter(
        Case.fecha_cierre < cutoff_date,
        Case.status == CaseStatus.ARCHIVADO
    ).all()

    for case in expired_cases:
        case.client_name = "ANONYMIZED"
        case.client_contact = "ANONYMIZED"
        case.subject_name = "ANONYMIZED"
        # Preserve case number and dates for legal audit
```

#### Audit Log Requirements

**Comprehensive Logging:**

```python
class AuditLog(db.Model):
    """Immutable audit log for all system actions."""

    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(50), nullable=False, index=True)
    resource_type = db.Column(db.String(50), index=True)
    resource_id = db.Column(db.Integer)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(256))
    details = db.Column(JSON)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
```

**Logged Actions:**
- LOGIN / LOGOUT
- CASE_CREATED / CASE_VIEWED / CASE_CLOSED
- EVIDENCE_UPLOADED / EVIDENCE_DOWNLOADED / EVIDENCE_VERIFIED
- REPORT_GENERATED / REPORT_SIGNED
- TIMELINE_EVENT_CREATED
- GRAPH_NODE_CREATED / GRAPH_RELATIONSHIP_CREATED
- ADMIN actions (USER_CREATED, ROLE_MODIFIED, etc.)

**Retention:** Permanent (never deleted)

**Export Capability:**
```python
# CSV export for judicial presentation
@admin_bp.route('/audit-logs/export/csv')
@require_role('admin')
def export_audit_logs_csv():
    # Exports all logs with digital signature
```

## GPS Tracking Prohibition

**Legal Basis:** Sentencia del Tribunal Supremo 278/2021

**Prohibition:**
> Automatic GPS tracking of vehicles without owner consent violates privacy rights (Art. 18 Constitución Española).

**System Implementation:**
- GPS tracking features disabled by default
- Manual location logging allowed (visual observation)
- Timestamp + location + notes (human-entered)
- No automated vehicle tracking
- Warnings in UI about legal restrictions

```python
# app/templates/timeline/create.html
<div class="alert alert-warning">
    <strong>⚠️ Advertencia Legal:</strong>
    La colocación de dispositivos GPS en vehículos sin consentimiento
    del propietario vulnera el derecho a la intimidad (STS 278/2021).
    Solo registre ubicaciones observadas manualmente.
</div>
```

## Report Generation Compliance

**Judicial Admissibility Requirements:**

Reports must include:

1. **Identification Section:**
   - Investigator name and TIP
   - Agency name and registration
   - Client identification (with consent)

2. **Objective:**
   - Clear statement of investigation purpose
   - Legitimacy basis documented

3. **Methodology:**
   - Technical methods used
   - Tools and equipment
   - Evidence collection procedures
   - Chain of custody maintenance

4. **Chronological Narrative:**
   - Timeline of events
   - Cross-referenced to evidence items
   - Timestamps with time zone

5. **Evidence Annexes:**
   - Digital signatures (SHA-256/SHA-512)
   - Hash verification results
   - Chain of custody logs
   - Metadata preservation

6. **Conclusions:**
   - Factual findings only
   - No legal interpretations (reserved for judges)

7. **Digital Signature:**
   - PDF signed with investigator's digital certificate
   - Timestamp from trusted authority

```python
# app/services/report_service.py
class ReportService:
    @staticmethod
    def generate_pdf_report(report_id):
        # Includes all required sections
        # Signs with SHA-256/SHA-512
        # Immutable once signed
```

## Compliance Checklist

### Before Deployment

- [ ] TIP number validation active
- [ ] Libro-registro accessible with export
- [ ] Legitimacy validation enforced
- [ ] Crime keyword detection enabled
- [ ] Confidentiality flags implemented
- [ ] Encryption at rest configured (AES-256)
- [ ] HTTPS/TLS enforced
- [ ] Audit logging comprehensive
- [ ] Chain of custody immutable
- [ ] Evidence hash verification automatic
- [ ] GPS tracking warnings displayed
- [ ] Report format compliant
- [ ] Data retention policy active
- [ ] GDPR privacy notice available

### Ongoing Compliance

- [ ] Regular security audits
- [ ] Audit log review monthly
- [ ] Backup verification weekly
- [ ] Encryption key rotation annually
- [ ] Staff training on legal requirements
- [ ] Incident response plan tested
- [ ] DPO designated and contactable
- [ ] Legal counsel review quarterly

## Legal Disclaimers

### User Responsibility

Users of this system are responsible for:
- Ensuring investigations have legitimate basis
- Respecting subject privacy rights
- Reporting crimes as legally required
- Maintaining professional secrecy
- Complying with court orders

### System Limitations

This system:
- Assists in legal compliance but does not guarantee it
- Requires proper configuration and use
- Must be operated by licensed private investigators
- Should be reviewed by legal counsel

### Liability

The developers and distributors of this software:
- Provide tools for legal compliance assistance
- Do not assume liability for user misuse
- Recommend consulting legal counsel
- Encourage ethical investigation practices

## References

### Legal Texts

- **Ley 5/2014**: https://www.boe.es/buscar/act.php?id=BOE-A-2014-3626
- **Real Decreto 2364/1994**: https://www.boe.es/buscar/act.php?id=BOE-A-1994-28643
- **GDPR**: https://eur-lex.europa.eu/eli/reg/2016/679/oj
- **LOPDGDD**: https://www.boe.es/buscar/act.php?id=BOE-A-2018-16673

### Standards

- **UNE 71506**: Metodología de análisis forense de evidencias electrónicas
- **ISO 27001**: Information security management
- **ISO 27037**: Guidelines for identification, collection, acquisition and preservation of digital evidence

### Jurisprudence

- **STS 278/2021**: GPS tracking privacy violation
- **STS 573/2017**: Chain of custody requirements
- **STC 70/2002**: Proportionality in private investigations

## Contact

For legal compliance questions:
- **DPO**: dpo@youragency.com
- **Legal Counsel**: legal@youragency.com
- **Technical Support**: support@youragency.com

---

**Last Updated:** January 2026
**Review Frequency:** Quarterly
**Next Review:** April 2026
