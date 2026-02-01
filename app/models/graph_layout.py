"""
Graph layout model for persisting node positions.

Stores the visual layout of graph nodes per case so that
the arrangement is consistent across page loads and reports.
"""
from datetime import datetime
from app.extensions import db


class GraphLayout(db.Model):
    """Stores graph node positions for a case."""

    __tablename__ = 'graph_layouts'

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), nullable=False, unique=True)
    positions = db.Column(db.JSON, nullable=False, default=dict)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    case = db.relationship('Case', backref=db.backref('graph_layout', uselist=False))

    def get_positions(self):
        """Return positions dict: {node_id: {x, y}}."""
        return self.positions or {}

    def set_positions(self, positions):
        """Set positions dict."""
        self.positions = positions
        self.updated_at = datetime.utcnow()

    def update_node_position(self, node_id, x, y):
        """Update position for a single node."""
        if self.positions is None:
            self.positions = {}
        pos = dict(self.positions)
        pos[str(node_id)] = {'x': x, 'y': y}
        self.positions = pos
        self.updated_at = datetime.utcnow()

    def remove_node_position(self, node_id):
        """Remove position for a node (e.g. when deleted)."""
        if self.positions and str(node_id) in self.positions:
            pos = dict(self.positions)
            del pos[str(node_id)]
            self.positions = pos

    def __repr__(self):
        return f'<GraphLayout case_id={self.case_id}>'
