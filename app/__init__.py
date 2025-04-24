from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import os
import logging
from logging.handlers import RotatingFileHandler
from app.services.pending_configs import PendingConfigsService
from app.services.config_storage import ConfigStorageService

# Load environment variables
load_dotenv()

# Initialize Flask extensions
db = SQLAlchemy()

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
    db.init_app(app)

    # Initialize services
    with app.app_context():
        # Initialize pending configs service
        from app.routes.main import init_pending_configs
        init_pending_configs()
        
        # Initialize config storage service
        db_path = os.path.join(app.instance_path, 'configs.db')
        app.config_storage = ConfigStorageService(configs_dir, db_path)

    # Register blueprints
    from app.routes import main
    app.register_blueprint(main.bp)

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
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('WireGuard Gateway UI startup')

    # Create database tables
    with app.app_context():
        db.create_all()

    return app 