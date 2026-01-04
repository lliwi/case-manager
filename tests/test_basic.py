"""
Basic tests to demonstrate testing infrastructure works.
"""
import pytest
from app import create_app
from app.extensions import db
from app.models import User, Role, Case, Evidence, AuditLog
from app.models.case import CaseStatus, LegitimacyType
from datetime import datetime


@pytest.mark.unit
class TestAppCreation:
    """Test basic app creation and configuration."""

    def test_app_creation(self):
        """Test app can be created in testing mode."""
        app = create_app('testing')
        assert app is not None
        assert app.config['TESTING'] is True

    def test_app_has_config(self):
        """Test app has required configuration."""
        app = create_app('testing')
        assert 'SECRET_KEY' in app.config
        assert 'SQLALCHEMY_DATABASE_URI' in app.config


@pytest.mark.unit
class TestDatabaseModels:
    """Test database models can be created."""

    def test_user_model_creation(self, app, db_session):
        """Test User model can be created."""
        user = User(
            email='test@example.com',
            nombre='Test',
            apellidos='User',
            tip_number='TIP-12345',
            is_active=True
        )
        user.password_hash = 'hashed_password'

        db_session.add(user)
        db_session.commit()

        assert user.id is not None
        assert user.email == 'test@example.com'

    def test_role_model_creation(self, app, db_session):
        """Test Role model can be created."""
        role = Role(
            name='test_role',
            description='Test role description'
        )

        db_session.add(role)
        db_session.commit()

        assert role.id is not None
        assert role.name == 'test_role'

    def test_case_model_creation(self, app, db_session, detective_user):
        """Test Case model can be created."""
        case = Case(
            numero_orden='2026-TEST-001',
            objeto_investigacion='Test investigation purpose',
            descripcion_detallada='Test detailed description',
            cliente_nombre='Test Client',
            cliente_dni_cif='12345678Z',
            cliente_email='client@test.com',
            sujeto_nombres='Test Subject',
            legitimacy_type=LegitimacyType.OTROS,
            legitimacy_description='Test justification with sufficient detail for the investigation',
            detective_id=detective_user.id,
            detective_tip=detective_user.tip_number,
            status=CaseStatus.EN_INVESTIGACION
        )

        db_session.add(case)
        db_session.commit()

        assert case.id is not None
        assert case.numero_orden == '2026-TEST-001'

    def test_audit_log_creation(self, app, db_session, detective_user):
        """Test AuditLog can be created."""
        log = AuditLog(
            action='TEST_ACTION',
            resource_type='test',
            resource_id=1,
            user_id=detective_user.id,
            user_email=detective_user.email,
            ip_address='127.0.0.1',
            timestamp=datetime.utcnow()
        )

        db_session.add(log)
        db_session.commit()

        assert log.id is not None
        assert log.action == 'TEST_ACTION'
        assert log.user_email == detective_user.email


@pytest.mark.unit
class TestUserPassword:
    """Test user password functionality."""

    def test_password_setter_method(self, app, db_session):
        """Test password setter method sets hash."""
        user = User(
            email='test@example.com',
            nombre='Test',
            apellidos='User',
            tip_number='TIP-12345'
        )
        user.set_password('SecurePassword123!')

        assert user.password_hash is not None
        assert user.password_hash != 'SecurePassword123!'
        assert user.password_hash.startswith('$2b$')

    def test_password_verification(self, app, db_session):
        """Test password can be verified."""
        user = User(
            email='test@example.com',
            nombre='Test',
            apellidos='User',
            tip_number='TIP-12345'
        )
        password = 'SecurePassword123!'
        user.set_password(password)

        assert user.check_password(password) is True
        assert user.check_password('WrongPassword') is False


@pytest.mark.unit
class TestUserRoles:
    """Test user-role relationship."""

    def test_user_can_have_roles(self, app, db_session):
        """Test user can be assigned roles."""
        user = User(
            email='test-roles@example.com',
            nombre='Test',
            apellidos='User',
            tip_number='TIP-99999'
        )
        user.set_password('TestPassword123!')

        # Use existing role instead of creating new one
        role = Role.query.filter_by(name='detective').first()

        user.roles.append(role)
        db_session.add(user)
        db_session.commit()

        assert len(user.roles) == 1
        assert role in user.roles

    def test_has_role_method(self, app, db_session):
        """Test has_role method works."""
        user = User(
            email='test-hasrole@example.com',
            nombre='Test',
            apellidos='User',
            tip_number='TIP-88888'
        )
        user.set_password('TestPassword123!')

        # Use existing roles instead of creating new ones
        detective_role = Role.query.filter_by(name='detective').first()
        admin_role = Role.query.filter_by(name='admin').first()

        user.roles.append(detective_role)
        db_session.add(user)
        db_session.commit()

        assert user.has_role('detective') is True
        assert user.has_role('admin') is False
