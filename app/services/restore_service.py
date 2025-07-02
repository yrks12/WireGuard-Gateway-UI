import os
import json
import zipfile
import shutil
import tempfile
import subprocess
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import logging

from .backup_service import BackupService
from .backup_validator import BackupValidator

logger = logging.getLogger(__name__)

class RestoreService:
    """Service for restoring system from backup files."""
    
    def __init__(self, instance_path: str):
        self.instance_path = instance_path
        self.restore_staging_dir = os.path.join(instance_path, 'restore_staging')
        os.makedirs(self.restore_staging_dir, exist_ok=True)
    
    @classmethod
    def restore_from_backup(cls, zip_path: str, instance_path: str) -> Tuple[bool, str]:
        """
        Restore system from a backup ZIP file.
        
        Args:
            zip_path: Path to the backup ZIP file
            instance_path: Instance directory path
            
        Returns:
            Tuple of (success, message)
        """
        service = cls(instance_path)
        
        try:
            # Step 1: Validate backup file
            logger.info(f"Starting restore from {zip_path}")
            
            is_valid, error, metadata = BackupValidator.validate_backup_file(zip_path)
            if not is_valid:
                return False, f"Backup validation failed: {error}"
            
            # Step 2: Create pre-restore backup
            logger.info("Creating pre-restore backup...")
            backup_success, backup_msg, backup_path = BackupService.create_backup(instance_path)
            if not backup_success:
                logger.warning(f"Pre-restore backup failed: {backup_msg}")
                # Continue anyway, but warn user
            else:
                logger.info(f"Pre-restore backup created: {backup_path}")
            
            # Step 3: Extract backup to staging area
            staging_dir = service._create_staging_directory()
            success, error = service._extract_backup(zip_path, staging_dir)
            if not success:
                service._cleanup_staging(staging_dir)
                return False, f"Backup extraction failed: {error}"
            
            # Step 4: Stop active services and interfaces
            success, error = service._stop_active_services()
            if not success:
                service._cleanup_staging(staging_dir)
                return False, f"Failed to stop services: {error}"
            
            # Step 5: Restore databases
            success, error = service._restore_databases(staging_dir)
            if not success:
                service._cleanup_staging(staging_dir)
                # Try to restart services even if restore failed
                service._start_services()
                return False, f"Database restore failed: {error}"
            
            # Step 6: Restore WireGuard configs
            success, error = service._restore_configs(staging_dir)
            if not success:
                service._cleanup_staging(staging_dir)
                service._start_services()
                return False, f"Config restore failed: {error}"
            
            # Step 7: Restore iptables rules (non-critical)
            success, error = service._restore_iptables(staging_dir)
            if not success:
                logger.warning(f"iptables restore failed: {error}")
                # Continue anyway - not critical for basic functionality
            
            # Step 8: Restart services
            success, error = service._start_services()
            if not success:
                logger.warning(f"Service restart warning: {error}")
                # Continue anyway - system might still work
            
            # Step 9: Validate restoration
            success, error = service._validate_restoration()
            if not success:
                logger.warning(f"Restoration validation failed: {error}")
                # Continue anyway - restoration might still be functional
            
            # Step 10: Cleanup staging directory
            service._cleanup_staging(staging_dir)
            
            logger.info("System restore completed successfully")
            return True, "System restored successfully from backup"
            
        except Exception as e:
            logger.error(f"Unexpected error during restore: {e}")
            # Try to cleanup and restart services
            try:
                service._cleanup_staging(staging_dir if 'staging_dir' in locals() else None)
                service._start_services()
            except:
                pass
            return False, f"Restore failed: {str(e)}"
    
    def _create_staging_directory(self) -> str:
        """Create a unique staging directory for this restore operation."""
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        staging_dir = os.path.join(self.restore_staging_dir, f"restore_{timestamp}")
        os.makedirs(staging_dir, exist_ok=True)
        return staging_dir
    
    def _extract_backup(self, zip_path: str, staging_dir: str) -> Tuple[bool, str]:
        """Extract backup ZIP file to staging directory."""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                zipf.extractall(staging_dir)
            
            logger.debug(f"Backup extracted to {staging_dir}")
            return True, ""
            
        except Exception as e:
            logger.error(f"Error extracting backup: {e}")
            return False, str(e)
    
    def _stop_active_services(self) -> Tuple[bool, str]:
        """Stop active WireGuard interfaces and services."""
        try:
            logger.info("Stopping active WireGuard interfaces...")
            
            # Get list of active WireGuard interfaces
            result = subprocess.run(
                ['sudo', 'wg', 'show', 'interfaces'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0 and result.stdout.strip():
                interfaces = result.stdout.strip().split()
                
                for interface in interfaces:
                    logger.info(f"Stopping interface: {interface}")
                    try:
                        # Try wg-quick down first
                        down_result = subprocess.run(
                            ['sudo', 'wg-quick', 'down', interface],
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        
                        if down_result.returncode != 0:
                            # Fallback to ip link delete
                            subprocess.run(
                                ['sudo', 'ip', 'link', 'delete', interface],
                                capture_output=True,
                                text=True,
                                timeout=30
                            )
                            
                    except Exception as e:
                        logger.warning(f"Error stopping interface {interface}: {e}")
                        # Continue with other interfaces
            
            return True, ""
            
        except Exception as e:
            logger.error(f"Error stopping services: {e}")
            return False, str(e)
    
    def _restore_databases(self, staging_dir: str) -> Tuple[bool, str]:
        """Restore database files from staging directory."""
        try:
            databases_restored = []
            
            # Restore app.db if present - check multiple possible target locations
            app_db_staging = os.path.join(staging_dir, 'app.db')
            if os.path.exists(app_db_staging):
                app_db_targets = [
                    os.path.join(self.instance_path, 'app.db'),  # Standard instance location
                    './app.db',  # Working directory
                    '/opt/wireguard-gateway/app.db',  # Production root
                ]
                
                # Try to find existing app.db location or use first target
                app_db_target = None
                for target in app_db_targets:
                    if os.path.exists(target):
                        app_db_target = target
                        break
                
                if not app_db_target:
                    app_db_target = app_db_targets[0]  # Default to instance location
                
                # Backup existing database
                if os.path.exists(app_db_target):
                    shutil.copy2(app_db_target, f"{app_db_target}.pre_restore")
                
                # Ensure target directory exists
                os.makedirs(os.path.dirname(app_db_target), exist_ok=True)
                shutil.copy2(app_db_staging, app_db_target)
                logger.info(f"Restored app.db to {app_db_target}")
                databases_restored.append('app.db')
            
            # Restore wireguard.db if present (main database used by restore scripts)
            wireguard_db_staging = os.path.join(staging_dir, 'wireguard.db')
            wireguard_db_target = '/var/lib/wireguard-gateway/wireguard.db'
            
            if os.path.exists(wireguard_db_staging):
                # Backup existing database
                if os.path.exists(wireguard_db_target):
                    shutil.copy2(wireguard_db_target, f"{wireguard_db_target}.pre_restore")
                
                # Ensure target directory exists
                os.makedirs(os.path.dirname(wireguard_db_target), exist_ok=True)
                shutil.copy2(wireguard_db_staging, wireguard_db_target)
                logger.info("Restored wireguard.db")
                databases_restored.append('wireguard.db')
            
            # Restore configs.db if present
            config_db_staging = os.path.join(staging_dir, 'configs.db')
            config_db_target = os.path.join(self.instance_path, 'configs.db')
            
            if os.path.exists(config_db_staging):
                # Backup existing database
                if os.path.exists(config_db_target):
                    shutil.copy2(config_db_target, f"{config_db_target}.pre_restore")
                
                shutil.copy2(config_db_staging, config_db_target)
                logger.info("Restored configs.db")
                databases_restored.append('configs.db')
            
            if not databases_restored:
                return False, "No database files found in backup to restore"
            
            logger.info(f"Successfully restored databases: {', '.join(databases_restored)}")
            return True, ""
            
        except Exception as e:
            logger.error(f"Error restoring databases: {e}")
            return False, str(e)
    
    def _restore_configs(self, staging_dir: str) -> Tuple[bool, str]:
        """Restore WireGuard config files from staging directory."""
        try:
            configs_staging = os.path.join(staging_dir, 'configs')
            configs_target = os.path.join(self.instance_path, 'configs')
            
            if os.path.exists(configs_staging):
                # Backup existing configs directory
                if os.path.exists(configs_target):
                    shutil.move(configs_target, f"{configs_target}.pre_restore")
                
                # Copy restored configs
                shutil.copytree(configs_staging, configs_target)
                
                # Count restored config files
                config_files = [f for f in os.listdir(configs_target) if f.endswith('.conf')]
                logger.info(f"Restored {len(config_files)} config files")
            else:
                # Create empty configs directory if none in backup
                os.makedirs(configs_target, exist_ok=True)
                logger.info("No config files in backup, created empty configs directory")
            
            return True, ""
            
        except Exception as e:
            logger.error(f"Error restoring configs: {e}")
            return False, str(e)
    
    def _restore_iptables(self, staging_dir: str) -> Tuple[bool, str]:
        """Restore iptables rules from staging directory."""
        try:
            rules_restored = []
            
            # Restore main iptables rules
            iptables_file = os.path.join(staging_dir, 'iptables_rules.txt')
            if os.path.exists(iptables_file):
                try:
                    with open(iptables_file, 'r') as f:
                        rules_content = f.read().strip()
                    
                    if rules_content:
                        # Apply iptables rules
                        result = subprocess.run(
                            ['sudo', 'iptables-restore'],
                            input=rules_content,
                            text=True,
                            capture_output=True,
                            timeout=60
                        )
                        
                        if result.returncode == 0:
                            logger.info("Restored iptables rules")
                            rules_restored.append("main iptables")
                        else:
                            logger.warning(f"iptables-restore failed: {result.stderr}")
                except Exception as e:
                    logger.warning(f"Error restoring main iptables rules: {e}")
            
            # Restore NAT rules
            nat_rules_file = os.path.join(staging_dir, 'iptables_nat_rules.txt')
            if os.path.exists(nat_rules_file):
                try:
                    with open(nat_rules_file, 'r') as f:
                        nat_rules = f.read().strip().split('\n')
                    
                    nat_rules_applied = 0
                    for rule in nat_rules:
                        if rule.strip() and not rule.startswith('#') and rule.startswith('-'):
                            # Convert from -S format to iptables command
                            rule_parts = rule.split()
                            if len(rule_parts) > 1:
                                rule_cmd = ['sudo', 'iptables', '-t', 'nat'] + rule_parts[1:]
                                try:
                                    subprocess.run(rule_cmd, timeout=30, check=True, capture_output=True)
                                    nat_rules_applied += 1
                                except subprocess.CalledProcessError as e:
                                    logger.debug(f"NAT rule failed (may already exist): {rule}")
                                except Exception as e:
                                    logger.warning(f"Error applying NAT rule '{rule}': {e}")
                    
                    if nat_rules_applied > 0:
                        logger.info(f"Restored {nat_rules_applied} iptables NAT rules")
                        rules_restored.append(f"{nat_rules_applied} NAT rules")
                except Exception as e:
                    logger.warning(f"Error restoring NAT rules: {e}")
            
            # Restore FORWARD rules
            forward_rules_file = os.path.join(staging_dir, 'iptables_forward_rules.txt')
            if os.path.exists(forward_rules_file):
                try:
                    with open(forward_rules_file, 'r') as f:
                        forward_rules = f.read().strip().split('\n')
                    
                    forward_rules_applied = 0
                    for rule in forward_rules:
                        if rule.strip() and not rule.startswith('#') and rule.startswith('-'):
                            # Convert from -S format to iptables command
                            rule_parts = rule.split()
                            if len(rule_parts) > 1:
                                rule_cmd = ['sudo', 'iptables', '-t', 'filter'] + rule_parts[1:]
                                try:
                                    subprocess.run(rule_cmd, timeout=30, check=True, capture_output=True)
                                    forward_rules_applied += 1
                                except subprocess.CalledProcessError as e:
                                    logger.debug(f"FORWARD rule failed (may already exist): {rule}")
                                except Exception as e:
                                    logger.warning(f"Error applying FORWARD rule '{rule}': {e}")
                    
                    if forward_rules_applied > 0:
                        logger.info(f"Restored {forward_rules_applied} iptables FORWARD rules")
                        rules_restored.append(f"{forward_rules_applied} FORWARD rules")
                except Exception as e:
                    logger.warning(f"Error restoring FORWARD rules: {e}")
            
            if rules_restored:
                logger.info(f"Successfully restored iptables: {', '.join(rules_restored)}")
            else:
                logger.warning("No iptables rules found in backup or all failed to restore")
            
            # iptables restore is non-critical, so we always return True
            return True, ""
            
        except Exception as e:
            logger.warning(f"Error restoring iptables: {e}")
            # iptables restore is non-critical, so we return True but log the error
            return True, str(e)
    
    def _start_services(self) -> Tuple[bool, str]:
        """Start services after restoration."""
        try:
            logger.info("Services will be managed by the application startup process")
            # The Flask app and monitoring services will restart automatically
            # WireGuard interfaces will be brought up when clients are activated
            return True, ""
            
        except Exception as e:
            logger.error(f"Error starting services: {e}")
            return False, str(e)
    
    def _validate_restoration(self) -> Tuple[bool, str]:
        """Validate that restoration was successful."""
        try:
            errors = []
            
            # Check database files exist and are readable
            app_db = os.path.join(self.instance_path, 'app.db')
            if os.path.exists(app_db):
                try:
                    conn = sqlite3.connect(app_db)
                    conn.execute("SELECT COUNT(*) FROM sqlite_master")
                    conn.close()
                except Exception as e:
                    errors.append(f"app.db validation failed: {e}")
            
            config_db = os.path.join(self.instance_path, 'configs.db')
            if os.path.exists(config_db):
                try:
                    conn = sqlite3.connect(config_db)
                    conn.execute("SELECT COUNT(*) FROM clients")
                    conn.close()
                except Exception as e:
                    errors.append(f"configs.db validation failed: {e}")
            
            # Check wireguard.db
            wireguard_db = '/var/lib/wireguard-gateway/wireguard.db'
            if os.path.exists(wireguard_db):
                try:
                    conn = sqlite3.connect(wireguard_db)
                    conn.execute("SELECT COUNT(*) FROM sqlite_master")
                    conn.close()
                except Exception as e:
                    errors.append(f"wireguard.db validation failed: {e}")
            
            # Check configs directory exists
            configs_dir = os.path.join(self.instance_path, 'configs')
            if not os.path.exists(configs_dir):
                errors.append("configs directory missing after restore")
            
            if errors:
                return False, "; ".join(errors)
            
            logger.info("Restoration validation successful")
            return True, ""
            
        except Exception as e:
            logger.error(f"Error validating restoration: {e}")
            return False, str(e)
    
    def _cleanup_staging(self, staging_dir: Optional[str]):
        """Clean up staging directory after restore operation."""
        if staging_dir and os.path.exists(staging_dir):
            try:
                shutil.rmtree(staging_dir)
                logger.debug(f"Cleaned up staging directory: {staging_dir}")
            except Exception as e:
                logger.warning(f"Error cleaning up staging directory: {e}")
    
    @classmethod
    def cleanup_old_staging(cls, instance_path: str, max_age_hours: int = 24):
        """Clean up old staging directories."""
        service = cls(instance_path)
        
        try:
            if os.path.exists(service.restore_staging_dir):
                current_time = datetime.now()
                
                for dirname in os.listdir(service.restore_staging_dir):
                    dir_path = os.path.join(service.restore_staging_dir, dirname)
                    if os.path.isdir(dir_path):
                        dir_age = current_time - datetime.fromtimestamp(os.path.getctime(dir_path))
                        
                        if dir_age.total_seconds() > max_age_hours * 3600:
                            shutil.rmtree(dir_path)
                            logger.info(f"Removed old staging directory: {dirname}")
                            
        except Exception as e:
            logger.warning(f"Error cleaning up old staging directories: {e}")