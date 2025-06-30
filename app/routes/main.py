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
from app.models.alert_history import AlertHistory
from app.services.wireguard_monitor import WireGuardMonitor
from app.services.reboot_service import RebootService

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
            # Get client info before deletion
            client = current_app.config_storage.get_client(client_id)
            if not client:
                return jsonify({'status': 'error', 'error': 'Client not found'}), 404
            
            # First, try to deactivate the interface if it's running
            interface_name = os.path.splitext(os.path.basename(client['config_path']))[0]
            
            # Check if interface is active
            try:
                result = subprocess.run(['sudo', 'wg', 'show', interface_name], capture_output=True, text=True)
                if result.returncode == 0:
                    logger.info(f"Interface {interface_name} is active, bringing it down and cleaning up rules before deletion")
                    
                    # Clean up iptables rules first (using client subnet from database)
                    try:
                        from app.services.iptables_manager import IptablesManager
                        success, error = IptablesManager.cleanup_forwarding(interface_name, client['subnet'])
                        if success:
                            logger.info(f"Successfully cleaned up iptables rules for {interface_name}")
                        else:
                            logger.warning(f"Failed to cleanup iptables rules for {interface_name}: {error}")
                    except Exception as e:
                        logger.warning(f"Error cleaning up iptables rules for {interface_name}: {e}")
                    
                    # Try wg-quick down first
                    down_result = subprocess.run(['sudo', 'wg-quick', 'down', client['config_path']], capture_output=True, text=True)
                    if down_result.returncode != 0:
                        # Fallback to ip link delete if wg-quick fails
                        logger.warning(f"wg-quick down failed for {interface_name}, using ip link delete")
                        subprocess.run(['sudo', 'ip', 'link', 'delete', interface_name], capture_output=True, text=True)
                        
                        # If we used ip link delete, we still need to clean up any remaining rules
                        try:
                            IptablesManager.cleanup_forwarding(interface_name, client['subnet'])
                        except Exception as e:
                            logger.warning(f"Additional iptables cleanup failed: {e}")
            except Exception as e:
                logger.warning(f"Error stopping interface {interface_name} before deletion: {e}")
            
            # Now delete from database and filesystem
            current_app.config_storage.delete_client(client_id)
            logger.info(f"Successfully deleted client {client['name']} (ID: {client_id})")
            
            return jsonify({'status': 'success', 'message': 'Client deleted successfully'})
        except Exception as e:
            logger.exception(f"Error deleting client {client_id}")
            return jsonify({'status': 'error', 'error': str(e)}), 500
    else:
        try:
            client = current_app.config_storage.get_client(client_id)
            if not client:
                return jsonify({'status': 'error', 'error': 'Client not found'}), 404
            
            # Check actual system state and sync database if needed
            interface_name = os.path.splitext(os.path.basename(client['config_path']))[0]
            
            # Get actual WireGuard interfaces
            try:
                result = subprocess.run(['sudo', 'wg', 'show', 'interfaces'], capture_output=True, text=True)
                active_interfaces = set(result.stdout.strip().split()) if result.returncode == 0 else set()
                system_active = interface_name in active_interfaces
                system_status = 'active' if system_active else 'inactive'
                
                # If database status doesn't match system state, update database
                if client['status'] != system_status:
                    logger.info(f"Syncing client {client['name']} status: DB={client['status']} -> System={system_status}")
                    current_app.config_storage.update_client_status(client_id, system_status)
                    client['status'] = system_status
                    
            except Exception as e:
                logger.warning(f"Error checking system state for client {client_id}: {e}")
            
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
        
        # Check if config file exists
        if not os.path.exists(config_path):
            logger.error(f"Config file not found: {config_path}")
            return jsonify({
                'error': 'Configuration file not found',
                'details': f'Config file {config_path} does not exist'
            }), 404
        
        # Check if interface already exists
        interface_name = os.path.splitext(os.path.basename(config_path))[0]
        try:
            check_result = subprocess.run(['sudo', 'wg', 'show', interface_name], capture_output=True, text=True)
            if check_result.returncode == 0:
                logger.warning(f"Interface {interface_name} already exists, updating database status")
                current_app.config_storage.update_client_status(client_id, 'active')
                return jsonify({
                    'status': 'success',
                    'message': 'Client was already active, status updated'
                })
        except Exception as e:
            logger.debug(f"Error checking existing interface {interface_name}: {e}")
        
        logger.info(f"Attempting to activate client {client_id} with config: {config_path}")
        
        result = subprocess.run(
            ['sudo', 'wg-quick', 'up', config_path],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"Failed to activate client {client_id}: stdout={result.stdout}, stderr={result.stderr}")
            error_details = result.stderr if result.stderr else result.stdout
            
            # Provide specific error context
            context = {}
            if "File exists" in error_details:
                context['conflict_type'] = 'route_conflict'
                context['suggestion'] = 'Another interface is using the same route. Check for conflicts.'
            elif "Permission denied" in error_details:
                context['conflict_type'] = 'permission_error'
                context['suggestion'] = 'Check sudo permissions for WireGuard operations.'
            elif "No such file" in error_details:
                context['conflict_type'] = 'missing_dependency'
                context['suggestion'] = 'WireGuard tools may not be properly installed.'
            
            return jsonify({
                'error': 'Failed to activate client',
                'details': error_details,
                'command': f'wg-quick up {config_path}',
                'context': context
            }), 500
        
        # Update client status
        current_app.config_storage.update_client_status(client_id, 'active')
        logger.info(f"Successfully activated client {client_id}")
        
        return jsonify({
            'status': 'success',
            'message': 'Client activated successfully'
        })
    except Exception as e:
        logger.exception(f"Unexpected error activating client {client_id}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@bp.route('/clients/<client_id>/deactivate', methods=['POST'])
@login_required
def deactivate_client(client_id):
    """Deactivate a WireGuard client."""
    client = current_app.config_storage.get_client(client_id)
    if not client:
        return jsonify({'error': 'Client not found'}), 404
    
    try:
        # Check if interface is actually running
        interface_name = os.path.splitext(os.path.basename(client['config_path']))[0]
        try:
            check_result = subprocess.run(['sudo', 'wg', 'show', interface_name], capture_output=True, text=True)
            if check_result.returncode != 0:
                # Interface not running, just update database
                logger.info(f"Interface {interface_name} not running, updating database status")
                current_app.config_storage.update_client_status(client_id, 'inactive')
                return jsonify({
                    'status': 'success',
                    'message': 'Client was already inactive, status updated'
                })
        except Exception as e:
            logger.debug(f"Error checking interface {interface_name}: {e}")
        
        # Run wg-quick down with sudo
        config_path = client['config_path']
        logger.info(f"Attempting to deactivate client {client_id} with config: {config_path}")
        
        result = subprocess.run(
            ['sudo', 'wg-quick', 'down', config_path],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            # If wg-quick fails, try ip link delete as fallback
            logger.warning(f"wg-quick down failed for {interface_name}, trying ip link delete")
            fallback_result = subprocess.run(['sudo', 'ip', 'link', 'delete', interface_name], capture_output=True, text=True)
            
            if fallback_result.returncode != 0:
                logger.error(f"Failed to deactivate client {client_id}: wg-quick stderr={result.stderr}, ip link stderr={fallback_result.stderr}")
                return jsonify({
                    'error': 'Failed to deactivate client',
                    'details': f"wg-quick: {result.stderr}, ip link: {fallback_result.stderr}",
                    'command': f'wg-quick down {config_path}'
                }), 500
            else:
                logger.info(f"Successfully deactivated {interface_name} using ip link delete")
        
        # Clean up any iptables rules that might be left behind
        try:
            from app.services.iptables_manager import IptablesManager
            success, error = IptablesManager.cleanup_forwarding(interface_name, client['subnet'])
            if success:
                logger.info(f"Successfully cleaned up iptables rules for {interface_name}")
            else:
                logger.warning(f"Failed to cleanup iptables rules for {interface_name}: {error}")
        except Exception as e:
            logger.warning(f"Error cleaning up iptables rules for {interface_name}: {e}")
        
        # Update client status
        current_app.config_storage.update_client_status(client_id, 'inactive')
        logger.info(f"Successfully deactivated client {client_id}")
        
        return jsonify({
            'status': 'success',
            'message': 'Client deactivated successfully'
        })
    except Exception as e:
        logger.exception(f"Unexpected error deactivating client {client_id}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

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
        success, error = IptablesManager.setup_forwarding(interface_name, client['subnet'])
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
        success, error = IptablesManager.cleanup_forwarding(interface_name, client['subnet'])
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
    """Get all clients with real-time system state."""
    try:
        # Get clients from database
        db_clients = current_app.config_storage.list_clients()
        
        # Get actual WireGuard interfaces
        try:
            result = subprocess.run(['sudo', 'wg', 'show', 'interfaces'], capture_output=True, text=True)
            active_interfaces = set(result.stdout.strip().split()) if result.returncode == 0 else set()
        except Exception as e:
            logger.warning(f"Failed to get WireGuard interfaces: {e}")
            active_interfaces = set()
        
        # Merge database data with system reality
        clients = []
        for client in db_clients:
            interface_name = os.path.splitext(os.path.basename(client['config_path']))[0]
            
            # Determine actual status from system
            system_active = interface_name in active_interfaces
            
            # Create enhanced client object
            enhanced_client = client.copy()
            enhanced_client['system_status'] = 'active' if system_active else 'inactive'
            enhanced_client['interface_name'] = interface_name
            
            # If there's a mismatch, log it
            if client['status'] != enhanced_client['system_status']:
                logger.info(f"Status mismatch for {client['name']}: DB={client['status']}, System={enhanced_client['system_status']}")
                # Update database to match system reality
                current_app.config_storage.update_client_status(client['id'], enhanced_client['system_status'])
                enhanced_client['status'] = enhanced_client['system_status']
            
            clients.append(enhanced_client)
        
        return jsonify({
            'status': 'success',
            'clients': clients,
            'active_interfaces': list(active_interfaces)
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
            logger.info(f"Loading existing email settings: host={settings.smtp_host}, port={settings.smtp_port}, from={settings.smtp_from}")
            form.smtp_host.data = settings.smtp_host
            form.smtp_port.data = settings.smtp_port
            form.smtp_username.data = settings.smtp_username
            form.smtp_from.data = settings.smtp_from
            form.smtp_use_tls.data = settings.smtp_use_tls
            form.alert_recipients.data = settings.alert_recipients
        else:
            logger.info("No existing email settings found")
    
    if form.validate_on_submit():
        try:
            logger.info("Saving new email settings")
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
            
            logger.info("Email settings updated successfully")
            flash('Email settings updated successfully', 'success')
            return redirect(url_for('main.email_settings'))
            
        except Exception as e:
            logger.error(f"Error updating email settings: {e}")
            flash('Failed to update email settings', 'error')
    
    return render_template('email_settings.html', form=form)

@bp.route('/email-settings/test', methods=['POST'])
@login_required
def test_email_settings():
    """Send a test email to verify SMTP settings."""
    try:
        logger.info("Attempting to send test email")
        # Send test email
        success = EmailService.send_alert(
            subject="Test Alert",
            message="This is a test email to verify your SMTP settings are working correctly.",
            is_html=False
        )
        
        if success:
            logger.info("Test email sent successfully")
            flash('Test email sent successfully!', 'success')
        else:
            logger.error("Failed to send test email")
            flash('Failed to send test email. Please check your SMTP settings.', 'error')
            
    except Exception as e:
        logger.error(f"Error sending test email: {e}")
        flash(f'Error sending test email: {str(e)}', 'error')
    
    return redirect(url_for('main.email_settings'))

@bp.route('/api/monitoring/status')
@login_required
def get_monitoring_status():
    """Get current connection status for all clients from the database."""
    try:
        clients = current_app.config_storage.list_clients()
        status = {}
        for client in clients:
            # Get interface name from config path
            config_path = client.get('config_path')
            if config_path:
                interface = os.path.splitext(os.path.basename(config_path))[0]
                # Get current handshake status
                peers = WireGuardMonitor.check_interface(interface)
                last_handshake = None
                for peer, is_connected in peers.items():
                    if is_connected and peer in WireGuardMonitor._last_handshakes:
                        last_handshake = WireGuardMonitor._last_handshakes[peer]
                        break
            else:
                interface = None
                last_handshake = None

            status[client['id']] = {
                'name': client['name'],
                'connected': client['status'] == 'active',
                'last_handshake': last_handshake.isoformat() if last_handshake else None,
                'last_alert': None  # You can enhance this to fetch from alert history if needed
            }
        return jsonify({
            'status': 'success',
            'data': {
                'status': status
            }
        })
    except Exception as e:
        logger.error(f"Error getting monitoring status: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/api/monitoring/test', methods=['POST'])
@login_required
def test_monitoring():
    """Manually trigger connection checks and alerts for testing."""
    try:
        # Get all active clients
        clients = current_app.config_storage.list_clients()
        results = []
        for client in clients:
            if client.get('status') == 'active':
                # Derive interface name from config_path
                config_path = client.get('config_path')
                if config_path:
                    interface = os.path.splitext(os.path.basename(config_path))[0]
                else:
                    interface = None
                client_name = client.get('name', 'Unknown')
                if interface:
                    # Force check and alert
                    WireGuardMonitor.check_and_alert(interface, client_name)
                    results.append({
                        'client': client_name,
                        'interface': interface,
                        'status': 'checked'
                    })
        return jsonify({
            'status': 'success',
            'message': 'Connection checks triggered',
            'results': results
        })
    except Exception as e:
        logger.error(f"Error in test monitoring: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/monitoring')
@login_required
def monitoring():
    """Show monitoring page."""
    return render_template('monitoring.html')

@bp.route('/ddns-monitoring')
@login_required
def ddns_monitoring():
    """Show DDNS monitoring page."""
    return render_template('ddns_monitoring.html')

@bp.route('/api/monitoring/alerts')
@login_required
def get_alert_history():
    """Get alert history for the monitoring page."""
    try:
        # Get alerts from the database
        alerts = AlertHistory.query.order_by(AlertHistory.sent_at.desc()).limit(100).all()
        
        return jsonify({
            'status': 'success',
            'alerts': [{
                'timestamp': alert.sent_at.isoformat(),
                'client_name': alert.client_name,
                'subject': alert.subject,
                'success': alert.success
            } for alert in alerts]
        })
    except Exception as e:
        logger.error(f"Error getting alert history: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/system/reboot', methods=['POST'])
@login_required
@rate_limit(max_requests=2, time_window=60)
def reboot_system():
    """Endpoint to reboot the server."""
    success, error = RebootService.reboot()
    if success:
        return jsonify({'status': 'success', 'message': 'Reboot initiated'}), 200
    else:
        return jsonify({'status': 'error', 'message': error or 'Failed to reboot'}), 500

# New DNS and Auto-Reconnect API endpoints

@bp.route('/api/dns/status')
@login_required
def get_dns_status():
    """Get DNS resolution status for all monitored hostnames."""
    try:
        from app.services.dns_resolver import DNSResolver
        status = DNSResolver.get_hostname_status()
        return jsonify({
            'status': 'success',
            'dns_status': status
        })
    except Exception as e:
        logger.error(f"Error getting DNS status: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/api/auto-reconnect/status')
@login_required
def get_auto_reconnect_status():
    """Get auto-reconnection status for all clients."""
    try:
        from app.services.auto_reconnect import AutoReconnectService
        status = AutoReconnectService.get_reconnection_status()
        return jsonify({
            'status': 'success',
            'reconnect_status': status
        })
    except Exception as e:
        logger.error(f"Error getting auto-reconnect status: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/api/auto-reconnect/clear-history', methods=['POST'])
@login_required
def clear_reconnect_history():
    """Clear all auto-reconnection history."""
    try:
        from app.services.auto_reconnect import AutoReconnectService
        AutoReconnectService.clear_all_reconnection_history()
        return jsonify({
            'status': 'success',
            'message': 'Reconnection history cleared'
        })
    except Exception as e:
        logger.error(f"Error clearing reconnection history: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/api/auto-reconnect/clear-client/<client_id>', methods=['POST'])
@login_required
def clear_client_reconnect_history(client_id):
    """Clear auto-reconnection history for a specific client."""
    try:
        from app.services.auto_reconnect import AutoReconnectService
        AutoReconnectService.clear_reconnection_history(client_id)
        return jsonify({
            'status': 'success',
            'message': f'Reconnection history cleared for client {client_id}'
        })
    except Exception as e:
        logger.error(f"Error clearing reconnection history for client {client_id}: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/api/auto-reconnect/manual-reconnect/<client_id>', methods=['POST'])
@login_required
def manual_reconnect_client(client_id):
    """Manually trigger a reconnection for a specific client."""
    try:
        from app.services.auto_reconnect import AutoReconnectService
        
        # Get client information
        client = current_app.config_storage.get_client(client_id)
        if not client:
            return jsonify({
                'status': 'error',
                'message': 'Client not found'
            }), 404
        
        # Trigger manual reconnection
        success = AutoReconnectService._reconnect_client(client, current_app.config_storage)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': f'Manual reconnection initiated for client {client["name"]}'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'Failed to reconnect client {client["name"]}'
            }), 500
            
    except Exception as e:
        logger.error(f"Error during manual reconnection of client {client_id}: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/api/system/cleanup-duplicates', methods=['POST'])
@login_required  
def cleanup_duplicate_clients():
    """Remove duplicate clients with the same public key, keeping the most recent."""
    try:
        clients = current_app.config_storage.list_clients()
        
        # Group clients by public key
        clients_by_key = {}
        for client in clients:
            key = client['public_key']
            if key not in clients_by_key:
                clients_by_key[key] = []
            clients_by_key[key].append(client)
        
        # Find duplicates
        duplicates_removed = 0
        for public_key, client_list in clients_by_key.items():
            if len(client_list) > 1:
                # Sort by created_at, keep the most recent
                client_list.sort(key=lambda x: x['created_at'], reverse=True)
                to_keep = client_list[0]
                to_remove = client_list[1:]
                
                logger.info(f"Found {len(client_list)} clients with same public key {public_key[:16]}...")
                logger.info(f"Keeping: {to_keep['name']} (created: {to_keep['created_at']})")
                
                for client in to_remove:
                    logger.info(f"Removing duplicate: {client['name']} (created: {client['created_at']})")
                    try:
                        current_app.config_storage.delete_client(client['id'])
                        duplicates_removed += 1
                    except Exception as e:
                        logger.error(f"Failed to delete duplicate client {client['id']}: {e}")
        
        return jsonify({
            'status': 'success',
            'message': f'Removed {duplicates_removed} duplicate clients',
            'duplicates_removed': duplicates_removed
        })
        
    except Exception as e:
        logger.exception("Error cleaning up duplicate clients")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/api/system/sync', methods=['POST'])
@login_required
def sync_system_state():
    """Synchronize database state with actual WireGuard interfaces."""
    try:
        # Get actual WireGuard interfaces
        result = subprocess.run(
            ['sudo', 'wg', 'show', 'interfaces'],
            capture_output=True,
            text=True
        )
        
        active_interfaces = set()
        if result.returncode == 0:
            active_interfaces = set(result.stdout.strip().split())
        
        # Get all clients from database
        clients = current_app.config_storage.list_clients()
        
        updated_count = 0
        for client in clients:
            # Get interface name from config path
            interface_name = os.path.splitext(os.path.basename(client['config_path']))[0]
            
            # Check if interface is actually active
            is_active = interface_name in active_interfaces
            expected_status = 'active' if is_active else 'inactive'
            
            # Update status if it doesn't match
            if client['status'] != expected_status:
                current_app.config_storage.update_client_status(client['id'], expected_status)
                updated_count += 1
                logger.info(f"Updated client {client['name']} status from {client['status']} to {expected_status}")
        
        return jsonify({
            'status': 'success',
            'message': f'Synchronized system state. Updated {updated_count} clients.',
            'active_interfaces': list(active_interfaces),
            'total_clients': len(clients)
        })
        
    except Exception as e:
        logger.exception("Error synchronizing system state")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500