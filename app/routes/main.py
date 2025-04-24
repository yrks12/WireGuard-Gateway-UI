from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify
import os
import psutil
import subprocess
from werkzeug.utils import secure_filename
from functools import wraps
import time
from app.services.wireguard import WireGuardService
from app.services.pending_configs import PendingConfigsService

bp = Blueprint('main', __name__)
pending_configs = None

def init_pending_configs():
    """Initialize the pending configs service with the app context."""
    global pending_configs
    storage_dir = os.path.join(current_app.instance_path, 'pending_configs')
    pending_configs = PendingConfigsService(storage_dir)

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
    clients = current_app.config_storage.list_clients()
    return render_template('clients.html', clients=clients)

@bp.route('/clients/upload', methods=['POST'])
@rate_limit(10, 60)  # 10 requests per minute
def upload_config():
    if 'config' not in request.files:
        return jsonify({'error': 'No config file provided'}), 400
        
    config_file = request.files['config']
    if not config_file.filename:
        return jsonify({'error': 'No config file selected'}), 400
        
    try:
        config_content = config_file.read().decode('utf-8')
        
        # Validate config content
        if not config_content.strip():
            return jsonify({'error': 'Config file is empty'}), 400
            
        # Check if AllowedIPs is 0.0.0.0/0
        if 'AllowedIPs = 0.0.0.0/0' in config_content:
            # Store as pending config
            config_id = pending_configs.store_pending_config(config_content)
            return jsonify({
                'config_id': config_id,
                'status': 'pending_subnet',
                'message': 'Please provide specific subnet(s)'
            }), 200
            
        # If not 0.0.0.0/0, validate and process normally
        # Validate file extension
        if not config_file.filename.endswith('.conf'):
            return jsonify({'error': 'Invalid file type. Please upload a .conf file'}), 400
        
        # Validate file size (max 10KB)
        config_file.seek(0, os.SEEK_END)
        file_size = config_file.tell()
        config_file.seek(0)
        if file_size > 10 * 1024:  # 10KB
            return jsonify({'error': 'File too large. Maximum size is 10KB'}), 400
        
        # Validate config using WireGuardService
        is_valid, error_msg, config_data = WireGuardService.validate_config(config_content)
        
        if not is_valid:
            # If the error is about 0.0.0.0/0, store as pending config
            if "0.0.0.0/0" in error_msg:
                config_id = pending_configs.store_pending_config(config_content)
                return jsonify({
                    'status': 'pending_subnet',
                    'config_id': config_id,
                    'message': error_msg
                }), 400
            else:
                return jsonify({'error': error_msg}), 400
        
        # Store the config and metadata
        client_id, metadata = current_app.config_storage.store_config(
            config_content,
            config_data['subnets'][0],  # Use first subnet
            config_data['public_key'],
            original_filename=config_file.filename
        )
        
        return jsonify({
            'status': 'success',
            'message': 'Config uploaded and validated successfully',
            'client_id': client_id,
            'metadata': metadata
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@bp.route('/clients/subnet', methods=['POST'])
@rate_limit(max_requests=5, time_window=60)
def submit_subnet():
    """Handle subnet submission for pending configs."""
    if not request.is_json:
        return jsonify({'error': 'Content-Type must be application/json'}), 400
    
    data = request.get_json()
    if not data or 'config_id' not in data or 'subnet' not in data:
        return jsonify({'error': 'Missing required fields: config_id and subnet'}), 400
    
    config_id = data['config_id']
    subnet = data['subnet']
    
    # Update config with new subnet
    success, error_msg, updated_config = pending_configs.update_config_with_subnet(config_id, subnet)
    
    if not success:
        return jsonify({'error': error_msg}), 400
    
    # Store the updated config and metadata
    client_id, metadata = current_app.config_storage.store_config(
        updated_config['content'],
        subnet,
        updated_config['public_key']
    )
    
    return jsonify({
        'status': 'success',
        'message': 'Config updated successfully',
        'client_id': client_id,
        'metadata': metadata
    })

@bp.route('/clients/<client_id>', methods=['GET'])
def get_client(client_id):
    """Get client details."""
    client = current_app.config_storage.get_client(client_id)
    if not client:
        return jsonify({'error': 'Client not found'}), 404
        
    # Get test history
    test_history = current_app.config_storage.get_test_history(client_id)
    
    return jsonify({
        'client': client,
        'test_history': test_history
    })

@bp.route('/clients/<client_id>/activate', methods=['POST'])
def activate_client(client_id):
    """Activate a WireGuard client."""
    client = current_app.config_storage.get_client(client_id)
    if not client:
        return jsonify({'error': 'Client not found'}), 404
    
    try:
        # Run wg-quick up with sudo
        config_path = client['config_path']
        result = subprocess.run(
            ['sudo', 'wg-quick', 'up', config_path],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return jsonify({
                'error': 'Failed to activate client',
                'details': result.stderr
            }), 500
        
        # Update client status
        current_app.config_storage.update_client_status(client_id, 'active')
        
        return jsonify({
            'status': 'success',
            'message': 'Client activated successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/clients/<client_id>/deactivate', methods=['POST'])
def deactivate_client(client_id):
    """Deactivate a WireGuard client."""
    client = current_app.config_storage.get_client(client_id)
    if not client:
        return jsonify({'error': 'Client not found'}), 404
    
    try:
        # Run wg-quick down with sudo
        config_path = client['config_path']
        result = subprocess.run(
            ['sudo', 'wg-quick', 'down', config_path],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return jsonify({
                'error': 'Failed to deactivate client',
                'details': result.stderr
            }), 500
        
        # Update client status
        current_app.config_storage.update_client_status(client_id, 'inactive')
        
        return jsonify({
            'status': 'success',
            'message': 'Client deactivated successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/clients/<client_id>/delete', methods=['DELETE'])
def delete_client(client_id):
    """Delete a client and its config."""
    success = current_app.config_storage.delete_client(client_id)
    if not success:
        return jsonify({'error': 'Client not found'}), 404
        
    return jsonify({
        'status': 'success',
        'message': 'Client deleted successfully'
    })

@bp.route('/system')
def system():
    """Show system metrics and status."""
    metrics = {
        'cpu_percent': psutil.cpu_percent(),
        'memory_percent': psutil.virtual_memory().percent,
        'disk_percent': psutil.disk_usage('/').percent
    }
    return render_template('system.html', metrics=metrics) 