# WireGuard Gateway UI - Fix Plan Status

## Completed Fixes ✅

### Fix #3 + #4 (Combined): False Disconnect Alerts & Database Readonly Errors
- **Status**: ✅ COMPLETED & DEPLOYED
- **Branch**: `fix/false-positive-disconnect-alert` (merged to main)
- **Root Cause**: Peers without recent handshakes were falsely marked as disconnected + SQLAlchemy session corruption
- **Solution**: 
  - Changed default peer status to True when found in `wg show` output
  - Increased disconnect threshold from 5 to 30 minutes  
  - Added "Now" handshake handling
  - Implemented retry logic with rollback for database operations
- **Result**: Reduced false alerts from 480+ per hour to 0

### Fix #2: Email Settings Lost on Reinstall
- **Status**: ✅ COMPLETED & DEPLOYED  
- **Branch**: `fix/email-settings-lost-on-reinstall` (merged to main)
- **Root Cause**: `install.sh` recreates database, losing email settings
- **Solution**:
  - Created backup/restore script for email settings
  - Modified install.sh to backup before DB deletion and restore after
  - Added startup loading of email settings from database
  - Fixed virtual environment path issue (`env` → `venv`)
- **Result**: Email settings now persist across reinstalls

### Fix #5: Timestamp Mismatch UI vs Logs  
- **Status**: 🔄 PARTIALLY COMPLETED
- **Branch**: `fix/timestamp-mismatch-ui-vs-logs` (ready for PR)
- **Completed**:
  - ✅ UTC formatter for all application logs
  - ✅ Template filter for UTC display
  - ✅ Monitoring logs now show UTC timestamps
  - ✅ Dashboard Recent Activity fixed (latest commit)
  - ✅ Client Testing handshake display fixed (latest commit)
- **Remaining Issues**:
  - ❌ Connection Status still shows "Never" instead of actual handshake times
  - ❌ Some templates still use `toLocaleString()` (need to check monitoring.html, clients.html)
  - ❌ Recent Activity API returns empty data (missing `last_activated`/`last_deactivated` fields)

## Pending Fixes 🔄

### Fix #5: Complete Timestamp Standardization (PRIORITY: HIGH)
**Remaining Tasks:**
1. **Fix Recent Activity API** (Critical issue discovered):
   - `last_activated` and `last_deactivated` fields don't exist in config storage
   - Recent Activity will always be empty without these fields
   - Need to add these fields to database schema and update activation/deactivation logic

2. **Fix Connection Status "Never" Display**:
   - Connection Status shows "Never" because handshake data isn't properly propagated
   - Need to ensure handshake data from `WireGuardMonitor._last_handshakes` is properly displayed

3. **Standardize Remaining Templates**:
   - `monitoring.html` line 110: still uses `toLocaleString()`
   - `clients.html` line 157: reverted back to `toLocaleString()` on main branch
   - Need to update all templates to use UTC format consistently

4. **Fix Timestamp Storage Inconsistency**:
   - Config storage uses SQLite `CURRENT_TIMESTAMP` (local time)
   - Flask ORM uses `datetime.utcnow()` (UTC)
   - Need to standardize all timestamp storage to UTC

### Fix #1: Client Name Lost on Subnet Prompt (PRIORITY: LOW)
- **Status**: ❌ NOT STARTED
- **Branch**: `fix/client-name-lost-on-subnet` (created but no implementation)
- **Root Cause**: When user fixes subnet, original client name is lost
- **Priority**: Low - cosmetic issue only

## Architecture Issues Identified 🔍

### Dual Database System
The codebase uses **two separate database systems** which complicates timestamp management:
- **Config Storage** (`/instance/configs.db`): SQLite with `CURRENT_TIMESTAMP` (local time)
- **Flask ORM** (`/instance/app.db`): Uses `datetime.utcnow()` (proper UTC)

### Missing Activity Tracking
Recent Activity feature is fundamentally broken:
- API expects `last_activated`/`last_deactivated` fields that don't exist
- Client activation/deactivation events are not timestamped
- Would need schema changes and route updates to fix properly

## Next Steps for Tomorrow 📋

1. **Immediate Priority**: Complete Fix #5 timestamp standardization
   - Fix all remaining `toLocaleString()` uses in templates
   - Address the Connection Status "Never" issue
   - Test deployment to ensure fixes work in production

2. **Medium Priority**: Decide on Recent Activity fix approach
   - Option A: Add missing fields to config storage (requires schema change)
   - Option B: Remove Recent Activity feature temporarily
   - Option C: Use test history data as substitute

3. **Low Priority**: Implement Fix #1 if time allows

## Deployment Notes 🚀

- **Production Location**: `/opt/wireguard-gateway/`
- **Deployment Command**: `sudo ./install.sh --skip-dependencies`
- **Never use**: `systemctl restart` (doesn't apply development changes)
- **Always verify**: Check logs at `http://172.17.246.210:5000/monitoring/logs` after deployment

## Technical Debt 📝

- Main routes file (`app/routes/main.py`) still needs refactoring (1006 lines)
- Empty files need cleanup (`check_users.py`)
- Incomplete development todos in `REMEBER.txt`
- Dual database system creates complexity and inconsistency