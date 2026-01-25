"""
Case deletion service for complete case removal.

Handles deletion of case and all related data:
- Evidence files and records (soft delete)
- Timeline events (soft delete)
- Reports and report files (soft delete)
- Monitoring tasks with sources and results (soft delete)
- OSINT contacts (soft delete)
- Neo4j graph nodes and relationships (hard delete)
- The case itself (soft delete)

IMPORTANT: Audit logs and Chain of Custody are NEVER deleted per Ley 5/2014.
"""
from datetime import datetime
from typing import Dict, Any, Optional
from flask import current_app
import os

from app.extensions import db
from app.models.audit import AuditLog


class CaseDeleteService:
    """Service for complete case deletion with all related elements."""

    @staticmethod
    def get_case_statistics(case) -> Dict[str, Any]:
        """Get statistics about what will be deleted for a case."""
        from app.models.evidence import Evidence
        from app.models.timeline import TimelineEvent
        from app.models.report import Report
        from app.models.monitoring import MonitoringTask, MonitoringResult

        try:
            from app.models.osint_contact import OSINTContact
            osint_count = OSINTContact.query.filter_by(
                case_id=case.id, is_deleted=False
            ).count()
        except ImportError:
            osint_count = 0

        evidence_count = Evidence.query.filter_by(
            case_id=case.id, is_deleted=False
        ).count()

        timeline_count = TimelineEvent.query.filter_by(
            case_id=case.id, is_deleted=False
        ).count()

        report_count = Report.query.filter_by(
            case_id=case.id, is_deleted=False
        ).count()

        monitoring_tasks = MonitoringTask.query.filter_by(
            case_id=case.id, is_deleted=False
        ).all()
        monitoring_task_count = len(monitoring_tasks)

        monitoring_result_count = sum(
            MonitoringResult.query.filter_by(task_id=task.id).count()
            for task in monitoring_tasks
        )

        graph_stats = {'total_nodes': 0, 'total_relationships': 0}
        try:
            from app.services.graph_service import GraphService
            graph_service = GraphService()
            graph_stats = graph_service.get_graph_statistics(case.id)
        except Exception as e:
            current_app.logger.warning(f"Could not get graph statistics: {e}")

        return {
            'evidences': evidence_count,
            'timeline_events': timeline_count,
            'reports': report_count,
            'monitoring_tasks': monitoring_task_count,
            'monitoring_results': monitoring_result_count,
            'osint_contacts': osint_count,
            'graph_nodes': graph_stats.get('total_nodes', 0),
            'graph_relationships': graph_stats.get('total_relationships', 0)
        }

    @staticmethod
    def delete_case_completely(
        case, user, delete_files: bool = False, delete_graph: bool = True
    ) -> Dict[str, Any]:
        """Delete a case and all its related elements."""
        from app.models.evidence import Evidence
        from app.models.timeline import TimelineEvent
        from app.models.report import Report
        from app.models.monitoring import MonitoringTask

        results = {
            'success': True,
            'case_id': case.id,
            'case_numero_orden': case.numero_orden,
            'deleted_counts': {
                'evidences': 0, 'timeline_events': 0, 'reports': 0,
                'monitoring_tasks': 0, 'osint_contacts': 0,
                'graph_nodes': 0, 'files_deleted': 0
            },
            'errors': []
        }

        try:
            # 1. Delete evidences
            for evidence in Evidence.query.filter_by(case_id=case.id, is_deleted=False).all():
                try:
                    if delete_files and evidence.file_path and os.path.exists(evidence.file_path):
                        os.remove(evidence.file_path)
                        results['deleted_counts']['files_deleted'] += 1
                    evidence.is_deleted = True
                    evidence.deleted_at = datetime.utcnow()
                    evidence.deleted_by_id = user.id
                    results['deleted_counts']['evidences'] += 1
                except Exception as e:
                    results['errors'].append(f"Error evidence {evidence.id}: {e}")

            # 2. Delete timeline events
            for event in TimelineEvent.query.filter_by(case_id=case.id, is_deleted=False).all():
                event.is_deleted = True
                event.deleted_at = datetime.utcnow()
                event.deleted_by_id = user.id
                results['deleted_counts']['timeline_events'] += 1

            # 3. Delete reports
            for report in Report.query.filter_by(case_id=case.id, is_deleted=False).all():
                if delete_files and report.file_path and os.path.exists(report.file_path):
                    os.remove(report.file_path)
                    results['deleted_counts']['files_deleted'] += 1
                report.is_deleted = True
                report.deleted_at = datetime.utcnow()
                results['deleted_counts']['reports'] += 1

            # 4. Delete monitoring tasks
            for task in MonitoringTask.query.filter_by(case_id=case.id, is_deleted=False).all():
                if delete_files:
                    for result in task.results.all():
                        if result.media_local_paths:
                            for path in result.media_local_paths:
                                if path and os.path.exists(path):
                                    os.remove(path)
                                    results['deleted_counts']['files_deleted'] += 1
                task.soft_delete(user.id)
                results['deleted_counts']['monitoring_tasks'] += 1

            # 5. Delete OSINT contacts
            try:
                from app.models.osint_contact import OSINTContact
                for contact in OSINTContact.query.filter_by(case_id=case.id, is_deleted=False).all():
                    contact.soft_delete(user.id)
                    results['deleted_counts']['osint_contacts'] += 1
            except ImportError:
                pass

            # 6. Delete Neo4j graph
            if delete_graph:
                try:
                    from app.services.graph_service import GraphService
                    graph_service = GraphService()
                    stats = graph_service.get_graph_statistics(case.id)
                    if graph_service.clear_case_graph(case.id):
                        results['deleted_counts']['graph_nodes'] = stats.get('total_nodes', 0)
                except Exception as e:
                    results['errors'].append(f"Error clearing Neo4j graph: {e}")

            # 7. Delete legitimacy document
            if delete_files and case.legitimacy_document_path:
                if os.path.exists(case.legitimacy_document_path):
                    os.remove(case.legitimacy_document_path)
                    results['deleted_counts']['files_deleted'] += 1

            # 8. Soft delete the case
            case.is_deleted = True
            case.deleted_at = datetime.utcnow()
            case.deleted_by_id = user.id

            db.session.commit()

            # 9. Log deletion
            AuditLog.log(
                action='CASE_DELETED_COMPLETE',
                resource_type='case',
                resource_id=case.id,
                user=user,
                description=f'Case {case.numero_orden} deleted with all related elements',
                extra_data={'deleted_counts': results['deleted_counts']}
            )

        except Exception as e:
            db.session.rollback()
            results['success'] = False
            results['errors'].append(f"Critical error: {e}")

        return results

    @staticmethod
    def can_delete_case(case, user) -> tuple:
        """Check if a user can delete a case."""
        if not user.is_admin():
            return False, "Solo los administradores pueden eliminar casos."
        if case.is_deleted:
            return False, "Este caso ya ha sido eliminado."
        return True, None
