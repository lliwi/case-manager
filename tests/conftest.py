"""
Pytest configuration and fixtures for Case Manager tests.

This module provides common fixtures and test utilities.
"""
import pytest
import os
import tempfile
from datetime import datetime, timedelta
from app import create_app
from app.extensions import db, bcrypt
from app.models import User, Role, Case, Evidence, ChainOfCustody, TimelineEvent, Report, AuditLog


@pytest.fixture(scope='session')
def app():
    """Create application for testing."""
    # Create temporary database
    db_fd, db_path = tempfile.mkstemp()

    # Override configuration for testing
    test_config = {
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'WTF_CSRF_ENABLED': False,
        'SECRET_KEY': 'test-secret-key',
        'NEO4J_URI': 'bolt://localhost:7687',
        'NEO4J_USER': 'neo4j',
        'NEO4J_PASSWORD': 'test_password',
        'CELERY_BROKER_URL': 'redis://localhost:6379/0',
        'CELERY_RESULT_BACKEND': 'redis://localhost:6379/1',
        'EVIDENCE_UPLOAD_FOLDER': tempfile.mkdtemp(),
        'MAX_CONTENT_LENGTH': 100 * 1024 * 1024,  # 100MB
    }

    # Create app
    app = create_app('testing')
    app.config.update(test_config)

    # Create application context
    with app.app_context():
        db.create_all()

        # Create default roles
        admin_role = Role(name='admin', description='Administrator')
        detective_role = Role(name='detective', description='Detective')
        analyst_role = Role(name='analyst', description='Analyst')

        db.session.add_all([admin_role, detective_role, analyst_role])
        db.session.commit()

        yield app

        # Cleanup
        db.session.remove()
        db.drop_all()

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture(scope='function')
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture(scope='function')
def runner(app):
    """Create CLI test runner."""
    return app.test_cli_runner()


@pytest.fixture(scope='function')
def db_session(app):
    """Create database session for testing."""
    with app.app_context():
        # Clear any existing data from previous tests
        db.session.rollback()

        yield db.session

        # Clean up: rollback any uncommitted changes
        db.session.rollback()
        # Clear the session
        db.session.remove()


@pytest.fixture
def admin_user(db_session):
    """Create admin user for testing."""
    # Clean up any existing user with this email
    existing = User.query.filter_by(email='admin@test.com').first()
    if existing:
        db_session.delete(existing)
        db_session.commit()

    admin_role = Role.query.filter_by(name='admin').first()
    detective_role = Role.query.filter_by(name='detective').first()

    user = User(
        email='admin@test.com',
        nombre='Test',
        apellidos='Admin',
        tip_number='TIP-TEST-001',
        is_active=True,
        mfa_enabled=False
    )
    user.set_password('TestPassword123!')
    user.roles.extend([admin_role, detective_role])

    db_session.add(user)
    db_session.commit()

    return user


@pytest.fixture
def detective_user(db_session):
    """Create detective user for testing."""
    # Clean up any existing user with this email
    existing = User.query.filter_by(email='detective@test.com').first()
    if existing:
        # Delete associated cases first (to avoid foreign key constraint)
        from app.models import Case
        Case.query.filter_by(detective_id=existing.id).delete()
        db_session.delete(existing)
        db_session.commit()

    detective_role = Role.query.filter_by(name='detective').first()

    user = User(
        email='detective@test.com',
        nombre='Test',
        apellidos='Detective',
        tip_number='TIP-TEST-002',
        is_active=True,
        mfa_enabled=False
    )
    user.set_password('TestPassword123!')
    user.roles.append(detective_role)

    db_session.add(user)
    db_session.commit()

    return user


@pytest.fixture
def analyst_user(db_session):
    """Create analyst user for testing."""
    # Clean up any existing user with this email
    existing = User.query.filter_by(email='analyst@test.com').first()
    if existing:
        db_session.delete(existing)
        db_session.commit()

    analyst_role = Role.query.filter_by(name='analyst').first()

    user = User(
        email='analyst@test.com',
        nombre='Test',
        apellidos='Analyst',
        tip_number='TIP-TEST-003',
        is_active=True,
        mfa_enabled=False
    )
    user.set_password('TestPassword123!')
    user.roles.append(analyst_role)

    db_session.add(user)
    db_session.commit()

    return user


@pytest.fixture
def test_case(db_session, detective_user):
    """Create test case."""
    from app.models.case import CaseStatus, CasePriority, LegitimacyType

    case = Case(
        numero_orden='2026-TEST-001',
        objeto_investigacion='Test investigation purpose',
        descripcion_detallada='Test case for unit testing',
        cliente_nombre='Test Client',
        cliente_dni_cif='12345678Z',
        cliente_email='test@client.com',
        sujeto_nombres='Test Subject',
        legitimacy_type=LegitimacyType.INFIDELIDAD_CONYUGAL,
        legitimacy_description='Test justification for investigation',
        detective_id=detective_user.id,
        detective_tip=detective_user.tip_number,
        status=CaseStatus.EN_INVESTIGACION,
        priority=CasePriority.MEDIA,
        confidencial=True
    )

    db_session.add(case)
    db_session.commit()

    return case


@pytest.fixture
def test_evidence(db_session, test_case, detective_user):
    """Create test evidence."""
    from app.models.evidence import EvidenceType

    evidence = Evidence(
        case_id=test_case.id,
        original_filename='test_evidence.jpg',
        stored_filename='test_evidence_encrypted.jpg',
        file_path='/data/evidence/test_evidence_encrypted.jpg',
        file_size=1024,
        mime_type='image/jpeg',
        evidence_type=EvidenceType.IMAGE,
        sha256_hash='a' * 64,
        sha512_hash='b' * 128,
        uploaded_by_id=detective_user.id,
        acquisition_date=datetime.utcnow(),
        is_encrypted=True,
        description='Test evidence for unit testing'
    )

    db_session.add(evidence)
    db_session.commit()

    return evidence


@pytest.fixture
def test_timeline_event(db_session, test_case, detective_user):
    """Create test timeline event."""
    from app.models.timeline import EventType

    event = TimelineEvent(
        case_id=test_case.id,
        event_type=EventType.SURVEILLANCE,
        title='Test Surveillance Event',
        description='Test event for unit testing',
        event_date=datetime.utcnow(),
        created_by_id=detective_user.id,
        location='Test Location',
        latitude=40.4168,  # Madrid coordinates
        longitude=-3.7038,
        subjects=['Test Subject'],
        tags=['test', 'surveillance'],
        confidence=0.95
    )

    db_session.add(event)
    db_session.commit()

    return event


@pytest.fixture
def test_report(db_session, test_case, detective_user):
    """Create test report."""
    from app.models.report import ReportType, ReportStatus

    report = Report(
        case_id=test_case.id,
        title='Test Investigation Report',
        report_type=ReportType.FINAL,
        status=ReportStatus.DRAFT,
        created_by_id=detective_user.id,
        content={
            'introduction': 'Test introduction',
            'methodology': 'Test methodology',
            'findings': 'Test findings',
            'conclusions': 'Test conclusions'
        },
        version=1
    )

    db_session.add(report)
    db_session.commit()

    return report


@pytest.fixture
def authenticated_client(client, admin_user):
    """Create authenticated test client."""
    with client.session_transaction() as session:
        session['_user_id'] = str(admin_user.id)
        session['_fresh'] = True

    return client


@pytest.fixture
def sample_image_file():
    """Create sample image file for testing."""
    from PIL import Image
    import io

    img = Image.new('RGB', (100, 100), color='red')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)

    return img_bytes


@pytest.fixture
def sample_pdf_file():
    """Create sample PDF file for testing."""
    import io

    # Simple PDF content
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000214 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
308
%%EOF
"""

    return io.BytesIO(pdf_content)


@pytest.fixture
def mock_celery_task(monkeypatch):
    """Mock Celery task execution."""
    class MockTask:
        def __init__(self, result=None, state='SUCCESS'):
            self.result = result or {'success': True}
            self.state = state
            self.id = 'test-task-id-12345'

        def delay(self, *args, **kwargs):
            return self

        def apply_async(self, *args, **kwargs):
            return self

        def ready(self):
            return True

        def successful(self):
            return self.state == 'SUCCESS'

        def failed(self):
            return self.state == 'FAILURE'

    return MockTask
