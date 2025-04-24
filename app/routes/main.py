from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify
import os
import psutil
import subprocess
from werkzeug.utils import secure_filename
from functools import wraps
import time
from app.services.wireguard import WireGuardService
from app.services.pending_configs import PendingConfigsService
from app.services.ip_forwarding import IPForwardingService
from datetime import datetime
from app.services.iptables_manager import IptablesManager

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
        # First, ensure IP forwarding is enabled
        if not IPForwardingService.check_status():
            success, error = IPForwardingService.enable_permanent()
            if not success:
                return jsonify({
                    'error': 'Failed to enable IP forwarding',
                    'details': error
                }), 500
        
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

@bp.route('/clients/<client_id>/status', methods=['GET'])
def get_client_status(client_id):
    """Get the status of a WireGuard client."""
    client = current_app.config_storage.get_client(client_id)
    if not client:
        return jsonify({'error': 'Client not found'}), 404
    
    try:
        # Get interface name from config path
        interface_name = os.path.splitext(os.path.basename(client['config_path']))[0]
        
        # Get status using WireGuardService
        status = WireGuardService.get_client_status(interface_name)
        
        # If we get an error about no such device, it means the interface is not active
        if 'error' in status and 'No such device' in status['error']:
            return jsonify({
                'interface': interface_name,
                'connected': False,
                'status': 'inactive',
                'message': 'Interface is not active'
            })
        
        # Update last handshake in database if available
        if status.get('last_handshake'):
            current_app.config_storage.update_client_status(
                client_id,
                'active' if status.get('connected') else 'inactive',
                datetime.fromisoformat(status['last_handshake'])
            )
        
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/system/ip_forwarding', methods=['GET'])
def get_ip_forwarding_status():
    """Get the current IP forwarding status."""
    status = IPForwardingService.check_status()
    return jsonify({
        'enabled': status,
        'message': 'IP forwarding is enabled' if status else 'IP forwarding is disabled'
    })

@bp.route('/system/ip_forwarding', methods=['POST'])
def set_ip_forwarding():
    """Enable or disable IP forwarding."""
    if not request.is_json:
        return jsonify({'error': 'Content-Type must be application/json'}), 400
    
    data = request.get_json()
    if not isinstance(data.get('enable'), bool):
        return jsonify({'error': 'Request must include "enable" boolean field'}), 400
    
    try:
        if data['enable']:
            success, error = IPForwardingService.enable_permanent()
        else:
            success, error = IPForwardingService.disable_temporary()
            
        if not success:
            return jsonify({
                'error': 'Failed to update IP forwarding',
                'details': error
            }), 500
            
        return jsonify({
            'status': 'success',
            'message': f"IP forwarding {'enabled' if data['enable'] else 'disabled'} successfully"
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/clients/<client_id>/setup-forwarding', methods=['POST'])
def setup_forwarding(client_id):
    """Set up IP forwarding and iptables rules for a client."""
    client = current_app.config_storage.get_client(client_id)
    if not client:
        return jsonify({'error': 'Client not found'}), 404
    
    try:
        # Get interface name from config path
        interface_name = os.path.splitext(os.path.basename(client['config_path']))[0]
        
        # Set up forwarding rules
        success, error = IptablesManager.setup_forwarding(interface_name)
        if not success:
            return jsonify({
                'error': 'Failed to set up forwarding',
                'details': error
            }), 500
        
        # Get router command
        router_cmd = IptablesManager.get_router_command(interface_name, client['subnet'])
        
        return jsonify({
            'status': 'success',
            'message': 'Forwarding rules set up successfully',
            'router_command': router_cmd
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/clients/<client_id>/cleanup-forwarding', methods=['POST'])
def cleanup_forwarding(client_id):
    """Remove IP forwarding and iptables rules for a client."""
    client = current_app.config_storage.get_client(client_id)
    if not client:
        return jsonify({'error': 'Client not found'}), 404
    
    try:
        # Get interface name from config path
        interface_name = os.path.splitext(os.path.basename(client['config_path']))[0]
        
        # Clean up forwarding rules
        success, error = IptablesManager.cleanup_forwarding(interface_name)
        if not success:
            return jsonify({
                'error': 'Failed to clean up forwarding',
                'details': error
            }), 500
        
        return jsonify({
            'status': 'success',
            'message': 'Forwarding rules cleaned up successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/clients/<client_id>/forwarding-rules', methods=['GET'])
def get_forwarding_rules(client_id):
    """Get the current iptables rules for a client."""
    client = current_app.config_storage.get_client(client_id)
    if not client:
        return jsonify({'error': 'Client not found'}), 404
    
    try:
        # Get interface name from config path
        interface_name = os.path.splitext(os.path.basename(client['config_path']))[0]
        
        # Get forwarding rules
        success, rules, error = IptablesManager.get_forwarding_rules(interface_name)
        if not success:
            return jsonify({
                'error': 'Failed to get forwarding rules',
                'details': error
            }), 500
        
        return jsonify({
            'status': 'success',
            'rules': rules
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500 