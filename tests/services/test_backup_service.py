import os
import json
import tempfile
import shutil
import zipfile
import pytest
from unittest.mock import patch, MagicMock

from app.services.backup_service import BackupService
from app.services.backup_validator import BackupValidator
from app.services.restore_service import RestoreService


class TestBackupService:
    """Test cases for BackupService."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_instance = tempfile.mkdtemp()
        self.test_service = BackupService(self.test_instance)
        
        # Create test directories
        os.makedirs(os.path.join(self.test_instance, 'configs'), exist_ok=True)
        
        # Create test database files
        with open(os.path.join(self.test_instance, 'app.db'), 'w') as f:
            f.write("fake app database")
        
        with open(os.path.join(self.test_instance, 'configs.db'), 'w') as f:
            f.write("fake config database")
        
        # Create test config files
        with open(os.path.join(self.test_instance, 'configs', 'test_client.conf'), 'w') as f:
            f.write("""[Interface]
PrivateKey = test_private_key
Address = 10.0.0.1/24

[Peer]
PublicKey = test_public_key
AllowedIPs = 192.168.1.0/24
Endpoint = test.example.com:51820
""")
    
    def teardown_method(self):
        """Clean up test environment."""
        if os.path.exists(self.test_instance):
            shutil.rmtree(self.test_instance)
    
    def test_backup_creation_success(self):
        """Test successful backup creation."""
        with patch('subprocess.run') as mock_subprocess:
            # Mock iptables commands
            mock_subprocess.return_value = MagicMock(returncode=0, stdout="iptables rules")
            
            success, message, backup_path = BackupService.create_backup(self.test_instance)
            
            assert success is True
            assert "successfully" in message.lower()
            assert backup_path is not None
            assert os.path.exists(backup_path)
            assert backup_path.endswith('.zip')
    
    def test_backup_zip_structure(self):
        """Test that backup ZIP contains expected files."""
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = MagicMock(returncode=0, stdout="iptables rules")
            
            success, message, backup_path = BackupService.create_backup(self.test_instance)
            
            assert success is True
            
            # Check ZIP contents
            with zipfile.ZipFile(backup_path, 'r') as zipf:
                files = zipf.namelist()
                
                # Required files
                assert 'backup_metadata.json' in files
                assert 'app.db' in files
                assert 'configs.db' in files
                assert 'configs/test_client.conf' in files
                
                # Optional files (iptables)
                assert 'iptables_rules.txt' in files
    
    def test_backup_metadata_structure(self):
        """Test backup metadata structure."""
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = MagicMock(returncode=0, stdout="iptables rules")
            
            success, message, backup_path = BackupService.create_backup(self.test_instance)
            
            assert success is True
            
            # Extract and validate metadata
            with zipfile.ZipFile(backup_path, 'r') as zipf:
                metadata_content = zipf.read('backup_metadata.json').decode('utf-8')
                metadata = json.loads(metadata_content)
                
                # Check required fields
                assert 'backup_version' in metadata
                assert 'created_at' in metadata
                assert 'contents' in metadata
                
                # Check contents structure
                contents = metadata['contents']
                assert 'databases' in contents
                assert 'configs' in contents
                assert 'iptables_rules' in contents
                
                # Check specific content
                assert 'app.db' in contents['databases']
                assert 'configs.db' in contents['databases']
                assert 'test_client.conf' in contents['configs']
    
    def test_backup_without_configs(self):
        """Test backup creation when no config files exist."""
        # Remove config files
        shutil.rmtree(os.path.join(self.test_instance, 'configs'))
        os.makedirs(os.path.join(self.test_instance, 'configs'))
        
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = MagicMock(returncode=0, stdout="iptables rules")
            
            success, message, backup_path = BackupService.create_backup(self.test_instance)
            
            assert success is True
            
            # Check that configs directory exists but is empty
            with zipfile.ZipFile(backup_path, 'r') as zipf:
                files = zipf.namelist()
                config_files = [f for f in files if f.startswith('configs/') and f.endswith('.conf')]
                assert len(config_files) == 0
    
    def test_backup_iptables_failure(self):
        """Test backup continues when iptables export fails."""
        with patch('subprocess.run') as mock_subprocess:
            # Mock iptables failure
            mock_subprocess.return_value = MagicMock(returncode=1, stderr="iptables error")
            
            success, message, backup_path = BackupService.create_backup(self.test_instance)
            
            # Backup should still succeed (iptables is non-critical)
            assert success is True
            assert backup_path is not None
    
    def test_get_backup_info(self):
        """Test getting backup information."""
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = MagicMock(returncode=0, stdout="iptables rules")
            
            # Create a backup
            BackupService.create_backup(self.test_instance)
            
            # Get backup info
            info = BackupService.get_backup_info(self.test_instance)
            
            assert 'backups' in info
            assert len(info['backups']) == 1
            assert 'backup_dir' in info
            assert 'max_age_days' in info
            
            backup = info['backups'][0]
            assert 'filename' in backup
            assert 'size' in backup
            assert 'created_at' in backup


class TestBackupValidator:
    """Test cases for BackupValidator."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up test environment."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def create_test_backup(self, include_all=True):
        """Create a test backup ZIP file."""
        zip_path = os.path.join(self.test_dir, 'test_backup.zip')
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            # Add metadata
            metadata = {
                'backup_version': '1.0',
                'created_at': '2024-01-01T12:00:00Z',
                'contents': {
                    'databases': ['app.db', 'configs.db'],
                    'configs': ['test_client.conf'],
                    'iptables_rules': ['iptables_rules.txt']
                }
            }
            zipf.writestr('backup_metadata.json', json.dumps(metadata))
            
            if include_all:
                # Add database files
                zipf.writestr('app.db', 'fake app database')
                zipf.writestr('configs.db', 'fake config database')
                
                # Add config file
                config_content = """[Interface]
PrivateKey = test_key
Address = 10.0.0.1/24

[Peer]
PublicKey = test_peer_key
AllowedIPs = 192.168.1.0/24
"""
                zipf.writestr('configs/test_client.conf', config_content)
                
                # Add iptables rules
                zipf.writestr('iptables_rules.txt', 'iptables rules content')
        
        return zip_path
    
    def test_valid_backup_validation(self):
        """Test validation of a valid backup file."""
        zip_path = self.create_test_backup()
        
        is_valid, error, metadata = BackupValidator.validate_backup_file(zip_path)
        
        assert is_valid is True
        assert error == "Backup file is valid"
        assert metadata is not None
        assert metadata['backup_version'] == '1.0'
    
    def test_missing_file_validation(self):
        """Test validation when backup file doesn't exist."""
        nonexistent_path = os.path.join(self.test_dir, 'nonexistent.zip')
        
        is_valid, error, metadata = BackupValidator.validate_backup_file(nonexistent_path)
        
        assert is_valid is False
        assert "does not exist" in error
        assert metadata is None
    
    def test_invalid_zip_validation(self):
        """Test validation of invalid ZIP file."""
        invalid_zip = os.path.join(self.test_dir, 'invalid.zip')
        with open(invalid_zip, 'w') as f:
            f.write("not a zip file")
        
        is_valid, error, metadata = BackupValidator.validate_backup_file(invalid_zip)
        
        assert is_valid is False
        assert "ZIP" in error
        assert metadata is None
    
    def test_missing_metadata_validation(self):
        """Test validation when metadata file is missing."""
        zip_path = os.path.join(self.test_dir, 'no_metadata.zip')
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            zipf.writestr('app.db', 'fake database')
        
        is_valid, error, metadata = BackupValidator.validate_backup_file(zip_path)
        
        assert is_valid is False
        assert "backup_metadata.json" in error
        assert metadata is None
    
    def test_unsupported_version_validation(self):
        """Test validation with unsupported backup version."""
        zip_path = os.path.join(self.test_dir, 'wrong_version.zip')
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            metadata = {
                'backup_version': '999.0',  # Unsupported version
                'created_at': '2024-01-01T12:00:00Z',
                'contents': {}
            }
            zipf.writestr('backup_metadata.json', json.dumps(metadata))
        
        is_valid, error, metadata = BackupValidator.validate_backup_file(zip_path)
        
        assert is_valid is False
        assert "Unsupported backup version" in error
        assert metadata is None
    
    def test_extract_backup_info(self):
        """Test extracting basic backup information."""
        zip_path = self.create_test_backup()
        
        info = BackupValidator.extract_backup_info(zip_path)
        
        assert info is not None
        assert info['version'] == '1.0'
        assert 'created_at' in info
        assert 'contents' in info
        assert 'file_size' in info


class TestRestoreService:
    """Test cases for RestoreService."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_instance = tempfile.mkdtemp()
        self.test_service = RestoreService(self.test_instance)
        
        # Create existing instance structure
        os.makedirs(os.path.join(self.test_instance, 'configs'), exist_ok=True)
        
        with open(os.path.join(self.test_instance, 'app.db'), 'w') as f:
            f.write("existing app database")
        
        with open(os.path.join(self.test_instance, 'configs.db'), 'w') as f:
            f.write("existing config database")
    
    def teardown_method(self):
        """Clean up test environment."""
        if os.path.exists(self.test_instance):
            shutil.rmtree(self.test_instance)
    
    def create_test_backup_zip(self):
        """Create a test backup ZIP file."""
        zip_path = os.path.join(self.test_instance, 'test_restore.zip')
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            # Add metadata
            metadata = {
                'backup_version': '1.0',
                'created_at': '2024-01-01T12:00:00Z',
                'contents': {
                    'databases': ['app.db', 'configs.db'],
                    'configs': ['restored_client.conf'],
                    'iptables_rules': []
                }
            }
            zipf.writestr('backup_metadata.json', json.dumps(metadata))
            
            # Add database files
            zipf.writestr('app.db', 'restored app database')
            zipf.writestr('configs.db', 'restored config database')
            
            # Add config file
            config_content = """[Interface]
PrivateKey = restored_key
Address = 10.0.0.2/24

[Peer]
PublicKey = restored_peer_key
AllowedIPs = 192.168.2.0/24
"""
            zipf.writestr('configs/restored_client.conf', config_content)
        
        return zip_path
    
    def test_staging_directory_creation(self):
        """Test staging directory creation."""
        staging_dir = self.test_service._create_staging_directory()
        
        assert os.path.exists(staging_dir)
        assert 'restore_' in os.path.basename(staging_dir)
    
    def test_backup_extraction(self):
        """Test backup extraction to staging."""
        zip_path = self.create_test_backup_zip()
        staging_dir = self.test_service._create_staging_directory()
        
        success, error = self.test_service._extract_backup(zip_path, staging_dir)
        
        assert success is True
        assert error == ""
        assert os.path.exists(os.path.join(staging_dir, 'backup_metadata.json'))
        assert os.path.exists(os.path.join(staging_dir, 'app.db'))
        assert os.path.exists(os.path.join(staging_dir, 'configs', 'restored_client.conf'))
    
    @patch('subprocess.run')
    def test_stop_active_services(self, mock_subprocess):
        """Test stopping active WireGuard services."""
        # Mock wg show interfaces command
        mock_subprocess.return_value = MagicMock(
            returncode=0, 
            stdout="wg0 wg1\\n"
        )
        
        success, error = self.test_service._stop_active_services()
        
        assert success is True
        assert error == ""
        
        # Verify subprocess calls
        assert mock_subprocess.call_count >= 1
    
    def test_database_restoration(self):
        """Test database file restoration."""
        zip_path = self.create_test_backup_zip()
        staging_dir = self.test_service._create_staging_directory()
        self.test_service._extract_backup(zip_path, staging_dir)
        
        # Backup original content for verification
        with open(os.path.join(self.test_instance, 'app.db'), 'r') as f:
            original_content = f.read()
        
        success, error = self.test_service._restore_databases(staging_dir)
        
        assert success is True
        assert error == ""
        
        # Verify databases were restored
        with open(os.path.join(self.test_instance, 'app.db'), 'r') as f:
            restored_content = f.read()
        
        assert restored_content == "restored app database"
        assert restored_content != original_content
        
        # Verify backup was created
        assert os.path.exists(os.path.join(self.test_instance, 'app.db.pre_restore'))
    
    def test_config_restoration(self):
        """Test WireGuard config restoration."""
        zip_path = self.create_test_backup_zip()
        staging_dir = self.test_service._create_staging_directory()
        self.test_service._extract_backup(zip_path, staging_dir)
        
        success, error = self.test_service._restore_configs(staging_dir)
        
        assert success is True
        assert error == ""
        
        # Verify config was restored
        restored_config = os.path.join(self.test_instance, 'configs', 'restored_client.conf')
        assert os.path.exists(restored_config)
        
        with open(restored_config, 'r') as f:
            content = f.read()
        
        assert 'restored_key' in content
        assert '[Interface]' in content
        assert '[Peer]' in content
    
    def test_cleanup_staging(self):
        """Test staging directory cleanup."""
        staging_dir = self.test_service._create_staging_directory()
        
        # Create some test files
        with open(os.path.join(staging_dir, 'test_file.txt'), 'w') as f:
            f.write("test content")
        
        assert os.path.exists(staging_dir)
        
        self.test_service._cleanup_staging(staging_dir)
        
        assert not os.path.exists(staging_dir)