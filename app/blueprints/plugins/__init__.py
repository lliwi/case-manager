"""Plugins blueprint for plugin management and execution."""
from flask import Blueprint

plugins_bp = Blueprint('plugins', __name__)

from app.blueprints.plugins import routes
