# 🛠️ Fix Plan: Email Settings Lost on Reinstall

## 🧩 Issue Summary

When running `./install.sh` on a system that already has WireGuard Gateway installed, all email settings (SMTP credentials, alert recipients) are permanently lost and must be manually reconfigured. This breaks email alerting functionality for VPN disconnect notifications until the administrator notices and reconfigures the settings.

**Evidence from Logs:**
```
2025-07-01 12:22:28,733 WARNING: No recipients specified for alert
2025-07-01 12:22:28,743 ERROR: Failed to send disconnect alert for lind_05d1b831
INFO: Using configured alert recipients: []
```

**User Impact:**
- Silent failure of critical disconnect alerts
- No notification that email settings were lost
- Manual reconfiguration required after every reinstall
- Potential security/monitoring gaps until reconfiguration

## 🔍 Root Cause

The issue occurs because the install script performs destructive database operations without any backup or migration mechanism:

### **Database Destruction** (`install.sh:385`)
```bash
# Remove existing database file completely
rm -f $DB_FILE
touch $DB_FILE
chmod 644 $DB_FILE
```

### **No Backup or Migration**
The install script:
1. **Completely deletes** the existing database file at `/var/lib/wireguard-gateway/wireguard.db`
2. **Creates a blank database** with only default admin user
3. **No preservation** of existing email settings, client configurations, or alert history
4. **No warning** to user about data loss

### **Missing Startup Configuration Loading**
Additionally, even if email settings survived reinstall, there's a secondary issue:
- Email settings are stored in database but **NOT automatically loaded** into Flask app config during startup
- Settings only get loaded when user manually accesses the email settings page
- This means email alerts remain broken until manual intervention

### **Current Database Recreation Logic** (`install.sh:506-518`)
```bash
# Only recreates admin user, nothing else
python3 -c "
from app import create_app
from app.models.user import User
from app.database import db
# Creates tables but no data migration
db.create_all()
# Only creates admin user, ignores all other data
"
```

## ✅ Proposed Fix Plan

### 1. **Implement Database Backup and Restore**
   - **Backup Phase**: Before database deletion, export critical data (email settings, client metadata)
   - **Restore Phase**: After database recreation, restore backed-up settings
   - **Selective Backup**: Focus on email settings, user preferences, non-config data

### 2. **Add Installation Mode Detection**
   - **Fresh Install**: Current behavior (clean database creation)
   - **Reinstall/Upgrade**: Preserve user data mode
   - **Forced Clean**: Option to override and do fresh install
   - **User Prompt**: Ask user about data preservation vs clean install

### 3. **Email Settings Startup Loading**
   - Modify app initialization to load email settings from database into Flask config
   - Ensure email functionality works immediately after app startup
   - Add validation and logging for email configuration status

### 4. **Data Migration Framework**
   - Create reusable backup/restore functions for future upgrades
   - Support for incremental database schema migrations
   - Validation of restored data integrity

### 5. **User Communication and Warnings**
   - Clear warnings before data loss operations
   - Post-install summary of preserved vs reset settings
   - Recommendations for manual verification of critical settings

## 🧪 Test Plan

### 1. **Fresh Installation Test**
   - Install on clean system
   - Configure email settings via web interface
   - verify email alerts work
   - **Expected**: Clean installation with no data migration needed

### 2. **Reinstall with Email Settings Test (Primary Fix)**
   - Fresh install and configure email settings
   - Run `./install.sh` again
   - Verify email settings are preserved and functional
   - **Expected**: Email settings automatically restored and working

### 3. **Mixed Data Preservation Test**
   - Configure email settings, add clients, create user accounts
   - Reinstall system
   - Verify:
     - Email settings preserved
     - Client configs handled appropriately (separate from email issue)
     - Admin user credentials remain intact
   - **Expected**: Email settings preserved regardless of other data

### 4. **Email Startup Loading Test**
   - Configure email settings in database
   - Restart WireGuard Gateway service
   - Trigger disconnect event
   - **Expected**: Email alerts work immediately without manual configuration

### 5. **Upgrade vs Clean Install Mode Test**
   - Test installation with upgrade flag/option
   - Test installation with clean flag/option
   - Verify user can choose data preservation strategy
   - **Expected**: User control over data migration behavior

### 6. **Data Integrity Test**
   - Configure complex email settings (multiple recipients, custom SMTP)
   - Perform reinstall
   - Verify all email configuration details preserved accurately
   - **Expected**: No data corruption or loss during backup/restore

### 7. **Rollback Test**
   - Simulate backup failure during reinstall
   - Verify graceful fallback to clean install
   - Ensure no system corruption
   - **Expected**: Safe fallback behavior if backup/restore fails

## 🧯 Rollback Plan

### **Safe Rollback Strategy**
1. **Install Script Revert**: Git revert changes to install.sh
2. **Restore Original Behavior**: Database recreation without backup/restore
3. **No Breaking Changes**: New backup/restore functionality isolated in separate functions
4. **Data Safety**: Existing clean install behavior remains as fallback

### **Compatibility Considerations**
- New install script must work on systems with existing old installations
- Backward compatibility with systems that lack backup data
- Graceful handling of partially corrupted backups
- Option to force clean installation if restoration fails

### **Emergency Procedures**
- Manual database restoration from backups if automated restore fails
- Documentation for manual email settings reconfiguration
- Clear error messages and recovery instructions
- Support for running installation in "safe mode" (clean install only)

## 📁 Related Files

**Primary Files (Require Changes):**
- `install.sh` - Main installation script, database backup/restore logic (lines 385, 506-518)
- `app/__init__.py` - App initialization, email settings loading during startup
- `app/models/email_settings.py` - Email settings model, backup/restore methods

**Secondary Files (Supporting Changes):**
- `app/services/email_service.py` - Email configuration validation and logging
- `app/routes/main.py` - Email settings routes, post-install validation
- Database migration utilities (new files to be created)

**Configuration Files:**
- `.env` or environment configuration for installation modes
- Systemd service file considerations for startup behavior

**Testing Files:**
- `tests/installation/` - New test suite for installation scenarios
- `tests/services/test_email_service.py` - Enhanced tests for startup loading

## 🎯 Implementation Priority

### **Critical Priority (Must Fix)**
1. **Database Backup Creation** - Before deletion, save email settings
2. **Database Restore Logic** - After recreation, restore email settings
3. **Install Mode Detection** - Distinguish fresh vs reinstall scenarios

### **High Priority (Should Fix)**
4. **Email Settings Startup Loading** - Automatic loading during app initialization
5. **User Communication** - Warnings and notifications about data operations
6. **Error Handling** - Graceful failure recovery for backup/restore

### **Medium Priority (Enhancement)**
7. **Installation Modes** - User choice for data preservation strategy
8. **Data Migration Framework** - Reusable for future upgrades
9. **Extended Testing** - Comprehensive installation scenario coverage

### **Low Priority (Nice to Have)**
10. **GUI Installation** - Web-based installation mode selection
11. **Backup Encryption** - Secure storage of sensitive email credentials
12. **Automated Email Validation** - Post-install connectivity testing

## 📊 Success Criteria

### **Functional Success**
- ✅ Email settings preserved across reinstallation
- ✅ Email alerts work immediately after reinstall (no manual reconfiguration)
- ✅ Fresh installations continue to work without regression
- ✅ User warned before any potential data loss operations

### **Technical Success**
- ✅ Robust backup/restore mechanism with error handling
- ✅ Email settings automatically loaded during app startup
- ✅ Installation mode detection works reliably
- ✅ No breaking changes to existing installation workflows

### **Validation Criteria**
- Install system, configure email settings, reinstall → settings preserved
- Restart service after reinstall → email alerts work immediately
- Install on clean system → no backup/restore errors or delays
- Force clean install option → complete reset as expected

### **User Experience Success**
- Clear feedback during installation about data preservation
- No silent failures or unexpected configuration losses
- Minimal post-installation manual steps required
- Obvious recovery options if something goes wrong

### **Operational Success**
- Email alerting remains functional across system maintenance
- Administrators can safely run updates/reinstalls
- Critical monitoring capabilities preserved during upgrades
- Reduced support burden for email reconfiguration issues