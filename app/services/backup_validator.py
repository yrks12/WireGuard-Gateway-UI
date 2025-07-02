import os
import json
import zipfile
import sqlite3
import tempfile
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class BackupValidator:
    """Service for validating backup files and their contents."""
    
    SUPPORTED_BACKUP_VERSIONS = ["1.0"]
    MAX_BACKUP_SIZE = 50 * 1024 * 1024  # 50MB
    MAX_EXTRACTED_SIZE = 100 * 1024 * 1024  # 100MB
    MAX_ZIP_ENTRIES = 10000
    
    REQUIRED_FILES = [
        'backup_metadata.json'
    ]
    
    OPTIONAL_FILES = [
        'app.db',
        'configs.db',
        'iptables_rules.txt',
        'iptables_nat_rules.txt',
        'configs/'
    ]
    
    @classmethod
    def validate_backup_file(cls, zip_path: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Validate a backup ZIP file comprehensively.
        
        Args:
            zip_path: Path to the backup ZIP file
            
        Returns:
            Tuple of (is_valid, error_message, metadata)
        """
        try:
            # Basic file checks
            success, error = cls._validate_file_basic(zip_path)
            if not success:
                return False, error, None
            
            # ZIP structure validation
            success, error, zip_info = cls._validate_zip_structure(zip_path)
            if not success:
                return False, error, None
            
            # Extract and validate metadata
            success, error, metadata = cls._validate_metadata(zip_path)
            if not success:
                return False, error, None
            
            # Validate database files if present
            success, error = cls._validate_databases(zip_path, metadata)
            if not success:
                return False, error, None
            
            # Validate config files if present
            success, error = cls._validate_configs(zip_path, metadata)
            if not success:
                return False, error, None
            
            logger.info(f"Backup file validation successful: {zip_path}")
            return True, "Backup file is valid", metadata
            
        except Exception as e:
            logger.error(f"Unexpected error during backup validation: {e}")
            return False, f"Validation failed: {str(e)}", None
    
    @classmethod
    def _validate_file_basic(cls, zip_path: str) -> Tuple[bool, str]:
        """Perform basic file validation checks."""
        try:
            # Check if file exists
            if not os.path.exists(zip_path):
                return False, "Backup file does not exist"
            
            # Check file size
            file_size = os.path.getsize(zip_path)
            if file_size == 0:
                return False, "Backup file is empty"
            
            if file_size > cls.MAX_BACKUP_SIZE:
                return False, f"Backup file too large ({file_size} bytes, max {cls.MAX_BACKUP_SIZE})"
            
            # Check file extension
            if not zip_path.lower().endswith('.zip'):
                return False, "File must have .zip extension"
            
            return True, ""
            
        except Exception as e:
            return False, f"File validation error: {str(e)}"
    
    @classmethod
    def _validate_zip_structure(cls, zip_path: str) -> Tuple[bool, str, Optional[Dict]]:
        """Validate ZIP file structure and contents."""
        try:
            zip_info = {
                'entries': [],
                'total_size': 0,
                'has_required_files': set(),
                'has_optional_files': set()
            }
            
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                # Check for ZIP bombs and malicious content
                entries = zipf.infolist()
                
                if len(entries) > cls.MAX_ZIP_ENTRIES:
                    return False, f"Too many files in ZIP ({len(entries)}, max {cls.MAX_ZIP_ENTRIES})", None
                
                total_extracted_size = 0
                
                for entry in entries:
                    # Check for path traversal attacks
                    if '..' in entry.filename or entry.filename.startswith('/'):
                        return False, f"Malicious path detected: {entry.filename}", None
                    
                    # Check extracted size (ZIP bomb protection)
                    total_extracted_size += entry.file_size
                    if total_extracted_size > cls.MAX_EXTRACTED_SIZE:
                        return False, f"Extracted size too large (max {cls.MAX_EXTRACTED_SIZE})", None
                    
                    zip_info['entries'].append({
                        'filename': entry.filename,
                        'compressed_size': entry.compress_size,
                        'file_size': entry.file_size
                    })
                    
                    # Check for required and optional files
                    for req_file in cls.REQUIRED_FILES:
                        if entry.filename == req_file:
                            zip_info['has_required_files'].add(req_file)
                    
                    for opt_file in cls.OPTIONAL_FILES:
                        if entry.filename == opt_file or entry.filename.startswith(opt_file):
                            zip_info['has_optional_files'].add(opt_file)
                
                zip_info['total_size'] = total_extracted_size
                
                # Check that all required files are present
                missing_required = set(cls.REQUIRED_FILES) - zip_info['has_required_files']
                if missing_required:
                    return False, f"Missing required files: {', '.join(missing_required)}", None
                
                return True, "", zip_info
                
        except zipfile.BadZipFile:
            return False, "Invalid ZIP file format", None
        except Exception as e:
            return False, f"ZIP validation error: {str(e)}", None
    
    @classmethod
    def _validate_metadata(cls, zip_path: str) -> Tuple[bool, str, Optional[Dict]]:
        """Extract and validate backup metadata."""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                # Extract metadata file
                metadata_content = zipf.read('backup_metadata.json').decode('utf-8')
                metadata = json.loads(metadata_content)
                
                # Validate required metadata fields
                required_fields = ['backup_version', 'created_at', 'contents']
                for field in required_fields:
                    if field not in metadata:
                        return False, f"Missing required metadata field: {field}", None
                
                # Validate backup version
                version = metadata.get('backup_version')
                if version not in cls.SUPPORTED_BACKUP_VERSIONS:
                    return False, f"Unsupported backup version: {version}", None
                
                # Validate contents structure
                contents = metadata.get('contents', {})
                if not isinstance(contents, dict):
                    return False, "Invalid contents structure in metadata", None
                
                logger.debug(f"Metadata validation successful, version: {version}")
                return True, "", metadata
                
        except json.JSONDecodeError as e:
            return False, f"Invalid metadata JSON: {str(e)}", None
        except KeyError:
            return False, "backup_metadata.json not found in ZIP", None
        except Exception as e:
            return False, f"Metadata validation error: {str(e)}", None
    
    @classmethod
    def _validate_databases(cls, zip_path: str, metadata: Dict) -> Tuple[bool, str]:
        """Validate database files in the backup."""
        try:
            databases = metadata.get('contents', {}).get('databases', [])
            
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                for db_name in databases:
                    if db_name not in zipf.namelist():
                        return False, f"Database file {db_name} listed in metadata but not found in ZIP"
                    
                    # Extract database to temporary file for validation
                    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
                        temp_db.write(zipf.read(db_name))
                        temp_db_path = temp_db.name
                    
                    try:
                        # Validate SQLite database integrity
                        conn = sqlite3.connect(temp_db_path)
                        cursor = conn.cursor()
                        
                        # Check database integrity
                        cursor.execute("PRAGMA integrity_check")
                        result = cursor.fetchone()
                        
                        if result[0] != 'ok':
                            conn.close()
                            os.unlink(temp_db_path)
                            return False, f"Database {db_name} failed integrity check: {result[0]}"
                        
                        # Check for expected tables based on database type
                        if db_name == 'app.db':
                            expected_tables = ['user', 'email_settings', 'alert_history']
                        elif db_name == 'configs.db':
                            expected_tables = ['clients']
                        else:
                            expected_tables = []
                        
                        if expected_tables:
                            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                            existing_tables = [row[0] for row in cursor.fetchall()]
                            
                            for table in expected_tables:
                                if table not in existing_tables:
                                    logger.warning(f"Expected table {table} not found in {db_name}")
                        
                        conn.close()
                        logger.debug(f"Database {db_name} validation successful")
                        
                    finally:
                        # Clean up temporary file
                        if os.path.exists(temp_db_path):
                            os.unlink(temp_db_path)
            
            return True, ""
            
        except Exception as e:
            return False, f"Database validation error: {str(e)}"
    
    @classmethod
    def _validate_configs(cls, zip_path: str, metadata: Dict) -> Tuple[bool, str]:
        """Validate WireGuard config files in the backup."""
        try:
            config_files = metadata.get('contents', {}).get('configs', [])
            
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                for config_file in config_files:
                    config_path = f"configs/{config_file}"
                    
                    if config_path not in zipf.namelist():
                        return False, f"Config file {config_file} listed in metadata but not found in ZIP"
                    
                    # Basic config file validation
                    if not config_file.endswith('.conf'):
                        return False, f"Invalid config file extension: {config_file}"
                    
                    # Extract and validate config content
                    config_content = zipf.read(config_path).decode('utf-8')
                    
                    # Basic WireGuard config validation
                    if '[Interface]' not in config_content:
                        return False, f"Config file {config_file} missing [Interface] section"
                    
                    if '[Peer]' not in config_content:
                        return False, f"Config file {config_file} missing [Peer] section"
                    
                    logger.debug(f"Config file {config_file} validation successful")
            
            return True, ""
            
        except Exception as e:
            return False, f"Config validation error: {str(e)}"
    
    @classmethod
    def extract_backup_info(cls, zip_path: str) -> Optional[Dict]:
        """Extract basic information from backup file without full validation."""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                metadata_content = zipf.read('backup_metadata.json').decode('utf-8')
                metadata = json.loads(metadata_content)
                
                return {
                    'version': metadata.get('backup_version'),
                    'created_at': metadata.get('created_at'),
                    'timestamp': metadata.get('timestamp'),
                    'contents': metadata.get('contents', {}),
                    'file_size': os.path.getsize(zip_path)
                }
                
        except Exception as e:
            logger.error(f"Error extracting backup info: {e}")
            return None