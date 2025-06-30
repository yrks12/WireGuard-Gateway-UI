
import pytest
import os
import tempfile
import shutil
from app import create_app, db

@pytest.fixture(scope='session')
def app():
    """Create and configure a new app instance for each test session."""
    # Create a temporary directory for the instance folder
    instance_path = tempfile.mkdtemp()
    
    # Create a temporary database file
    db_fd, db_path = tempfile.mkstemp()
    
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
        'SECRET_KEY': 'test-secret-key',
        'WTF_CSRF_ENABLED': False,  # Disable CSRF for testing forms
        'INSTANCE_PATH': instance_path
    })

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

    # Clean up the temporary directory and database file
    os.close(db_fd)
    os.unlink(db_path)
    shutil.rmtree(instance_path)

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """A test runner for the app's Click commands."""
    return app.test_cli_runner()

@pytest.fixture
def app_context(app):
    """A fixture to provide the app context."""
    with app.app_context():
        yield

