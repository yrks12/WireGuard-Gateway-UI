# Backup & Restore Feature Plan

## Goal
Enable web-based export and import of complete WireGuard Gateway system backups, allowing users to download a `.zip` file containing all client configurations, database metadata, iptables rules, and system settings for full system restoration via web interface.

## Scope

### What is included in backup:
- **WireGuard client config files** (`/instance/configs/*.conf`)
- **Client metadata database** (`/instance/configs.db` - SQLite with client info, status, timestamps)
- **Flask application database** (`/instance/app.db` - users, email settings, alert history)
- **Active iptables rules** (exported as shell commands for restoration)
- **Email settings and alert configuration**
- **System configuration metadata** (backup version, timestamp, system info)

### What is not included:
- **System logs** (`/logs/` directory - too large, not essential for restoration)
- **Pending configs** (`/instance/pending_configs/` - temporary data)
- **Virtual environment** (`/env/` - can be recreated)
- **Source code** (assumed to be deployed from git)
- **System-level WireGuard keys** (server private key - security risk)

## UI Integration

### New Routes:
- `GET /system/backup` - Generate and download backup ZIP file
- `POST /system/restore` - Upload and restore from backup ZIP file
- `GET /system/backup-status` - Check backup/restore operation status (for progress tracking)

### UI Elements:
- **Backup Section** in main dashboard or settings page:
  - "Download System Backup" button → triggers backup generation and download
  - Backup timestamp display of last successful backup
- **Restore Section**:
  - File upload input for `.zip` backup files
  - "Restore System" button with confirmation dialog
  - Progress indicator during restore operation
  - Warning about overwriting existing data

## Backup Architecture

### Backup Collection Process:
1. **Create temporary backup directory** in `/instance/backups/backup_YYYYMMDD_HHMMSS/`
2. **Copy database files**:
   - `cp /instance/app.db → backup_dir/app.db`
   - `cp /instance/configs.db → backup_dir/configs.db`
3. **Copy WireGuard configs**:
   - `cp -r /instance/configs/ → backup_dir/configs/`
4. **Export iptables rules**:
   - `sudo iptables-save > backup_dir/iptables_rules.txt`
   - `sudo iptables -t nat -S > backup_dir/iptables_nat_rules.txt`
5. **Generate metadata file**:
   - `backup_dir/backup_metadata.json` with version, timestamp, system info
6. **Create ZIP archive**:
   - `backup_YYYYMMDD_HHMMSS.zip` containing all files
7. **Cleanup temporary directory** after ZIP creation

### Backup Storage:
- **Temporary storage**: `/instance/backups/` (cleaned up after download)
- **ZIP file naming**: `wireguard_backup_YYYYMMDD_HHMMSS.zip`
- **Maximum backup age**: Auto-cleanup backups older than 7 days
- **Backup size estimation**: ~1-10MB depending on number of clients

### Download Mechanism:
- Use Flask's `send_file()` with `as_attachment=True`
- Set proper Content-Type: `application/zip`
- Delete temporary files after successful download
- Handle download errors and cleanup

## Restore Flow

### Upload Validation:
1. **File type check**: Ensure `.zip` extension and valid ZIP format
2. **File size limit**: Max 50MB upload size (configurable)
3. **ZIP structure validation**: Check for required files (`backup_metadata.json`, `app.db`, etc.)
4. **Metadata validation**: Verify backup version compatibility
5. **Database schema validation**: Check database tables match expected structure

### Restoration Sequence:
1. **Pre-restore backup**: Create automatic backup of current system before restore
2. **Stop active services**: Temporarily disable WireGuard monitoring
3. **Deactivate all WireGuard interfaces**: `sudo wg-quick down <interface>`
4. **Clear existing iptables rules**: Reset NAT and forwarding rules
5. **Restore databases**:
   - Stop Flask app database connections
   - Replace `app.db` and `configs.db` with backup versions
   - Restart database connections
6. **Restore WireGuard configs**: Copy `.conf` files to `/instance/configs/`
7. **Restore iptables rules**: Execute saved iptables commands
8. **Restart monitoring services**: Re-enable background tasks
9. **Validate restoration**: Check database connectivity and config integrity

### Error Handling & Rollback:
- **Transaction-like behavior**: If any step fails, rollback to pre-restore state
- **Backup validation checkpoint**: Verify each restored component before proceeding
- **Graceful degradation**: If iptables restore fails, continue with configs but warn user
- **Detailed error logging**: Log each restoration step for debugging
- **User feedback**: Real-time progress updates via AJAX/WebSocket

## Security & Validation

### File Security:
- **Upload directory isolation**: Use separate temp directory with restricted permissions
- **ZIP bomb protection**: Limit extracted file sizes and directory depth
- **Path traversal prevention**: Validate all file paths within ZIP
- **Temporary file cleanup**: Ensure all temp files are removed after operations

### Access Control:
- **Admin-only feature**: Require admin role for backup/restore operations
- **Rate limiting**: Limit backup generation to once per hour per user
- **CSRF protection**: Use Flask-WTF tokens for all forms
- **Audit logging**: Log all backup/restore operations with user and timestamp

### Data Validation:
- **Database integrity**: SQLite PRAGMA integrity_check before/after restore
- **Config syntax validation**: Validate WireGuard config syntax after restore
- **JSON schema validation**: Validate backup metadata against expected schema
- **Checksum verification**: Optional MD5/SHA256 checksums for critical files

## Dependencies

### New Python Packages:
```python
# Add to requirements.txt
zipfile  # Built-in, no new dependency
tempfile  # Built-in, no new dependency
subprocess  # Built-in, for iptables commands
hashlib  # Built-in, for checksums
```

### System Tools:
- `iptables-save` / `iptables-restore` (already available)
- `zip` / `unzip` commands (standard on most systems)
- Standard file system tools (`cp`, `mv`, `rm`)

### Flask Extensions:
- **File upload handling**: Current Flask setup should handle file uploads
- **Progress tracking**: Consider WebSocket or periodic AJAX polling
- **Background tasks**: Use existing threading model or consider Celery for long operations

## Testing Plan

### Unit Tests:
- **BackupService tests**:
  - Test backup creation with mock data
  - Test ZIP file structure and content
  - Test cleanup operations
- **RestoreService tests**:
  - Test ZIP extraction and validation
  - Test database restoration logic
  - Test rollback mechanisms
- **Validation tests**:
  - Test malformed ZIP handling
  - Test corrupted database handling
  - Test missing file scenarios

### Integration Tests:
- **Full backup/restore cycle**:
  - Create test system with clients and settings
  - Generate backup and validate content
  - Restore to clean system and verify data integrity
- **Error scenario testing**:
  - Test restoration with corrupted files
  - Test disk space exhaustion scenarios
  - Test permission issues

### Load Testing:
- **Large backup handling**: Test with 100+ client configs
- **Concurrent backup requests**: Test rate limiting
- **Upload timeout scenarios**: Test large file uploads

## Edge Cases

### Existing Config Conflicts:
- **Duplicate client names**: Restore should overwrite or skip with warning
- **Interface name conflicts**: Handle cases where interfaces are already active
- **Database ID conflicts**: Use REPLACE instead of INSERT for existing records

### Invalid/Missing Content:
- **Corrupted ZIP files**: Graceful error handling with user feedback
- **Missing critical files**: Partial restore with warnings about missing components
- **Schema version mismatches**: Migration logic or clear error messages
- **Empty databases**: Handle restore of systems with no existing data

### System State Issues:
- **Active WireGuard connections**: Gracefully disconnect before restore
- **Insufficient disk space**: Pre-flight checks for available space
- **Permission errors**: Clear error messages about file access issues
- **Service restart failures**: Rollback and manual intervention guidance

## Implementation Architecture

### Service Layer Design:
```python
# app/services/backup_service.py
class BackupService:
    @classmethod
    def create_backup() -> Tuple[bool, str, Optional[str]]
    
    @classmethod
    def validate_backup_file(zip_path: str) -> Tuple[bool, str]
    
    @classmethod
    def restore_from_backup(zip_path: str) -> Tuple[bool, str]
```

### Route Structure:
```python
# app/routes/main.py - new routes
@bp.route('/system/backup', methods=['GET'])
@login_required
@admin_required
def download_backup():
    """Generate and download system backup"""

@bp.route('/system/restore', methods=['GET', 'POST'])  
@login_required
@admin_required
def restore_system():
    """Upload and restore system backup"""
```

### File Organization:
```
app/services/
├── backup_service.py          # Main backup/restore logic
├── backup_validator.py        # ZIP and content validation
└── system_state_manager.py    # Service start/stop coordination

instance/
├── backups/                   # Temporary backup storage
│   └── backup_YYYYMMDD_HHMMSS/
└── restore_staging/           # Temporary restore workspace
```

## Next Steps

### Phase 1: Core Service Implementation
1. **Create BackupService class** with basic backup creation
2. **Implement ZIP packaging logic** with proper file organization
3. **Add basic restore validation** and extraction logic
4. **Create unit tests** for core backup/restore functions

### Phase 2: Route Integration
1. **Add backup/restore routes** to main blueprint
2. **Create HTML templates** for backup/restore UI
3. **Implement file upload handling** with proper validation
4. **Add progress feedback** via AJAX updates

### Phase 3: Security & Robustness  
1. **Add comprehensive input validation** and security checks
2. **Implement rollback mechanisms** for failed restores
3. **Add audit logging** for all backup/restore operations
4. **Create integration tests** for full backup/restore cycles

### Phase 4: UI Polish & Documentation
1. **Enhance UI** with progress indicators and better UX
2. **Add backup scheduling** options (future enhancement)
3. **Create user documentation** for backup/restore procedures
4. **Performance optimization** for large backup files

### Deployment Considerations:
- **Update install.sh**: Ensure backup directory permissions are set correctly
- **Production testing**: Test backup/restore on actual `/opt/wireguard-gateway/` deployment
- **Storage planning**: Consider backup retention policies and cleanup automation
- **Monitoring integration**: Add backup/restore events to system monitoring