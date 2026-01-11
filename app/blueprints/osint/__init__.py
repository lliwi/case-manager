"""
OSINT Blueprint
Manages OSINT contacts and validations
"""
from flask import Blueprint

osint = Blueprint('osint', __name__, url_prefix='/osint')

from app.blueprints.osint import routes
