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

logger = logging.getLogger(__name__)

class BackupService:
    """Service for creating and managing system backups."""
    
    BACKUP_VERSION = "1.0"
    MAX_BACKUP_AGE_DAYS = 7
    
    def __init__(self, instance_path: str):
        self.instance_path = instance_path
        self.backups_dir = os.path.join(instance_path, 'backups')
        os.makedirs(self.backups_dir, exist_ok=True)
    
    @classmethod
    def create_backup(cls, instance_path: str) -> Tuple[bool, str, Optional[str]]:
        """
        Create a complete system backup.
        
        Returns:
            Tuple of (success, message, backup_file_path)
        """
        service = cls(instance_path)
        
        try:
            # Create timestamp for backup
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            backup_name = f"wireguard_backup_{timestamp}"
            
            # Create temporary backup directory
            temp_backup_dir = os.path.join(service.backups_dir, backup_name)
            os.makedirs(temp_backup_dir, exist_ok=True)
            
            logger.info(f"Starting backup creation in {temp_backup_dir}")
            
            # Step 1: Copy database files
            success, error = service._backup_databases(temp_backup_dir)
            if not success:
                shutil.rmtree(temp_backup_dir, ignore_errors=True)
                return False, f"Database backup failed: {error}", None
            
            # Step 2: Copy WireGuard config files
            success, error = service._backup_configs(temp_backup_dir)
            if not success:
                shutil.rmtree(temp_backup_dir, ignore_errors=True)
                return False, f"Config backup failed: {error}", None
            
            # Step 3: Export iptables rules
            success, error = service._backup_iptables(temp_backup_dir)
            if not success:
                # Non-critical - continue with warning
                logger.warning(f"iptables backup failed: {error}")
            
            # Step 4: Create metadata file
            success, error = service._create_backup_metadata(temp_backup_dir, timestamp)
            if not success:
                shutil.rmtree(temp_backup_dir, ignore_errors=True)
                return False, f"Metadata creation failed: {error}", None
            
            # Step 5: Create ZIP archive
            zip_path = f"{temp_backup_dir}.zip"
            success, error = service._create_zip_archive(temp_backup_dir, zip_path)
            if not success:
                shutil.rmtree(temp_backup_dir, ignore_errors=True)
                return False, f"ZIP creation failed: {error}", None
            
            # Step 6: Cleanup temporary directory
            shutil.rmtree(temp_backup_dir, ignore_errors=True)
            
            # Step 7: Cleanup old backups
            service._cleanup_old_backups()
            
            logger.info(f"Backup created successfully: {zip_path}")
            return True, "Backup created successfully", zip_path
            
        except Exception as e:
            logger.error(f"Unexpected error during backup creation: {e}")
            return False, f"Backup creation failed: {str(e)}", None
    
    def _backup_databases(self, backup_dir: str) -> Tuple[bool, str]:
        """Copy database files to backup directory."""
        try:
            # Copy Flask app database
            app_db_path = os.path.join(self.instance_path, 'app.db')
            if os.path.exists(app_db_path):
                shutil.copy2(app_db_path, os.path.join(backup_dir, 'app.db'))
                logger.debug("Copied app.db to backup")
            
            # Copy config storage database
            config_db_path = os.path.join(self.instance_path, 'configs.db')
            if os.path.exists(config_db_path):
                shutil.copy2(config_db_path, os.path.join(backup_dir, 'configs.db'))
                logger.debug("Copied configs.db to backup")
            
            return True, ""
            
        except Exception as e:
            logger.error(f"Error backing up databases: {e}")
            return False, str(e)
    
    def _backup_configs(self, backup_dir: str) -> Tuple[bool, str]:
        """Copy WireGuard config files to backup directory."""
        try:
            configs_src = os.path.join(self.instance_path, 'configs')
            configs_dst = os.path.join(backup_dir, 'configs')
            
            if os.path.exists(configs_src) and os.listdir(configs_src):
                shutil.copytree(configs_src, configs_dst)
                config_count = len([f for f in os.listdir(configs_dst) if f.endswith('.conf')])
                logger.debug(f"Copied {config_count} config files to backup")
            else:
                # Create empty configs directory
                os.makedirs(configs_dst)
                logger.debug("No config files found, created empty configs directory")
            
            return True, ""
            
        except Exception as e:
            logger.error(f"Error backing up configs: {e}")
            return False, str(e)
    
    def _backup_iptables(self, backup_dir: str) -> Tuple[bool, str]:
        """Export current iptables rules to backup directory."""
        try:
            # Export main iptables rules
            result = subprocess.run(
                ['sudo', 'iptables-save'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                with open(os.path.join(backup_dir, 'iptables_rules.txt'), 'w') as f:
                    f.write(result.stdout)
                logger.debug("Exported iptables rules to backup")
            else:
                logger.warning(f"iptables-save failed: {result.stderr}")
                return False, f"iptables-save failed: {result.stderr}"
            
            # Export NAT table rules
            result = subprocess.run(
                ['sudo', 'iptables', '-t', 'nat', '-S'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                with open(os.path.join(backup_dir, 'iptables_nat_rules.txt'), 'w') as f:
                    f.write(result.stdout)
                logger.debug("Exported iptables NAT rules to backup")
            else:
                logger.warning(f"iptables NAT export failed: {result.stderr}")
            
            return True, ""
            
        except subprocess.TimeoutExpired:
            return False, "iptables export timed out"
        except Exception as e:
            logger.error(f"Error backing up iptables: {e}")
            return False, str(e)
    
    def _create_backup_metadata(self, backup_dir: str, timestamp: str) -> Tuple[bool, str]:
        """Create backup metadata file."""
        try:
            # Collect system information
            metadata = {
                'backup_version': self.BACKUP_VERSION,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'timestamp': timestamp,
                'system_info': {
                    'platform': os.name,
                    'instance_path': self.instance_path
                },
                'contents': {
                    'databases': [],
                    'configs': [],
                    'iptables_rules': []
                }
            }
            
            # Check what files we actually backed up
            if os.path.exists(os.path.join(backup_dir, 'app.db')):
                metadata['contents']['databases'].append('app.db')
            
            if os.path.exists(os.path.join(backup_dir, 'configs.db')):
                metadata['contents']['databases'].append('configs.db')
            
            configs_dir = os.path.join(backup_dir, 'configs')
            if os.path.exists(configs_dir):
                config_files = [f for f in os.listdir(configs_dir) if f.endswith('.conf')]
                metadata['contents']['configs'] = config_files
            
            if os.path.exists(os.path.join(backup_dir, 'iptables_rules.txt')):
                metadata['contents']['iptables_rules'].append('iptables_rules.txt')
            
            if os.path.exists(os.path.join(backup_dir, 'iptables_nat_rules.txt')):
                metadata['contents']['iptables_rules'].append('iptables_nat_rules.txt')
            
            # Write metadata file
            metadata_path = os.path.join(backup_dir, 'backup_metadata.json')
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.debug("Created backup metadata file")
            return True, ""
            
        except Exception as e:
            logger.error(f"Error creating backup metadata: {e}")
            return False, str(e)
    
    def _create_zip_archive(self, source_dir: str, zip_path: str) -> Tuple[bool, str]:
        """Create ZIP archive from backup directory."""
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(source_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Create relative path for ZIP archive
                        arcname = os.path.relpath(file_path, source_dir)
                        zipf.write(file_path, arcname)
            
            # Verify ZIP file was created and has content
            if os.path.exists(zip_path) and os.path.getsize(zip_path) > 0:
                logger.debug(f"Created ZIP archive: {zip_path}")
                return True, ""
            else:
                return False, "ZIP file creation failed or is empty"
                
        except Exception as e:
            logger.error(f"Error creating ZIP archive: {e}")
            return False, str(e)
    
    def _cleanup_old_backups(self):
        """Remove backup files older than MAX_BACKUP_AGE_DAYS."""
        try:
            current_time = datetime.now()
            
            for filename in os.listdir(self.backups_dir):
                if filename.startswith('wireguard_backup_') and filename.endswith('.zip'):
                    file_path = os.path.join(self.backups_dir, filename)
                    file_age = current_time - datetime.fromtimestamp(os.path.getctime(file_path))
                    
                    if file_age.days > self.MAX_BACKUP_AGE_DAYS:
                        os.remove(file_path)
                        logger.info(f"Removed old backup file: {filename}")
                        
        except Exception as e:
            logger.warning(f"Error cleaning up old backups: {e}")
    
    @classmethod
    def get_backup_info(cls, instance_path: str) -> Dict:
        """Get information about existing backups."""
        service = cls(instance_path)
        backups = []
        
        try:
            if os.path.exists(service.backups_dir):
                for filename in os.listdir(service.backups_dir):
                    if filename.startswith('wireguard_backup_') and filename.endswith('.zip'):
                        file_path = os.path.join(service.backups_dir, filename)
                        file_stat = os.stat(file_path)
                        
                        backups.append({
                            'filename': filename,
                            'path': file_path,
                            'size': file_stat.st_size,
                            'created_at': datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
                            'age_days': (datetime.now() - datetime.fromtimestamp(file_stat.st_ctime)).days
                        })
                
                # Sort by creation time, newest first
                backups.sort(key=lambda x: x['created_at'], reverse=True)
        
        except Exception as e:
            logger.error(f"Error getting backup info: {e}")
        
        return {
            'backups': backups,
            'backup_dir': service.backups_dir,
            'max_age_days': cls.MAX_BACKUP_AGE_DAYS
        }