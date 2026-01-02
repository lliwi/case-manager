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
    stats = {
        'total_cases': 0,
        'active_cases': 0,
        'total_evidences': 0,
        'total_actions': 0,
    }

    # TODO: Update these queries when case and evidence models are created
    # For now, just count audit logs
    stats['total_actions'] = AuditLog.query.filter_by(user_id=current_user.id).count()

    return stats
