"""
Libro-registro blueprint.
"""
from flask import Blueprint

libro_bp = Blueprint('libro_registro', __name__)

from app.blueprints.libro_registro import routes
