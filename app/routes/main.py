from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify
import os
import psutil
from werkzeug.utils import secure_filename
from functools import wraps
import time
from app.services.wireguard import WireGuardService

bp = Blueprint('main', __name__)

# Rate limiting decorator
def rate_limit(max_requests=5, time_window=60):
    """Rate limiting decorator for endpoints."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Simple in-memory rate limiting
            if not hasattr(current_app, 'rate_limits'):
                current_app.rate_limits = {}
            
            client_ip = request.remote_addr
            now = time.time()
            
            if client_ip not in current_app.rate_limits:
                current_app.rate_limits[client_ip] = {'count': 0, 'window_start': now}
            
            window = current_app.rate_limits[client_ip]
            
            if now - window['window_start'] > time_window:
                window['count'] = 0
                window['window_start'] = now
            
            if window['count'] >= max_requests:
                return jsonify({'error': 'Rate limit exceeded'}), 429
            
            window['count'] += 1
            return f(*args, **kwargs)
        return wrapped
    return decorator

@bp.route('/')
def index():
    """Dashboard page showing active clients and system status."""
    return render_template('index.html')

@bp.route('/clients')
def clients():
    """List all WireGuard clients."""
    return render_template('clients.html')

@bp.route('/clients/upload', methods=['POST'])
@rate_limit(max_requests=5, time_window=60)
def upload_client():
    """Handle WireGuard client config upload."""
    if 'config' not in request.files:
        return jsonify({'error': 'No config file provided'}), 400
    
    file = request.files['config']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    # Validate file extension
    if not file.filename.endswith('.conf'):
        return jsonify({'error': 'Invalid file type. Please upload a .conf file'}), 400
    
    # Validate file size (max 10KB)
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    if file_size > 10 * 1024:  # 10KB
        return jsonify({'error': 'File too large. Maximum size is 10KB'}), 400
    
    try:
        # Secure filename and create temp path
        filename = secure_filename(file.filename)
        temp_dir = os.path.join(current_app.instance_path, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, filename)
        
        # Save file temporarily
        file.save(temp_path)
        
        # Read and validate config
        with open(temp_path, 'r') as f:
            config_content = f.read()
        
        # Validate config using WireGuardService
        is_valid, error_msg, config_data = WireGuardService.validate_config(config_content)
        
        if not is_valid:
            # Clean up temp file
            os.remove(temp_path)
            return jsonify({'error': error_msg}), 400
        
        # If valid, move to permanent storage
        config_dir = os.path.join(current_app.instance_path, 'configs')
        os.makedirs(config_dir, exist_ok=True)
        final_path = os.path.join(config_dir, filename)
        os.rename(temp_path, final_path)
        
        # Set proper permissions
        os.chmod(final_path, 0o600)
        
        return jsonify({
            'status': 'success',
            'message': 'Config uploaded and validated successfully',
            'config_data': config_data
        })
        
    except Exception as e:
        # Clean up temp file if it exists
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({'error': f'Error processing config: {str(e)}'}), 500

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