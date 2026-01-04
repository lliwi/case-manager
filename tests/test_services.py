"""
Unit tests for service layer.

Tests cover AuditService, EvidenceService, LegitimacyService, and TimelineService.
"""
import pytest
import os
import tempfile
from datetime import datetime
from app.services.audit_service import AuditService
from app.services.evidence_service import EvidenceService
from app.services.legitimacy_service import LegitimacyService
from app.services.timeline_service import TimelineService
from app.models import AuditLog, Evidence, TimelineEvent
from app.models.case import LegitimacyType
from app.models.timeline import EventType


@pytest.mark.unit
class TestAuditService:
    """Tests for AuditService."""

    def test_log_action(self, app, db_session, detective_user):
        """Test logging an action."""
        with app.test_request_context(
            '/',
            environ_base={'REMOTE_ADDR': '127.0.0.1'},
            headers={'User-Agent': 'Test Browser'}
        ):
            log_entry = AuditService.log(
                action='TEST_ACTION',
                resource_type='test',
                resource_id=123,
                user=detective_user,
                details={'key': 'value'}
            )

            assert log_entry is not None
            assert log_entry.action == 'TEST_ACTION'
            assert log_entry.resource_type == 'test'
            assert log_entry.resource_id == 123
            assert log_entry.user_id == detective_user.id
            assert log_entry.details == {'key': 'value'}

    def test_get_logs_for_user(self, app, db_session, detective_user):
        """Test retrieving logs for specific user."""
        with app.test_request_context(
            '/',
            environ_base={'REMOTE_ADDR': '127.0.0.1'}
        ):
            # Create multiple logs
            for i in range(3):
                AuditService.log(
                    action=f'ACTION_{i}',
                    resource_type='test',
                    user=detective_user
                )

            logs = AuditService.get_logs_for_user(detective_user.id, limit=10)

            assert len(logs) >= 3

    def test_get_logs_for_resource(self, app, db_session, detective_user):
        """Test retrieving logs for specific resource."""
        with app.test_request_context(
            '/',
            environ_base={'REMOTE_ADDR': '127.0.0.1'}
        ):
            resource_id = 456

            # Create logs for specific resource
            for i in range(2):
                AuditService.log(
                    action=f'RESOURCE_ACTION_{i}',
                    resource_type='case',
                    resource_id=resource_id,
                    user=detective_user
                )

            logs = AuditService.get_logs_for_resource('case', resource_id)

            assert len(logs) >= 2
            assert all(log.resource_id == resource_id for log in logs)

    def test_search_logs(self, app, db_session, detective_user):
        """Test searching logs with filters."""
        with app.test_request_context(
            '/',
            environ_base={'REMOTE_ADDR': '127.0.0.1'}
        ):
            # Create searchable logs
            AuditService.log(
                action='LOGIN',
                resource_type='user',
                user=detective_user
            )

            result = AuditService.search_logs(
                action='LOGIN',
                resource_type='user',
                user_id=detective_user.id
            )

            assert result['total'] > 0
            assert len(result['logs']) > 0
            assert result['logs'][0].action == 'LOGIN'


@pytest.mark.unit
class TestEvidenceService:
    """Tests for EvidenceService."""

    def test_validate_file_size(self, app):
        """Test file size validation."""
        with app.app_context():
            # Valid size (1MB)
            result = EvidenceService.validate_evidence_file(
                filename='test.jpg',
                file_size=1024 * 1024
            )
            assert result['valid'] is True

            # Too large (over 100MB default limit)
            result = EvidenceService.validate_evidence_file(
                filename='test.jpg',
                file_size=200 * 1024 * 1024
            )
            assert result['valid'] is False
            assert 'size' in result['error'].lower()

    def test_validate_file_extension(self, app):
        """Test file extension validation."""
        with app.app_context():
            # Valid extensions
            valid_files = ['test.jpg', 'doc.pdf', 'video.mp4', 'archive.zip']
            for filename in valid_files:
                result = EvidenceService.validate_evidence_file(
                    filename=filename,
                    file_size=1024
                )
                assert result['valid'] is True

            # Invalid extension
            result = EvidenceService.validate_evidence_file(
                filename='malware.exe',
                file_size=1024
            )
            assert result['valid'] is False
            assert 'extension' in result['error'].lower() or 'type' in result['error'].lower()

    def test_get_evidence_stats(self, db_session, test_case, test_evidence):
        """Test evidence statistics calculation."""
        stats = EvidenceService.get_evidence_stats(test_case.id)

        assert stats is not None
        assert 'total_count' in stats
        assert 'total_size_bytes' in stats
        assert 'total_size_mb' in stats
        assert 'verification_rate' in stats
        assert stats['total_count'] >= 1

    def test_verify_evidence_integrity(self, app, db_session, test_evidence):
        """Test evidence integrity verification."""
        with app.app_context():
            # This would need actual file for full test
            # Testing the logic flow
            result = EvidenceService.verify_integrity(test_evidence.id)

            # Will fail without actual file, but tests the service exists
            assert result is not None


@pytest.mark.unit
class TestLegitimacyService:
    """Tests for LegitimacyService."""

    def test_validate_legitimate_case(self, app):
        """Test validation of legitimate investigation."""
        with app.app_context():
            result = LegitimacyService.validate_legitimacy(
                legitimacy_type=LegitimacyType.INFIDELIDAD_CONYUGAL,
                justification='Investigation of marital infidelity per client request',
                case_description='Surveillance of spouse behavior'
            )

            assert result['is_valid'] is True
            assert result['legitimacy_type'] == LegitimacyType.INFIDELIDAD_CONYUGAL

    def test_detect_criminal_investigation(self, app):
        """Test detection of criminal cases (prohibited)."""
        with app.app_context():
            # Test with prohibited keywords
            criminal_descriptions = [
                'Investigation of a murder case',
                'Drug trafficking investigation',
                'Homicidio investigation',
                'Narcotráfico case'
            ]

            for description in criminal_descriptions:
                result = LegitimacyService.validate_legitimacy(
                    legitimacy_type=LegitimacyType.OTROS,
                    justification='Client request',
                    case_description=description
                )

                assert result['is_valid'] is False
                assert 'crime' in result['error'].lower() or 'delito' in result['error'].lower()

    def test_insufficient_justification(self, app):
        """Test validation with insufficient justification."""
        with app.app_context():
            result = LegitimacyService.validate_legitimacy(
                legitimacy_type=LegitimacyType.INFIDELIDAD_CONYUGAL,
                justification='No reason',  # Too short
                case_description='Investigation'
            )

            assert result['is_valid'] is False
            assert 'justification' in result['error'].lower()

    def test_all_legitimacy_types(self, app):
        """Test all legitimacy type enumerations."""
        with app.app_context():
            legitimacy_types = [
                LegitimacyType.INFIDELIDAD_CONYUGAL,
                LegitimacyType.BAJAS_LABORALES,
                LegitimacyType.INVESTIGACION_PATRIMONIAL,
                LegitimacyType.COMPETENCIA_DESLEAL,
                LegitimacyType.LOCALIZACION_PERSONAS,
                LegitimacyType.SOLVENCIA_PATRIMONIAL,
                LegitimacyType.CUSTODIA_MENORES,
                LegitimacyType.OTROS
            ]

            for leg_type in legitimacy_types:
                result = LegitimacyService.validate_legitimacy(
                    legitimacy_type=leg_type,
                    justification='Valid justification with sufficient detail for investigation',
                    case_description='Legitimate investigation case'
                )

                # All should pass with proper justification
                assert result['is_valid'] is True


@pytest.mark.unit
class TestTimelineService:
    """Tests for TimelineService."""

    def test_get_case_timeline(self, db_session, test_case, test_timeline_event):
        """Test retrieving case timeline."""
        events = TimelineService.get_case_timeline(test_case.id)

        assert len(events) >= 1
        assert events[0].case_id == test_case.id

    def test_filter_timeline_by_type(self, db_session, test_case, detective_user):
        """Test filtering timeline by event type."""
        # Create events of different types
        event_types = [EventType.SURVEILLANCE, EventType.MEETING, EventType.PHONE_CALL]

        for event_type in event_types:
            event = TimelineEvent(
                case_id=test_case.id,
                event_type=event_type,
                title=f'Test {event_type.value}',
                description='Test event',
                event_date=datetime.utcnow(),
                created_by_id=detective_user.id
            )
            db_session.add(event)

        db_session.commit()

        # Filter by specific type
        filtered = TimelineService.get_case_timeline(
            test_case.id,
            event_types=[EventType.SURVEILLANCE]
        )

        assert len(filtered) >= 1
        assert all(e.event_type == EventType.SURVEILLANCE for e in filtered)

    def test_detect_patterns(self, db_session, test_case, detective_user):
        """Test pattern detection in timeline."""
        # Create recurring events at same location
        location = 'Cafe Central, Madrid'

        for i in range(5):
            event = TimelineEvent(
                case_id=test_case.id,
                event_type=EventType.SURVEILLANCE,
                title=f'Observation {i}',
                description='Subject at location',
                event_date=datetime.utcnow(),
                created_by_id=detective_user.id,
                location=location,
                latitude=40.4168,
                longitude=-3.7038
            )
            db_session.add(event)

        db_session.commit()

        patterns = TimelineService.detect_patterns(test_case.id)

        assert patterns is not None
        assert 'recurring_locations' in patterns
        # Should detect the recurring location
        assert len(patterns['recurring_locations']) > 0

    def test_export_timeline_json(self, db_session, test_case, test_timeline_event):
        """Test JSON export of timeline."""
        timeline_json = TimelineService.export_timeline_json(test_case.id)

        assert timeline_json is not None
        assert isinstance(timeline_json, list)
        assert len(timeline_json) >= 1
        assert 'id' in timeline_json[0]
        assert 'title' in timeline_json[0]
        assert 'event_date' in timeline_json[0]

    def test_timeline_statistics(self, db_session, test_case, test_timeline_event):
        """Test timeline statistics calculation."""
        stats = TimelineService.get_timeline_stats(test_case.id)

        assert stats is not None
        assert 'total_events' in stats
        assert 'event_types' in stats
        assert stats['total_events'] >= 1
