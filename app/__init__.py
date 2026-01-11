"""
Application factory for Case Manager.

This module creates and configures the Flask application instance.
"""
import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template
from werkzeug.middleware.proxy_fix import ProxyFix
from app.config import config
from app.extensions import (
    db, migrate, login_manager, bcrypt, csrf,
    limiter, cache, talisman
)


def create_app(config_name=None):
    """
    Application factory pattern.

    Args:
        config_name: Configuration name ('development', 'production', 'testing')

    Returns:
        Configured Flask application instance
    """
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'production')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Configure ProxyFix for proper IP detection behind Nginx
    # x_for=1: Trust X-Forwarded-For header (1 proxy)
    # x_proto=1: Trust X-Forwarded-Proto header
    # x_host=1: Trust X-Forwarded-Host header
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Initialize extensions
    initialize_extensions(app)

    # Register blueprints
    register_blueprints(app)

    # Register error handlers
    register_error_handlers(app)

    # Register CLI commands
    register_cli_commands(app)

    # Configure logging
    configure_logging(app)

    # Initialize plugin system
    initialize_plugins(app)

    return app


def initialize_extensions(app):
    """Initialize Flask extensions."""
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    cache.init_app(app)

    # Configure Talisman (security headers)
    if not app.config['DEBUG']:
        talisman.init_app(
            app,
            force_https=False,  # Set to True in production with HTTPS
            content_security_policy={
                'default-src': "'self'",
                'script-src': ["'self'", "'unsafe-inline'", "cdn.jsdelivr.net", "unpkg.com"],
                'style-src': ["'self'", "'unsafe-inline'", "cdn.jsdelivr.net"],
                'img-src': ["'self'", "data:"],
                'font-src': ["'self'", "cdn.jsdelivr.net"],
            }
        )


def register_blueprints(app):
    """Register application blueprints."""
    # Import blueprints
    from app.blueprints.auth import auth_bp
    from app.blueprints.dashboard import dashboard_bp
    from app.blueprints.cases import cases_bp
    from app.blueprints.libro_registro import libro_bp
    from app.blueprints.evidence import evidence_bp
    from app.blueprints.graph import graph_bp
    from app.blueprints.timeline import timeline_bp
    from app.blueprints.plugins import plugins_bp
    from app.blueprints.reports import reports_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.tasks import tasks_bp
    from app.blueprints.osint import osint

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(cases_bp, url_prefix='/cases')
    app.register_blueprint(libro_bp, url_prefix='/libro-registro')
    app.register_blueprint(evidence_bp, url_prefix='/evidence')
    app.register_blueprint(graph_bp, url_prefix='/graph')
    app.register_blueprint(timeline_bp, url_prefix='/timeline')
    app.register_blueprint(plugins_bp, url_prefix='/plugins')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(tasks_bp, url_prefix='/tasks')
    app.register_blueprint(osint, url_prefix='/osint')

    # Root route
    @app.route('/')
    def index():
        """Redirect to dashboard."""
        from flask import redirect, url_for
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.index'))
        return redirect(url_for('auth.login'))


def register_error_handlers(app):
    """Register error handlers."""
    @app.errorhandler(404)
    def not_found_error(error):
        """Handle 404 errors."""
        return render_template('errors/404.html'), 404

    @app.errorhandler(403)
    def forbidden_error(error):
        """Handle 403 errors."""
        return render_template('errors/403.html'), 403

    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors."""
        db.session.rollback()
        return render_template('errors/500.html'), 500

    @app.errorhandler(413)
    def request_entity_too_large(error):
        """Handle file too large errors."""
        return render_template('errors/413.html'), 413


def register_cli_commands(app):
    """Register custom CLI commands."""
    import click

    @app.cli.command()
    def init_db():
        """Initialize the database."""
        db.create_all()
        click.echo('Initialized the database.')

    @app.cli.command()
    @click.option('--email', prompt=True, help='Admin email')
    @click.option('--password', prompt=True, hide_input=True,
                  confirmation_prompt=True, help='Admin password')
    @click.option('--tip', prompt=True, help='TIP number')
    def create_admin(email, password, tip):
        """Create an admin user."""
        from app.models.user import User, Role
        from app.services.audit_service import log_action

        # Create admin role if it doesn't exist
        admin_role = Role.query.filter_by(name='admin').first()
        if not admin_role:
            admin_role = Role(name='admin', description='Administrator')
            db.session.add(admin_role)

        # Create detective role if it doesn't exist
        detective_role = Role.query.filter_by(name='detective').first()
        if not detective_role:
            detective_role = Role(name='detective', description='Detective Privado')
            db.session.add(detective_role)

        # Check if user exists
        user = User.query.filter_by(email=email).first()
        if user:
            click.echo(f'User {email} already exists.')
            return

        # Create admin user
        user = User(
            email=email,
            nombre='Administrator',
            tip_number=tip,
            is_active=True
        )
        user.set_password(password)
        user.roles.append(admin_role)
        user.roles.append(detective_role)

        db.session.add(user)
        db.session.commit()

        click.echo(f'Admin user {email} created successfully.')

    @app.cli.command()
    def init_neo4j():
        """Initialize Neo4j constraints and indexes."""
        from app.services.graph_service import GraphService

        service = GraphService()
        service.create_constraints()
        click.echo('Neo4j constraints and indexes created.')


def configure_logging(app):
    """Configure application logging."""
    if not app.debug and not app.testing:
        if app.config['LOG_TO_STDOUT']:
            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(logging.INFO)
            app.logger.addHandler(stream_handler)
        else:
            if not os.path.exists('logs'):
                os.mkdir('logs')
            file_handler = RotatingFileHandler(
                'logs/casemanager.log',
                maxBytes=10240000,  # 10MB
                backupCount=10
            )
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s: %(message)s '
                '[in %(pathname)s:%(lineno)d]'
            ))
            file_handler.setLevel(logging.INFO)
            app.logger.addHandler(file_handler)

        app.logger.setLevel(logging.INFO)
        app.logger.info('Case Manager startup')


def initialize_plugins(app):
    """Initialize the plugin system."""
    try:
        from app.plugins import plugin_manager
        plugin_manager.init_app(app)
        app.logger.info('Plugin system initialized')
    except Exception as e:
        app.logger.warning(f'Failed to initialize plugin system: {e}')
