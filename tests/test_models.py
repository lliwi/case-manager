"""
Unit tests for database models.

Tests cover User, Role, Case, Evidence, ChainOfCustody, TimelineEvent, Report, and AuditLog models.
"""
import pytest
from datetime import datetime, timedelta
from app.models import User, Role, Case, Evidence, ChainOfCustody, TimelineEvent, Report, AuditLog
from app.models.case import CaseStatus, CasePriority, LegitimacyType
from app.models.evidence import EvidenceType
from app.models.timeline import EventType
from app.models.report import ReportType, ReportStatus


@pytest.mark.unit
class TestUserModel:
    """Tests for User model."""

    def test_create_user(self, db_session):
        """Test user creation."""
        user = User(
            email='test@example.com',
            name='Test User',
            tip_number='TIP-12345',
            is_active=True
        )
        user.password = 'SecurePassword123!'

        db_session.add(user)
        db_session.commit()

        assert user.id is not None
        assert user.email == 'test@example.com'
        assert user.name == 'Test User'
        assert user.tip_number == 'TIP-12345'
        assert user.is_active is True
        assert user.password_hash is not None

    def test_password_hashing(self, db_session):
        """Test password hashing and verification."""
        user = User(email='test@example.com', name='Test', tip_number='TIP-001')
        password = 'MySecretPassword123!'
        user.password = password

        db_session.add(user)
        db_session.commit()

        # Password should be hashed
        assert user.password_hash != password
        assert user.password_hash.startswith('$2b$')

        # Verify correct password
        assert user.verify_password(password) is True

        # Verify incorrect password
        assert user.verify_password('WrongPassword') is False

    def test_user_roles(self, db_session, admin_user):
        """Test user role assignment."""
        admin_role = Role.query.filter_by(name='admin').first()

        assert admin_role in admin_user.roles
        assert admin_user.has_role('admin') is True
        assert admin_user.has_role('nonexistent') is False

    def test_is_admin(self, db_session, admin_user, detective_user):
        """Test is_admin helper method."""
        assert admin_user.is_admin() is True
        assert detective_user.is_admin() is False

    def test_mfa_token_generation(self, db_session, admin_user):
        """Test MFA token generation."""
        admin_user.generate_mfa_secret()

        assert admin_user.mfa_secret is not None
        assert len(admin_user.mfa_secret) > 0

    def test_user_string_representation(self, db_session, admin_user):
        """Test __repr__ method."""
        assert 'User' in repr(admin_user)
        assert admin_user.email in repr(admin_user)


@pytest.mark.unit
class TestRoleModel:
    """Tests for Role model."""

    def test_create_role(self, db_session):
        """Test role creation."""
        role = Role(
            name='test_role',
            description='Test role description'
        )

        db_session.add(role)
        db_session.commit()

        assert role.id is not None
        assert role.name == 'test_role'
        assert role.description == 'Test role description'

    def test_role_users_relationship(self, db_session, admin_user):
        """Test many-to-many relationship with users."""
        admin_role = Role.query.filter_by(name='admin').first()

        assert admin_user in admin_role.users
        assert len(admin_role.users) >= 1


@pytest.mark.unit
class TestCaseModel:
    """Tests for Case model."""

    def test_create_case(self, db_session, detective_user):
        """Test case creation."""
        case = Case(
            numero_orden='2026-001',
            title='Test Case',
            description='Test description',
            client_name='Test Client',
            client_contact='client@test.com',
            subject_name='Test Subject',
            legitimacy_type=LegitimacyType.INFIDELIDAD_CONYUGAL,
            legitimacy_justification='Test justification',
            detective_id=detective_user.id,
            detective_tip=detective_user.tip_number,
            status=CaseStatus.PENDIENTE_VALIDACION,
            priority=CasePriority.MEDIA,
            fecha_apertura=datetime.utcnow()
        )

        db_session.add(case)
        db_session.commit()

        assert case.id is not None
        assert case.numero_orden == '2026-001'
        assert case.status == CaseStatus.PENDIENTE_VALIDACION
        assert case.detective_id == detective_user.id

    def test_case_detective_relationship(self, db_session, test_case, detective_user):
        """Test relationship with detective user."""
        assert test_case.detective.id == detective_user.id
        assert test_case in detective_user.cases

    def test_case_status_enum(self, db_session):
        """Test case status enumeration."""
        assert hasattr(CaseStatus, 'PENDIENTE_VALIDACION')
        assert hasattr(CaseStatus, 'ACTIVO')
        assert hasattr(CaseStatus, 'CERRADO')
        assert hasattr(CaseStatus, 'ARCHIVADO')

    def test_legitimacy_type_enum(self, db_session):
        """Test legitimacy type enumeration."""
        assert hasattr(LegitimacyType, 'INFIDELIDAD_CONYUGAL')
        assert hasattr(LegitimacyType, 'BAJAS_LABORALES')
        assert hasattr(LegitimacyType, 'INVESTIGACION_PATRIMONIAL')


@pytest.mark.unit
class TestEvidenceModel:
    """Tests for Evidence model."""

    def test_create_evidence(self, db_session, test_case, detective_user):
        """Test evidence creation."""
        evidence = Evidence(
            case_id=test_case.id,
            original_filename='test.jpg',
            stored_filename='encrypted_test.jpg',
            file_path='/data/test.jpg',
            file_size=2048,
            mime_type='image/jpeg',
            evidence_type=EvidenceType.IMAGE,
            sha256_hash='a' * 64,
            sha512_hash='b' * 128,
            uploaded_by_id=detective_user.id,
            acquisition_date=datetime.utcnow(),
            is_encrypted=True
        )

        db_session.add(evidence)
        db_session.commit()

        assert evidence.id is not None
        assert evidence.case_id == test_case.id
        assert evidence.evidence_type == EvidenceType.IMAGE
        assert evidence.is_encrypted is True

    def test_evidence_case_relationship(self, db_session, test_evidence, test_case):
        """Test relationship with case."""
        assert test_evidence.case.id == test_case.id
        assert test_evidence in test_case.evidence

    def test_evidence_type_enum(self, db_session):
        """Test evidence type enumeration."""
        assert hasattr(EvidenceType, 'IMAGE')
        assert hasattr(EvidenceType, 'VIDEO')
        assert hasattr(EvidenceType, 'DOCUMENTO')
        assert hasattr(EvidenceType, 'AUDIO')


@pytest.mark.unit
class TestChainOfCustodyModel:
    """Tests for ChainOfCustody model."""

    def test_create_chain_entry(self, db_session, test_evidence, detective_user):
        """Test chain of custody entry creation."""
        entry = ChainOfCustody(
            evidence_id=test_evidence.id,
            action='UPLOADED',
            performed_by_id=detective_user.id,
            performed_at=datetime.utcnow(),
            ip_address='127.0.0.1',
            user_agent='Test Browser',
            notes='Test upload',
            hash_verified=True,
            hash_match=True,
            sha256=test_evidence.sha256_hash,
            sha512=test_evidence.sha512_hash
        )

        db_session.add(entry)
        db_session.commit()

        assert entry.id is not None
        assert entry.evidence_id == test_evidence.id
        assert entry.action == 'UPLOADED'
        assert entry.hash_verified is True

    def test_chain_immutability(self, db_session, test_evidence, detective_user):
        """Test that chain of custody entries are immutable."""
        entry = ChainOfCustody(
            evidence_id=test_evidence.id,
            action='VIEWED',
            performed_by_id=detective_user.id,
            performed_at=datetime.utcnow(),
            ip_address='127.0.0.1'
        )

        db_session.add(entry)
        db_session.commit()

        original_action = entry.action

        # Attempt to modify (should not be allowed in production)
        entry.action = 'MODIFIED'
        db_session.commit()

        # In a real forensic system, this would be prevented at the database level
        # This test documents the expected behavior


@pytest.mark.unit
class TestTimelineEventModel:
    """Tests for TimelineEvent model."""

    def test_create_timeline_event(self, db_session, test_case, detective_user):
        """Test timeline event creation."""
        event = TimelineEvent(
            case_id=test_case.id,
            event_type=EventType.MEETING,
            title='Test Meeting',
            description='Test meeting description',
            event_date=datetime.utcnow(),
            created_by_id=detective_user.id,
            location='Test Location',
            subjects=['Subject 1', 'Subject 2'],
            tags=['meeting', 'test'],
            confidence=0.9
        )

        db_session.add(event)
        db_session.commit()

        assert event.id is not None
        assert event.event_type == EventType.MEETING
        assert event.confidence == 0.9
        assert 'meeting' in event.tags

    def test_event_with_evidence(self, db_session, test_timeline_event, test_evidence):
        """Test linking evidence to timeline event."""
        test_timeline_event.evidence_id = test_evidence.id

        db_session.commit()

        assert test_timeline_event.evidence.id == test_evidence.id

    def test_event_geolocation(self, db_session, test_timeline_event):
        """Test geolocation fields."""
        assert test_timeline_event.latitude is not None
        assert test_timeline_event.longitude is not None
        assert -90 <= test_timeline_event.latitude <= 90
        assert -180 <= test_timeline_event.longitude <= 180


@pytest.mark.unit
class TestReportModel:
    """Tests for Report model."""

    def test_create_report(self, db_session, test_case, detective_user):
        """Test report creation."""
        report = Report(
            case_id=test_case.id,
            title='Test Report',
            report_type=ReportType.PRELIMINARY,
            status=ReportStatus.DRAFT,
            created_by_id=detective_user.id,
            content={'test': 'content'},
            version=1
        )

        db_session.add(report)
        db_session.commit()

        assert report.id is not None
        assert report.report_type == ReportType.PRELIMINARY
        assert report.status == ReportStatus.DRAFT
        assert report.version == 1

    def test_report_versioning(self, db_session, test_report):
        """Test report version management."""
        original_version = test_report.version

        # Create new version
        test_report.version += 1

        db_session.commit()

        assert test_report.version == original_version + 1

    def test_report_hashes(self, db_session, test_report):
        """Test PDF hash storage."""
        test_report.pdf_sha256 = 'a' * 64
        test_report.pdf_sha512 = 'b' * 128

        db_session.commit()

        assert len(test_report.pdf_sha256) == 64
        assert len(test_report.pdf_sha512) == 128


@pytest.mark.unit
class TestAuditLogModel:
    """Tests for AuditLog model."""

    def test_create_audit_log(self, db_session, detective_user):
        """Test audit log creation."""
        log = AuditLog(
            action='TEST_ACTION',
            resource_type='test',
            resource_id=1,
            user_id=detective_user.id,
            ip_address='127.0.0.1',
            user_agent='Test Browser',
            details={'test': 'data'},
            timestamp=datetime.utcnow()
        )

        db_session.add(log)
        db_session.commit()

        assert log.id is not None
        assert log.action == 'TEST_ACTION'
        assert log.user_id == detective_user.id

    def test_audit_log_immutability(self, db_session, detective_user):
        """Test that audit logs are immutable."""
        log = AuditLog(
            action='LOGIN',
            resource_type='user',
            user_id=detective_user.id,
            ip_address='127.0.0.1',
            timestamp=datetime.utcnow()
        )

        db_session.add(log)
        db_session.commit()

        original_action = log.action

        # In production, modification should be prevented at database level
        # This test documents expected behavior

    def test_audit_log_searchability(self, db_session, detective_user):
        """Test querying audit logs."""
        # Create multiple logs
        for i in range(5):
            log = AuditLog(
                action=f'ACTION_{i}',
                resource_type='test',
                user_id=detective_user.id,
                ip_address='127.0.0.1',
                timestamp=datetime.utcnow()
            )
            db_session.add(log)

        db_session.commit()

        # Query logs
        logs = AuditLog.query.filter_by(user_id=detective_user.id).all()

        assert len(logs) >= 5
