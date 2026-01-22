"""
Dashboard routes.
"""
from flask import render_template
from flask_login import login_required, current_user
from app.blueprints.dashboard import dashboard_bp
from app.models.audit import AuditLog
from app.extensions import db
from datetime import datetime, timedelta


@dashboard_bp.route('/')
@login_required
def index():
    """Main dashboard."""
    # Get user statistics
    stats = get_dashboard_stats()

    # Get recent activity
    recent_activity = AuditLog.query.filter_by(user_id=current_user.id).order_by(
        AuditLog.timestamp.desc()
    ).limit(10).all()

    return render_template(
        'dashboard/index.html',
        stats=stats,
        recent_activity=recent_activity
    )


def get_dashboard_stats():
    """Get dashboard statistics for current user."""
    from app.models.case import Case, CaseStatus
    from app.models.evidence import Evidence

    stats = {
        'total_cases': 0,
        'active_cases': 0,
        'total_evidence': 0,
        'graph_nodes': 0,
        'cases_this_month': 0,
        'total_actions': 0,
        'monitoring_alerts': 0,
        'active_monitoring_tasks': 0,
    }

    try:
        # Base query for cases (filter by detective if not admin)
        if current_user.is_admin():
            case_query = Case.query.filter(Case.is_deleted == False)
        else:
            case_query = Case.query.filter(
                Case.detective_id == current_user.id,
                Case.is_deleted == False
            )

        # Total cases
        stats['total_cases'] = case_query.count()

        # Active cases (not archived, closed, or suspended)
        active_statuses = [CaseStatus.PENDIENTE_VALIDACION, CaseStatus.EN_INVESTIGACION]
        stats['active_cases'] = case_query.filter(Case.status.in_(active_statuses)).count()

        # Cases this month
        first_day_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        stats['cases_this_month'] = case_query.filter(Case.created_at >= first_day_of_month).count()

        # Get case IDs for evidence query
        case_ids = [c.id for c in case_query.all()]

        # Total evidence (for user's cases)
        if case_ids:
            stats['total_evidence'] = Evidence.query.filter(
                Evidence.case_id.in_(case_ids),
                Evidence.is_deleted == False
            ).count()

        # Graph nodes (try to get from Neo4j)
        try:
            from app.services.graph_service import GraphService
            graph_service = GraphService()
            if case_ids:
                # Count nodes for user's cases
                total_nodes = 0
                for case_id in case_ids[:10]:  # Limit to avoid slow queries
                    stats_data = graph_service.get_graph_statistics(case_id)
                    if stats_data:
                        total_nodes += stats_data.get('total_nodes', 0)
                stats['graph_nodes'] = total_nodes
        except Exception:
            # Neo4j might not be available
            stats['graph_nodes'] = 0

        # Total audit actions
        stats['total_actions'] = AuditLog.query.filter_by(user_id=current_user.id).count()

        # Monitoring metrics
        try:
            from app.models.monitoring import MonitoringTask, MonitoringResult, MonitoringStatus

            # Active monitoring tasks for user's cases
            if case_ids:
                stats['active_monitoring_tasks'] = MonitoringTask.query.filter(
                    MonitoringTask.case_id.in_(case_ids),
                    MonitoringTask.status == MonitoringStatus.ACTIVE
                ).count()

                # Unacknowledged alerts from monitoring results
                stats['monitoring_alerts'] = MonitoringResult.query.join(
                    MonitoringTask, MonitoringResult.task_id == MonitoringTask.id
                ).filter(
                    MonitoringTask.case_id.in_(case_ids),
                    MonitoringResult.is_alert == True,
                    MonitoringResult.alert_acknowledged == False
                ).count()
        except Exception:
            # Monitoring module might not be available
            pass

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error getting dashboard stats: {e}")

    return stats
