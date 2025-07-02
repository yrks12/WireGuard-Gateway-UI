# 🛠️ Fix Plan: Client Name Lost on Subnet Prompt

## 🧩 Issue Summary

When a user uploads a WireGuard client config file that contains `AllowedIPs = 0.0.0.0/0`, the system prompts them to specify a correct subnet. However, during this subnet correction process, the original client name (derived from the uploaded filename) is lost and replaced with a generic `client_{uuid}` naming pattern.

**Example Flow:**
1. User uploads `company_vpn.conf` with `AllowedIPs = 0.0.0.0/0`
2. System prompts for subnet correction
3. User provides valid subnet (e.g., `192.168.1.0/24`)
4. **Problem:** Final client name becomes `client_a1b2c3d4` instead of `company_vpn_a1b2c3d4`

This breaks naming consistency and makes client management confusing for users.

## 🔍 Root Cause

The issue stems from a missing parameter in the subnet submission workflow. Here's the detailed analysis:

### **Two-Path Validation Flow**

**Path A (Valid Config):** `app/routes/main.py:78-138`
- File uploaded and validated successfully
- `original_filename` parameter passed to `config_storage.store_config()` at line 134
- Client name correctly derived: `{filename_without_extension}_{uuid[:8]}`

**Path B (Pending Config - THE PROBLEM):** `app/routes/main.py:140-190`
- File uploaded but validation fails due to `0.0.0.0/0` in AllowedIPs
- Config stored in pending storage (`app/services/pending_configs.py`)
- **CRITICAL ISSUE:** Original filename **NOT preserved** in pending storage
- User prompted for subnet via `/clients/subnet` endpoint
- Upon subnet submission (line 161-166), `original_filename` parameter **NOT passed**
- Results in generic naming: `client_{uuid}`

### **Specific Code Locations**

**Problem Location 1:** `app/services/pending_configs.py:25-35`
```python
def store_pending_config(self, config_content, public_key):
    config_data = {
        'content': config_content,
        'public_key': public_key,
        'timestamp': datetime.utcnow().isoformat()
        # MISSING: 'original_filename' field
    }
```

**Problem Location 2:** `app/routes/main.py:161-166`
```python
client_id, metadata = current_app.config_storage.store_config(
    updated_config['content'],
    subnet,
    updated_config['public_key']
    # MISSING: original_filename parameter
)
```

### **Name Generation Logic** (`app/services/config_storage.py:88-94`)
```python
if original_filename:
    base_name = os.path.splitext(original_filename)[0]
    client_name = f"{base_name}_{client_id[:8]}"  # Desired behavior
else:
    client_name = f"client_{client_id[:8]}"       # Current buggy behavior
```

## ✅ Proposed Fix Plan

### 1. **Extend Pending Config Storage Structure**
   - Modify `app/services/pending_configs.py` to store original filename
   - Update `store_pending_config()` to accept and store `original_filename`
   - Update `get_pending_config()` to return original filename

### 2. **Pass Original Filename Through Upload Flow**
   - Modify upload route (`app/routes/main.py:78-138`) to pass filename to pending storage
   - Extract filename before validation and ensure it's preserved

### 3. **Fix Subnet Submission Route**
   - Modify subnet route (`app/routes/main.py:140-190`) to retrieve and use original filename
   - Pass `original_filename` to `config_storage.store_config()` call

### 4. **Add Filename Validation and Sanitization**
   - Sanitize filenames to prevent path traversal or invalid characters
   - Handle edge cases like missing extensions or special characters
   - Preserve user intent while ensuring system safety

### 5. **Frontend Enhancement (Optional)**
   - Display the intended client name in subnet prompt modal
   - Show user what the final client name will be after correction

## 🧪 Test Plan

### 1. **Happy Path Test**
   - Upload `test_client.conf` with valid AllowedIPs
   - Verify client name becomes `test_client_{uuid}`
   - Ensure existing behavior remains unchanged

### 2. **Subnet Correction Test (Primary Fix)**
   - Upload `company_vpn.conf` containing `AllowedIPs = 0.0.0.0/0`
   - Complete subnet correction workflow
   - Verify final client name is `company_vpn_{uuid}` not `client_{uuid}`

### 3. **Edge Cases Test**
   - Upload files with various naming patterns:
     - `client.conf` → `client_{uuid}`
     - `my-company-vpn.conf` → `my-company-vpn_{uuid}`
     - `CLIENT_VPN.CONF` → `CLIENT_VPN_{uuid}`
     - `file with spaces.conf` → `file with spaces_{uuid}` (sanitized)
   - Test files without extensions
   - Test very long filenames (truncation handling)

### 4. **Concurrent Upload Test**
   - Upload multiple files simultaneously, some requiring subnet correction
   - Verify each maintains its original name through the process
   - Test pending config storage doesn't have race conditions

### 5. **Storage Consistency Test**
   - Verify pending config cleanup works with new filename field
   - Test expiration of pending configs with filenames
   - Ensure database consistency after fix

## 🧯 Rollback Plan

### **Safe Rollback Approach**
1. **Code Revert**: Git revert the fix commit(s) to restore original behavior
2. **Database Safety**: No schema changes required, only field additions to JSON storage
3. **Pending Config Cleanup**: Existing pending configs without filename field will use fallback naming
4. **User Impact**: Users will temporarily experience original bug but no data loss

### **Compatibility Handling**
- New code must handle both old pending configs (without filename) and new ones (with filename)
- Implement graceful fallback to generic naming for legacy pending configs
- Ensure backward compatibility during transition period

### **Rollback Verification**
- Restore original upload behavior
- Verify pending config storage returns to original structure
- Test that existing clients remain unaffected

## 📁 Related Files

**Primary Files (Require Changes):**
- `app/services/pending_configs.py` - Store and retrieve original filename
- `app/routes/main.py` - Pass filename through both upload paths (lines 78-138, 140-190)
- `app/services/config_storage.py` - Name generation logic (reference, minimal changes)

**Secondary Files (Testing/Validation):**
- `app/services/wireguard.py` - Config validation logic (understanding)
- `app/templates/clients.html` - Frontend upload interface (optional enhancement)
- `tests/services/test_pending_configs.py` - Unit tests for pending storage
- `tests/routes/test_main.py` - Integration tests for upload flow

**Configuration Files:**
- `app/forms.py` - Upload form validation (review for consistency)

## 🎯 Implementation Priority

### **High Priority (Must Fix)**
1. **Pending Config Storage Enhancement** - Core infrastructure change
2. **Upload Route Filename Preservation** - Main workflow fix
3. **Subnet Route Filename Usage** - Complete the fix

### **Medium Priority (Should Fix)**
4. **Filename Sanitization** - Security and compatibility
5. **Error Handling** - Graceful degradation for edge cases
6. **Unit Tests** - Ensure fix works correctly

### **Low Priority (Nice to Have)**
7. **Frontend Enhancement** - User experience improvement
8. **Documentation Update** - Developer reference

## 📊 Success Criteria

### **Functional Success**
- ✅ Client names preserved through subnet correction workflow
- ✅ No regression in direct upload (no subnet correction) workflow
- ✅ Backward compatibility with existing clients and pending configs
- ✅ Edge cases handled gracefully (special characters, long names, etc.)

### **Technical Success**
- ✅ No breaking changes to existing API endpoints
- ✅ Pending config storage remains efficient and secure
- ✅ Database consistency maintained
- ✅ All tests pass including new regression tests

### **Validation Criteria**
- Upload `company.conf` with `0.0.0.0/0` → final name is `company_{uuid}`
- Upload `valid-client.conf` with proper subnet → final name is `valid-client_{uuid}`
- No error logs or warnings during normal operation
- Pending config cleanup works correctly with filename field

### **User Experience Success**
- Predictable client naming based on uploaded filename
- Clear feedback during subnet correction process
- No confusion about client identity in management interface