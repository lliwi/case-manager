"""
Monitoring blueprint for social media surveillance.

Provides routes for managing monitoring tasks, sources, and results.
"""
from flask import Blueprint

monitoring_bp = Blueprint('monitoring', __name__, url_prefix='/monitoring')

from app.blueprints.monitoring import routes
