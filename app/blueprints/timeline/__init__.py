"""
Timeline blueprint.
"""
from flask import Blueprint

timeline_bp = Blueprint('timeline', __name__)

from app.blueprints.timeline import routes
