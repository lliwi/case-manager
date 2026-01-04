"""
Timeline service for aggregating and managing case timeline events.
"""
from datetime import datetime, timedelta
from sqlalchemy import and_, or_
from app.extensions import db
from app.models.timeline import TimelineEvent, EventType
from app.models.evidence import Evidence
from app.models.case import Case


class TimelineService:
    """Service for managing timeline events."""

    @staticmethod
    def get_case_timeline(case_id, include_deleted=False):
        """
        Get all timeline events for a case.

        Args:
            case_id: Case ID
            include_deleted: Include soft-deleted events

        Returns:
            list: Timeline events ordered by event_date
        """
        query = TimelineEvent.query.filter_by(case_id=case_id)

        if not include_deleted:
            query = query.filter_by(is_deleted=False)

        return query.order_by(TimelineEvent.event_date.asc()).all()

    @staticmethod
    def get_filtered_timeline(case_id, filters=None):
        """
        Get filtered timeline events.

        Args:
            case_id: Case ID
            filters: dict with optional keys:
                - event_types: list of EventType enums
                - date_from: datetime
                - date_to: datetime
                - subjects: list of subject names
                - tags: list of tags
                - confidence_levels: list of confidence levels
                - has_evidence: bool

        Returns:
            list: Filtered timeline events
        """
        query = TimelineEvent.query.filter_by(case_id=case_id, is_deleted=False)

        if not filters:
            return query.order_by(TimelineEvent.event_date.asc()).all()

        # Filter by event types
        if filters.get('event_types'):
            query = query.filter(TimelineEvent.event_type.in_(filters['event_types']))

        # Filter by date range
        if filters.get('date_from'):
            query = query.filter(TimelineEvent.event_date >= filters['date_from'])
        if filters.get('date_to'):
            query = query.filter(TimelineEvent.event_date <= filters['date_to'])

        # Filter by subjects
        if filters.get('subjects'):
            # Search in comma-separated subjects field
            subject_conditions = [
                TimelineEvent.subjects.like(f'%{subject}%')
                for subject in filters['subjects']
            ]
            query = query.filter(or_(*subject_conditions))

        # Filter by tags
        if filters.get('tags'):
            tag_conditions = [
                TimelineEvent.tags.like(f'%{tag}%')
                for tag in filters['tags']
            ]
            query = query.filter(or_(*tag_conditions))

        # Filter by confidence level
        if filters.get('confidence_levels'):
            query = query.filter(TimelineEvent.confidence_level.in_(filters['confidence_levels']))

        # Filter by evidence presence
        if filters.get('has_evidence') is not None:
            if filters['has_evidence']:
                query = query.filter(TimelineEvent.evidence_id.isnot(None))
            else:
                query = query.filter(TimelineEvent.evidence_id.is_(None))

        return query.order_by(TimelineEvent.event_date.asc()).all()

    @staticmethod
    def get_timeline_by_subject(case_id, subject_name):
        """
        Get timeline events for a specific subject.

        Args:
            case_id: Case ID
            subject_name: Subject name to filter by

        Returns:
            list: Timeline events involving the subject
        """
        return TimelineEvent.query.filter(
            and_(
                TimelineEvent.case_id == case_id,
                TimelineEvent.is_deleted == False,
                TimelineEvent.subjects.like(f'%{subject_name}%')
            )
        ).order_by(TimelineEvent.event_date.asc()).all()

    @staticmethod
    def get_timeline_stats(case_id):
        """
        Get statistics about the timeline.

        Args:
            case_id: Case ID

        Returns:
            dict: Statistics including counts by type, date range, etc.
        """
        events = TimelineEvent.query.filter_by(case_id=case_id, is_deleted=False).all()

        if not events:
            return {
                'total_events': 0,
                'events_by_type': {},
                'date_range': None,
                'events_with_evidence': 0,
                'subjects': []
            }

        # Count by event type
        events_by_type = {}
        for event in events:
            event_type_name = event.event_type.value
            events_by_type[event_type_name] = events_by_type.get(event_type_name, 0) + 1

        # Get date range
        dates = [e.event_date for e in events if e.event_date]
        date_range = {
            'start': min(dates) if dates else None,
            'end': max(dates) if dates else None
        }

        # Count events with evidence
        events_with_evidence = sum(1 for e in events if e.evidence_id)

        # Get unique subjects
        all_subjects = []
        for event in events:
            if event.subjects:
                all_subjects.extend([s.strip() for s in event.subjects.split(',')])
        unique_subjects = list(set(all_subjects))

        return {
            'total_events': len(events),
            'events_by_type': events_by_type,
            'date_range': date_range,
            'events_with_evidence': events_with_evidence,
            'subjects': unique_subjects
        }

    @staticmethod
    def create_event(case_id, user, event_data):
        """
        Create a new timeline event.

        Args:
            case_id: Case ID
            user: User creating the event
            event_data: dict with event fields

        Returns:
            TimelineEvent: Created event
        """
        event = TimelineEvent(
            case_id=case_id,
            created_by_id=user.id,
            event_type=event_data['event_type'],
            title=event_data['title'],
            description=event_data.get('description'),
            event_date=event_data['event_date'],
            location_name=event_data.get('location_name'),
            latitude=event_data.get('latitude'),
            longitude=event_data.get('longitude'),
            subjects=event_data.get('subjects'),
            entities=event_data.get('entities'),
            tags=event_data.get('tags'),
            confidence_level=event_data.get('confidence_level', 'medium'),
            source=event_data.get('source'),
            color=event_data.get('color'),
            icon=event_data.get('icon'),
            evidence_id=event_data.get('evidence_id')
        )

        db.session.add(event)
        db.session.commit()

        return event

    @staticmethod
    def update_event(event_id, event_data):
        """
        Update an existing timeline event.

        Args:
            event_id: Event ID
            event_data: dict with updated fields

        Returns:
            TimelineEvent: Updated event
        """
        event = TimelineEvent.query.get_or_404(event_id)

        # Update fields
        for field in ['title', 'description', 'event_date', 'location_name',
                      'latitude', 'longitude', 'subjects', 'entities', 'tags',
                      'confidence_level', 'source', 'color', 'icon']:
            if field in event_data:
                setattr(event, field, event_data[field])

        event.updated_at = datetime.utcnow()
        db.session.commit()

        return event

    @staticmethod
    def delete_event(event_id, user):
        """
        Soft delete a timeline event.

        Args:
            event_id: Event ID
            user: User deleting the event

        Returns:
            TimelineEvent: Deleted event
        """
        event = TimelineEvent.query.get_or_404(event_id)
        event.soft_delete(user)
        return event

    @staticmethod
    def get_timeline_for_vis_js(case_id, filters=None):
        """
        Get timeline data formatted for Vis.js Timeline library.

        Args:
            case_id: Case ID
            filters: Optional filters

        Returns:
            dict: {
                'items': list of events in Vis.js format,
                'groups': list of subject groups
            }
        """
        events = TimelineService.get_filtered_timeline(case_id, filters)

        # Convert to Vis.js format
        items = [event.to_vis_js() for event in events]

        # Extract unique groups (subjects)
        groups = []
        subject_set = set()
        for event in events:
            if event.subjects:
                subjects = [s.strip() for s in event.subjects.split(',')]
                for subject in subjects:
                    if subject not in subject_set:
                        subject_set.add(subject)
                        groups.append({'id': subject, 'content': subject})

        # Add a "General" group for events without subjects
        groups.insert(0, {'id': 'General', 'content': 'Eventos Generales'})

        return {
            'items': items,
            'groups': groups
        }

    @staticmethod
    def auto_create_evidence_events(case_id):
        """
        Automatically create timeline events for all evidence in a case
        that don't already have timeline events.

        Args:
            case_id: Case ID

        Returns:
            int: Number of events created
        """
        # Get all evidence for the case
        evidence_list = Evidence.query.filter_by(case_id=case_id, is_deleted=False).all()

        # Get existing evidence IDs that already have timeline events
        existing_evidence_ids = set(
            e.evidence_id for e in TimelineEvent.query.filter_by(case_id=case_id).all()
            if e.evidence_id
        )

        created_count = 0
        for evidence in evidence_list:
            if evidence.id not in existing_evidence_ids:
                # Create timeline event for this evidence
                TimelineEvent.create_from_evidence(
                    evidence,
                    evidence.uploaded_by,
                    EventType.EVIDENCE_ACQUIRED
                )
                created_count += 1

        return created_count

    @staticmethod
    def get_timeline_export_data(case_id, filters=None):
        """
        Get timeline data formatted for export (JSON/CSV).

        Args:
            case_id: Case ID
            filters: Optional filters

        Returns:
            list: Events as dictionaries with all fields
        """
        events = TimelineService.get_filtered_timeline(case_id, filters)
        return [event.to_dict() for event in events]

    @staticmethod
    def detect_patterns(case_id):
        """
        Analyze timeline to detect patterns and routines.

        Args:
            case_id: Case ID

        Returns:
            dict: Detected patterns (location recurrences, time patterns, etc.)
        """
        events = TimelineEvent.query.filter_by(case_id=case_id, is_deleted=False).all()

        if len(events) < 3:
            return {'patterns': [], 'message': 'Not enough events to detect patterns'}

        patterns = []

        # Location recurrence pattern
        location_counts = {}
        for event in events:
            if event.location_name:
                location_counts[event.location_name] = location_counts.get(event.location_name, 0) + 1

        recurring_locations = [(loc, count) for loc, count in location_counts.items() if count >= 3]
        if recurring_locations:
            patterns.append({
                'type': 'recurring_location',
                'description': 'Ubicaciones recurrentes detectadas',
                'data': recurring_locations
            })

        # Time-of-day pattern
        hour_counts = {}
        for event in events:
            if event.event_date:
                hour = event.event_date.hour
                hour_counts[hour] = hour_counts.get(hour, 0) + 1

        peak_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        if peak_hours:
            patterns.append({
                'type': 'peak_hours',
                'description': 'Horarios de mayor actividad',
                'data': [(f'{h:02d}:00-{h:02d}:59', count) for h, count in peak_hours]
            })

        # Day-of-week pattern
        weekday_counts = {}
        for event in events:
            if event.event_date:
                weekday = event.event_date.strftime('%A')
                weekday_counts[weekday] = weekday_counts.get(weekday, 0) + 1

        if weekday_counts:
            patterns.append({
                'type': 'weekday_activity',
                'description': 'Actividad por día de la semana',
                'data': sorted(weekday_counts.items(), key=lambda x: x[1], reverse=True)
            })

        return {'patterns': patterns, 'total_events_analyzed': len(events)}
