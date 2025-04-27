from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify
from flask_login import login_required
import os
import psutil
import subprocess
from werkzeug.utils import secure_filename
from functools import wraps
import time
import logging
from app.services.wireguard import WireGuardService
from app.services.pending_configs import PendingConfigsService
from app.services.ip_forwarding import IPForwardingService
from app.services.email_service import EmailService
from datetime import datetime, timedelta
from app.services.iptables_manager import IptablesManager
from app.services.connectivity_test import ConnectivityTestService
from app.services.route_command_generator import RouteCommandGenerator
from app.services.status_poller import StatusPoller
from app.forms import EmailSettingsForm
from app.models.email_settings import EmailSettings

logger = logging.getLogger(__name__)

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
@login_required
def index():
    """Dashboard page showing active clients and system status."""
    return render_template('index.html')

@bp.route('/clients')
@login_required
def clients():
    """Show clients page."""
    return render_template('clients.html')

@bp.route('/clients/upload', methods=['POST'])
@login_required
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
@login_required
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

@bp.route('/clients/<client_id>', methods=['GET', 'DELETE'])
@login_required
def client(client_id):
    """Get or delete a client."""
    if request.method == 'DELETE':
        try:
            current_app.config_storage.delete_client(client_id)
            return jsonify({'status': 'success', 'message': 'Client deleted successfully'})
        except Exception as e:
            return jsonify({'status': 'error', 'error': str(e)}), 500
    else:
        try:
            client = current_app.config_storage.get_client(client_id)
            if not client:
                return jsonify({'status': 'error', 'error': 'Client not found'}), 404
            
            # Get test history
            test_history = current_app.config_storage.get_test_history(client_id)
            
            # Read config file content
            try:
                with open(client['config_path'], 'r') as f:
                    config_content = f.read()
                client['config_content'] = config_content
            except Exception as e:
                logger.error(f"Error reading config file: {e}")
                client['config_content'] = None
            
            return jsonify({
                'status': 'success',
                'client': client,
                'test_history': test_history or []
            })
        except Exception as e:
            return jsonify({'status': 'error', 'error': str(e)}), 500

@bp.route('/clients/<client_id>/activate', methods=['POST'])
@login_required
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
@login_required
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

@bp.route('/clients/<client_id>/setup-forwarding', methods=['POST'])
@login_required
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
@login_required
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
@login_required
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

@bp.route('/clients/<client_id>/test-connectivity', methods=['POST'])
@login_required
def test_client_connectivity(client_id):
    """Test connectivity to a client's subnet or a specific IP."""
    try:
        # Get custom IP from request if provided
        custom_ip = request.json.get('ip') if request.is_json else None
        
        if custom_ip:
            # Test connectivity to custom IP
            success, result = ConnectivityTestService.test_connectivity(custom_ip)
            # Store target for custom IP test
            result['target'] = custom_ip
        else:
            # Test connectivity to client's AllowedIPs
            success, result = ConnectivityTestService.test_client_connectivity(
                client_id,
                current_app.config_storage
            )
        
        # Always save test result to history, whether success or failure
        current_app.config_storage.add_test_result(
            client_id=client_id,
            latency_ms=result.get('latency_ms'),
            success=result.get('success', False),
            target=result.get('target', 'N/A'),
            error=result.get('error')
        )
            
        if not success:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Connectivity test failed'),
                'target': result.get('target', 'N/A')
            }), 400
            
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error testing connectivity: {e}")
        # Save failed test due to exception
        try:
            current_app.config_storage.add_test_result(
                client_id=client_id,
                latency_ms=None,
                success=False,
                target=custom_ip if custom_ip else 'N/A',
                error=str(e)
            )
        except Exception as save_error:
            logger.error(f"Error saving failed test result: {save_error}")
            
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/clients/<client_id>/route-command', methods=['GET'])
@login_required
def get_route_command(client_id):
    """Get the route command for a client's subnet."""
    try:
        client = current_app.config_storage.get_client(client_id)
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        # Get the client's subnet
        subnet = client.get('subnet')
        if not subnet:
            return jsonify({'error': 'No subnet found for client'}), 400
        
        # Generate route command
        success, result = RouteCommandGenerator.generate_route_command(subnet)
        
        if not success:
            return jsonify({
                'success': False,
                'error': result
            }), 400
            
        return jsonify({
            'success': True,
            'command': result,
            'subnet': subnet
        })
        
    except Exception as e:
        logger.error(f"Error generating route command: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/system/metrics', methods=['GET'])
@login_required
def get_system_metrics():
    """Get system-wide metrics (CPU, RAM, etc.)."""
    try:
        metrics = StatusPoller.get_system_metrics()
        
        if 'error' in metrics:
            return jsonify({
                'success': False,
                'error': metrics['error']
            }), 400
            
        return jsonify({
            'success': True,
            'metrics': metrics
        })
        
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/api/clients', methods=['GET'])
@login_required
def get_clients():
    """Get all clients as JSON."""
    try:
        clients = current_app.config_storage.list_clients()
        return jsonify({
            'status': 'success',
            'clients': clients
        })
    except Exception as e:
        logger.error(f"Error getting clients: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@bp.route('/api/recent-activity', methods=['GET'])
@login_required
def get_recent_activity():
    """Get recent activity for the dashboard."""
    try:
        # Get all clients
        clients = current_app.config_storage.list_clients()
        
        # Get recent activity (last 5 actions)
        recent_activity = []
        for client in clients:
            # Add activation/deactivation events
            if client.get('last_activated'):
                recent_activity.append({
                    'client': client['name'],
                    'action': 'activated',
                    'status': 'success',
                    'time': client['last_activated']
                })
            
            if client.get('last_deactivated'):
                recent_activity.append({
                    'client': client['name'],
                    'action': 'deactivated',
                    'status': 'success',
                    'time': client['last_deactivated']
                })
            
            # Add test history
            test_history = current_app.config_storage.get_test_history(client['id'])
            if test_history:
                for test in test_history[-5:]:  # Last 5 tests
                    recent_activity.append({
                        'client': client['name'],
                        'action': 'connectivity test',
                        'status': 'success' if test['success'] else 'failed',
                        'time': test['timestamp']
                    })
        
        # Sort by time and get last 5
        recent_activity.sort(key=lambda x: x['time'], reverse=True)
        recent_activity = recent_activity[:5]
        
        return jsonify({
            'status': 'success',
            'activity': recent_activity
        })
    except Exception as e:
        logger.error(f"Error getting recent activity: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@bp.route('/api/system-load', methods=['GET'])
@login_required
def get_system_load():
    """Get system load for the dashboard."""
    try:
        # Get CPU load
        cpu_load = psutil.cpu_percent(interval=1)
        
        # Get memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        
        # Get disk usage
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        
        return jsonify({
            'status': 'success',
            'load': {
                'cpu': cpu_load,
                'memory': memory_percent,
                'disk': disk_percent
            }
        })
    except Exception as e:
        logger.error(f"Error getting system load: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@bp.route('/clients/<client_id>/test', methods=['GET'])
@login_required
def client_testing(client_id):
    """Show client testing page."""
    client = current_app.config_storage.get_client(client_id)
    if not client:
        flash('Client not found', 'error')
        return redirect(url_for('main.clients'))
    
    return render_template('client_testing.html', client_id=client_id, client=client)

@bp.route('/clients/<client_id>/handshake', methods=['GET'])
@login_required
def check_handshake(client_id):
    """Check the last handshake time for a client."""
    try:
        client = current_app.config_storage.get_client(client_id)
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        # Get interface name from config path
        interface_name = os.path.splitext(os.path.basename(client['config_path']))[0]
        
        # Get current handshake status
        status = WireGuardService.get_client_status(interface_name)
        if 'error' in status:
            return jsonify({
                'error': status['error'],
                'last_handshake': None
            }), 500
        
        # Update the last handshake in the database if available
        if status.get('last_handshake'):
            try:
                # Calculate the actual timestamp by subtracting the time ago from current time
                handshake_str = status['last_handshake']
                total_seconds = 0
                
                # Handle combined formats like "1 minute, 45 seconds ago"
                if ',' in handshake_str:
                    parts = handshake_str.split(',')
                    for part in parts:
                        part = part.strip()
                        if 'minute' in part:
                            minutes = int(part.split()[0])
                            total_seconds += minutes * 60
                        elif 'second' in part:
                            seconds = int(part.split()[0])
                            total_seconds += seconds
                else:
                    # Handle single unit formats
                    if 'seconds ago' in handshake_str:
                        total_seconds = int(handshake_str.split()[0])
                    elif 'minutes ago' in handshake_str:
                        total_seconds = int(handshake_str.split()[0]) * 60
                    elif 'hours ago' in handshake_str:
                        total_seconds = int(handshake_str.split()[0]) * 3600
                    elif 'days ago' in handshake_str:
                        total_seconds = int(handshake_str.split()[0]) * 86400
                
                handshake_time = datetime.utcnow() - timedelta(seconds=total_seconds)
                
                current_app.config_storage.update_client_status(
                    client_id,
                    client['status'],
                    handshake_time
                )
            except (ValueError, TypeError) as e:
                logger.error(f"Error parsing handshake time: {e}")
        
        return jsonify({
            'status': 'success',
            'last_handshake': status.get('last_handshake'),
            'connected': status.get('connected', False)
        })
        
    except Exception as e:
        logger.error(f"Error checking handshake: {e}")
        return jsonify({
            'error': str(e),
            'last_handshake': None
        }), 500

@bp.route('/api/ip-forwarding', methods=['GET'])
@login_required
def get_ip_forwarding_status():
    """Get the current IP forwarding status."""
    try:
        enabled = IPForwardingService.check_status()
        return jsonify({
            'status': 'success',
            'enabled': enabled
        })
    except Exception as e:
        logger.error(f"Error checking IP forwarding status: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/email-settings', methods=['GET', 'POST'])
@login_required
def email_settings():
    """Configure email alert settings."""
    form = EmailSettingsForm()
    
    if request.method == 'GET':
        # Load existing settings
        settings = EmailSettings.get_settings()
        if settings:
            form.smtp_host.data = settings.smtp_host
            form.smtp_port.data = settings.smtp_port
            form.smtp_username.data = settings.smtp_username
            form.smtp_from.data = settings.smtp_from
            form.smtp_use_tls.data = settings.smtp_use_tls
            form.alert_recipients.data = settings.alert_recipients
    
    if form.validate_on_submit():
        try:
            # Update settings
            EmailSettings.update_settings(
                smtp_host=form.smtp_host.data,
                smtp_port=form.smtp_port.data,
                smtp_username=form.smtp_username.data,
                smtp_password=form.smtp_password.data,
                smtp_from=form.smtp_from.data,
                smtp_use_tls=form.smtp_use_tls.data,
                alert_recipients=form.alert_recipients.data
            )
            
            # Update app config
            current_app.config.update({
                'SMTP_HOST': form.smtp_host.data,
                'SMTP_PORT': form.smtp_port.data,
                'SMTP_USERNAME': form.smtp_username.data,
                'SMTP_PASSWORD': form.smtp_password.data,
                'SMTP_FROM': form.smtp_from.data,
                'SMTP_USE_TLS': form.smtp_use_tls.data,
                'ALERT_RECIPIENTS': [email.strip() for email in form.alert_recipients.data.split(',')]
            })
            
            flash('Email settings updated successfully', 'success')
            return redirect(url_for('main.email_settings'))
            
        except Exception as e:
            logger.error(f"Error updating email settings: {e}")
            flash('Failed to update email settings', 'error')
    
    return render_template('email_settings.html', form=form)