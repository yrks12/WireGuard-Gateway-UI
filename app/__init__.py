from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import os
import logging
from logging.handlers import RotatingFileHandler

# Load environment variables
load_dotenv()

# Initialize Flask extensions
db = SQLAlchemy()

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    
    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    # Configure the Flask application
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///wireguard.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['WIREGUARD_CONFIG_DIR'] = os.getenv('WIREGUARD_CONFIG_DIR', '/etc/wireguard')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024  # Max 16KB for config files

    # Initialize extensions
    db.init_app(app)

    # Initialize services
    with app.app_context():
        from app.routes.main import init_pending_configs
        init_pending_configs()

    # Register blueprints
    from app.routes import main
    app.register_blueprint(main.bp)

    # Register error handlers
    from app.error_handlers import register_error_handlers
    register_error_handlers(app)

    # Set up logging
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/wireguard.log', maxBytes=10240, backupCount=10)
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