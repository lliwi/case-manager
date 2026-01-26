#!/usr/bin/env python3
"""
Script para inicializar la base de datos en instalaciones limpias.

Este script crea todas las tablas directamente desde los modelos SQLAlchemy,
evitando la necesidad de aplicar migraciones en instalaciones nuevas.

Para instalaciones existentes que necesiten actualizarse, usar:
    flask db upgrade
"""
import os
import sys

# Add app directory to path
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import inspect, text
from app import create_app
from app.extensions import db


def is_fresh_database():
    """Check if this is a fresh database without tables."""
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()

    # If no tables or only alembic_version exists, it's fresh
    return len(tables) == 0 or (len(tables) == 1 and 'alembic_version' in tables)


def create_all_tables():
    """Create all tables from SQLAlchemy models."""
    print("Creating all tables from models...")
    db.create_all()
    print("All tables created successfully.")


def stamp_migrations_head():
    """Mark all migrations as applied without running them."""
    from flask_migrate import stamp
    print("Stamping migrations to head...")
    stamp(revision='head')
    print("Migrations stamped to head.")


def verify_tables():
    """Verify that all expected tables were created."""
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()

    expected_tables = [
        'users', 'roles', 'user_roles',
        'cases', 'evidences', 'chain_of_custody',
        'evidence_analyses', 'reports',
        'audit_logs', 'timeline_events',
        'graph_nodes', 'graph_relationships',
        'legitimacy_types_custom', 'relationship_types_custom',
        'monitoring_tasks', 'osint_sources', 'osint_results'
    ]

    missing = [t for t in expected_tables if t not in tables]

    if missing:
        print(f"Warning: Some expected tables are missing: {missing}")
        return False

    print(f"Verified {len(tables)} tables created.")
    return True


def init_database():
    """Initialize database for a fresh installation."""
    app = create_app()

    with app.app_context():
        # Check if this is a fresh installation
        if not is_fresh_database():
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()

            # Check if alembic_version exists and has a version
            if 'alembic_version' in tables:
                result = db.session.execute(text("SELECT version_num FROM alembic_version"))
                version = result.scalar()
                if version:
                    print(f"Database already initialized at migration: {version}")
                    print("Use 'flask db upgrade' for updates.")
                    return True

            print("Database has existing tables but no migration tracking.")
            print("This may be a partially initialized database.")
            print("")
            print("Options:")
            print("  1. For fresh install: Drop database and run this script again")
            print("  2. For existing data: Run 'flask db stamp head' to mark as current")
            return False

        print("Fresh database detected. Initializing...")
        print("")

        # Create all tables from models
        create_all_tables()

        # Stamp migrations as applied
        stamp_migrations_head()

        # Verify
        print("")
        if verify_tables():
            print("")
            print("=" * 60)
            print("DATABASE INITIALIZED SUCCESSFULLY")
            print("=" * 60)
            print("")
            print("Tables created:")
            print("  - users, roles: User management and authentication")
            print("  - cases: Investigation case registry (Libro-Registro)")
            print("  - evidences, chain_of_custody: Forensic evidence management")
            print("  - evidence_analyses: Plugin analysis results")
            print("  - reports: Investigation reports")
            print("  - audit_logs: Immutable audit trail")
            print("  - timeline_events: Investigation timeline")
            print("  - graph_nodes, graph_relationships: Entity relationships")
            print("  - monitoring_tasks: Background task tracking")
            print("  - osint_sources, osint_results: OSINT monitoring")
            print("")
            print("Next step:")
            print("  python create_test_user.py")
            print("")
            return True
        else:
            print("Warning: Some tables may be missing. Check the logs above.")
            return False


if __name__ == '__main__':
    success = init_database()
    sys.exit(0 if success else 1)
