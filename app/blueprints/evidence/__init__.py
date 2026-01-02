"""
Evidence blueprint.
"""
from flask import Blueprint

evidence_bp = Blueprint('evidence', __name__)

from app.blueprints.evidence import routes
