"""
Graph blueprint for relationship visualization.
"""
from flask import Blueprint

graph_bp = Blueprint('graph', __name__)

from app.blueprints.graph import routes
