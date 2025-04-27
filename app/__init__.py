from flask import Flask
from flask_login import LoginManager
from dotenv import load_dotenv
import os
import logging
from logging.handlers import RotatingFileHandler
from app.services.pending_configs import PendingConfigsService
from app.services.config_storage import ConfigStorageService
from app.database import db
from app.tasks import monitor_task

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
    app.instance_path = os.getenv('INSTANCE_PATH', '/opt/wireguard-gateway/instance')
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

        # Initialize monitoring task
        from app.tasks import start
        start(app)

    return app 