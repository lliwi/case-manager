"""
Cases blueprint.
"""
from flask import Blueprint

cases_bp = Blueprint('cases', __name__)

from app.blueprints.cases import routes
