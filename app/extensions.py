"""
Flask extensions initialization.

Extensions are initialized here but configured in the application factory.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask_talisman import Talisman

# Database
db = SQLAlchemy()
migrate = Migrate()

# Authentication
login_manager = LoginManager()
bcrypt = Bcrypt()

# Security
csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)
cache = Cache(config={'CACHE_TYPE': 'simple'})
talisman = Talisman()

# Configure login manager
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor, inicie sesión para acceder a esta página.'
login_manager.login_message_category = 'info'
login_manager.session_protection = 'strong'


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login."""
    from app.models.user import User
    return User.query.get(int(user_id))
