from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
import os
import psutil
from werkzeug.utils import secure_filename

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    """Dashboard page showing active clients and system status."""
    return render_template('index.html')

@bp.route('/clients')
def clients():
    """List all WireGuard clients."""
    return render_template('clients.html')

@bp.route('/clients/upload', methods=['POST'])
def upload_client():
    """Handle WireGuard client config upload."""
    if 'config' not in request.files:
        flash('No config file provided', 'error')
        return redirect(url_for('main.clients'))
    
    file = request.files['config']
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('main.clients'))
    
    if file and file.filename.endswith('.conf'):
        filename = secure_filename(file.filename)
        # TODO: Implement config validation and processing
        flash('Config uploaded successfully', 'success')
        return redirect(url_for('main.clients'))
    else:
        flash('Invalid file type. Please upload a .conf file', 'error')
        return redirect(url_for('main.clients'))

@bp.route('/clients/<client_id>/activate', methods=['POST'])
def activate_client(client_id):
    """Activate a WireGuard client."""
    # TODO: Implement client activation
    return {'status': 'success', 'message': 'Client activated'}

@bp.route('/clients/<client_id>/deactivate', methods=['POST'])
def deactivate_client(client_id):
    """Deactivate a WireGuard client."""
    # TODO: Implement client deactivation
    return {'status': 'success', 'message': 'Client deactivated'}

@bp.route('/system')
def system():
    """Show system metrics and status."""
    metrics = {
        'cpu_percent': psutil.cpu_percent(),
        'memory_percent': psutil.virtual_memory().percent,
        'disk_percent': psutil.disk_usage('/').percent
    }
    return render_template('system.html', metrics=metrics) 