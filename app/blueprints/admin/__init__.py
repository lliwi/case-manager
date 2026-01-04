"""Admin blueprint for system administration."""
from flask import Blueprint

admin_bp = Blueprint('admin', __name__)

from app.blueprints.admin import routes
