"""Reports blueprint for report generation and management."""
from flask import Blueprint

reports_bp = Blueprint('reports', __name__)

from app.blueprints.reports import routes
