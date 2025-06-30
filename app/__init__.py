from flask import Flask
from flask_login import LoginManager
from dotenv import load_dotenv
import os
import logging
from logging.handlers import RotatingFileHandler
from app.services.pending_configs import PendingConfigsService
from app.services.config_storage import ConfigStorageService
from app.database import db

# Load environment variables
load_dotenv()

# Initialize Flask extensions
login_manager = LoginManager()

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    
    # Configure the Flask application
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///app.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Set up instance paths
    app.instance_path = os.getenv('INSTANCE_PATH', './instance')
    os.makedirs(app.instance_path, exist_ok=True)
    
    # Create configs directory in instance folder
    configs_dir = os.path.join(app.instance_path, 'configs')
    os.makedirs(configs_dir, exist_ok=True)
    app.config['WIREGUARD_CONFIG_DIR'] = configs_dir
    
    # Initialize extensions
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    db.init_app(app)

    # Import User model
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from app.routes import main, auth
    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)

    # Register error handlers
    from app.error_handlers import register_error_handlers
    register_error_handlers(app)

    # Set up logging
    if not app.debug:
        log_path = os.getenv('LOG_PATH', 'logs/wireguard.log')
        log_dir = os.path.dirname(log_path)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        file_handler = RotatingFileHandler(log_path, maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.DEBUG)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.DEBUG)
        app.logger.setLevel(logging.INFO)
        app.logger.info('WireGuard Gateway UI startup')

    # Initialize services and create database tables within app context
    with app.app_context():
        # Initialize pending configs service
        from app.routes.main import init_pending_configs
        init_pending_configs()
        
        # Initialize config storage service
        db_path = os.path.join(app.instance_path, 'configs.db')
        app.config_storage = ConfigStorageService(configs_dir, db_path)
        
        # Create database tables
        db.create_all()

        # Create default development user if in debug mode
        create_default_dev_user(app)

        # Initialize DNS monitoring and auto-reconnect system
        init_dns_monitoring_and_auto_reconnect(app)

        # Initialize monitoring task
        from app.tasks import start
        start(app)

    return app

def create_default_dev_user(app):
    """Create a default development user if running in debug mode."""
    if app.debug:
        try:
            from app.models.user import User
            from werkzeug.security import generate_password_hash
            
            # Check if default user already exists
            if not User.query.filter_by(username='admin').first():
                admin = User(
                    username='admin',
                    password=generate_password_hash('admin123'),
                    must_change_password=False  # Don't force password change in dev
                )
                db.session.add(admin)
                db.session.commit()
                app.logger.info("Created default development user: admin/admin123")
        except Exception as e:
            app.logger.error(f"Failed to create default development user: {e}")

def register_existing_ddns_clients(app):
    """Register existing clients with DDNS hostnames for monitoring."""
    try:
        from app.services.dns_resolver import DNSResolver
        
        # Get all existing clients
        clients = app.config_storage.list_clients()
        registered_count = 0
        
        for client in clients:
            try:
                # Read config file content
                with open(client['config_path'], 'r') as f:
                    config_content = f.read()
                
                # Extract hostname
                hostname = DNSResolver.extract_hostname_from_config(config_content)
                if hostname:
                    # Register for DNS monitoring
                    DNSResolver.register_client_hostname(client['id'], hostname, client['name'])
                    registered_count += 1
                    app.logger.debug(f"Registered existing client {client['name']} with hostname {hostname}")
                    
            except Exception as e:
                app.logger.warning(f"Failed to register client {client.get('name', 'unknown')}: {e}")
        
        if registered_count > 0:
            app.logger.info(f"Registered {registered_count} existing clients with DDNS hostnames")
        
    except Exception as e:
        app.logger.error(f"Failed to register existing DDNS clients: {e}")

def init_dns_monitoring_and_auto_reconnect(app):
    """Initialize DNS monitoring and auto-reconnect system."""
    try:
        from app.services.dns_resolver import DNSResolver
        from app.services.auto_reconnect import AutoReconnectService
        
        # Set up DNS change callback
        def handle_dns_changes(changes):
            """Handle DNS changes by triggering auto-reconnect."""
            for change in changes:
                AutoReconnectService.handle_dns_change(change, app.config_storage)
        
        # Register the callback
        DNSResolver.set_dns_change_callback(handle_dns_changes)
        
        # Register existing clients with DDNS hostnames
        register_existing_ddns_clients(app)
        
        # Start DNS monitoring
        DNSResolver.start_monitoring()
        
        app.logger.info("DNS monitoring and auto-reconnect system initialized")
        
    except Exception as e:
        app.logger.error(f"Failed to initialize DNS monitoring: {e}")
        # Don't fail the app startup if DNS monitoring fails 