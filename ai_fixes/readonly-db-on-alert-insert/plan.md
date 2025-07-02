# 🛠️ Fix Plan: Readonly Database on Alert Insert

## 🧩 Issue Summary

The WireGuard Gateway application fails to insert alert history records into the SQLite database with the error:

```
(sqlite3.OperationalError) attempt to write a readonly database
```

This occurs during disconnect alert operations when `AlertHistory.add_alert()` is called from the monitoring system. The error indicates a SQLAlchemy session management issue combined with insufficient error handling, rather than actual file permission problems.

**Evidence from Analysis:**
- Database file permissions are correct: `0666 (-rw-rw-rw-)`
- Database owner is correct: `wireguard:wireguard`
- Error appears intermittent and may be related to session state corruption
- Subsequent database operations fail due to rolled-back SQLAlchemy sessions

## 🔍 Root Cause

The issue stems from inadequate database session management and error handling in multi-threaded operations:

### **Primary Issues**

#### 1. **No Error Handling in AlertHistory.add_alert()** (`app/models/alert_history.py:25-26`)
```python
@classmethod
def add_alert(cls, client_name: str, peer_key: str, subject: str, message: str, success: bool = True):
    alert = cls(...)
    db.session.add(alert)
    db.session.commit()  # No try/except - any error leaves session in bad state
```

#### 2. **SQLAlchemy Session State Corruption**
When the first readonly database error occurs:
- SQLAlchemy session enters a rolled-back state
- Subsequent operations fail with session state errors
- No session recovery mechanism exists
- Background monitoring thread continues with corrupted session

#### 3. **Multi-threaded Database Access** (`app/tasks.py:14-15`)
```python
def monitor_wireguard(app):
    with app.app_context():  # Background thread context
        # Database operations without proper session management
```

#### 4. **Race Conditions During Database Operations**
- Multiple monitoring threads potentially accessing database simultaneously
- No proper transaction scoping for background operations
- SQLite file locking conflicts under high load

### **Secondary Contributing Factors**

#### 5. **Missing Database Connection Configuration**
- No SQLAlchemy connection pooling configuration for multi-threaded access
- Default SQLite settings may not handle concurrent access optimally
- No retry mechanism for transient database errors

#### 6. **Inadequate Logging of Database Issues**
- Database errors not properly logged with context
- No visibility into session state or transaction conflicts
- Difficult to diagnose root cause of readonly errors

## ✅ Proposed Fix Plan

### 1. **Robust Error Handling in AlertHistory.add_alert()**
   - Add comprehensive try/catch with session rollback
   - Implement retry logic for transient database errors
   - Proper logging of database operation failures
   - Session state recovery after errors

### 2. **SQLAlchemy Session Management Enhancement**
   - Configure scoped sessions for background threads
   - Implement proper session lifecycle management
   - Add session rollback and cleanup on errors
   - Ensure each background task has isolated session

### 3. **Database Connection Configuration**
   - Configure SQLAlchemy with connection pooling for multi-threaded access
   - Set appropriate SQLite pragmas for concurrent access
   - Add connection timeout and retry settings
   - Implement database connection health checks

### 4. **Background Task Session Isolation**
   - Use database session per monitoring cycle
   - Implement proper transaction boundaries
   - Add session cleanup in finally blocks
   - Isolate alert insertion from other database operations

### 5. **Improved Error Recovery and Logging**
   - Enhanced logging for database operations with session state
   - Automatic session recovery after database errors
   - Graceful degradation when database is temporarily unavailable
   - Clear error messages for debugging

### 6. **Database Operation Atomicity**
   - Ensure all alert operations are atomic
   - Implement proper transaction scoping
   - Add rollback handling for partial operations
   - Prevent session state corruption

## 🧪 Test Plan

### 1. **Database Error Handling Test**
   - Simulate readonly database conditions
   - Verify proper error handling and session recovery
   - Test alert insertion continues after database errors
   - **Expected**: Graceful error handling with session recovery

### 2. **Multi-threaded Database Access Test**
   - Run multiple monitoring threads simultaneously
   - Generate high volume of alert insertions
   - Test database under concurrent access load
   - **Expected**: No readonly database errors under load

### 3. **Session State Recovery Test**
   - Force database error during alert insertion
   - Verify subsequent database operations succeed
   - Test session rollback and recovery mechanisms
   - **Expected**: Clean session state after errors

### 4. **Background Monitoring Resilience Test**
   - Run monitoring for extended periods
   - Simulate various database error conditions
   - Test monitoring continues despite database issues
   - **Expected**: Monitoring remains functional with degraded alert storage

### 5. **Database Connection Pool Test**
   - Test database operations with configured connection pooling
   - Verify proper connection lifecycle management
   - Test connection exhaustion scenarios
   - **Expected**: Stable database performance under various load conditions

### 6. **Alert History Functionality Test**
   - Verify alert insertion works correctly after fixes
   - Test alert history display in web interface
   - Validate data integrity of stored alerts
   - **Expected**: All alert functionality works without database errors

### 7. **System Restart and Recovery Test**
   - Restart service during high alert volume
   - Test database recovery after system restart
   - Verify no data corruption or session issues
   - **Expected**: Clean startup with functional alert system

## 🧯 Rollback Plan

### **Safe Rollback Strategy**
1. **Code Revert**: Git revert database session management changes
2. **Restore Original Behavior**: Original alert insertion without enhanced error handling
3. **Session Management**: Revert to simple session usage (may have original issues)
4. **No Data Loss**: Alert history table structure unchanged

### **Compatibility Considerations**
- New error handling is additive - no breaking changes
- Enhanced session management backward compatible
- Database schema remains unchanged
- Existing alert history preserved

### **Emergency Procedures**
- Disable alert insertion temporarily if database issues persist
- Manual database repair procedures if corruption occurs
- Service restart to reset session state
- Alternative logging mechanism if database unavailable

## 📁 Related Files

**Primary Files (Require Changes):**
- `app/models/alert_history.py` - Add robust error handling to add_alert() method
- `app/tasks.py` - Enhance session management in background monitoring
- `app/__init__.py` - Configure SQLAlchemy for multi-threaded access
- `app/services/wireguard_monitor.py` - Improve error handling around alert insertion

**Secondary Files (Testing/Validation):**
- `app/database.py` - Database configuration and session management
- `tests/models/test_alert_history.py` - Unit tests for alert insertion error handling
- `tests/services/test_wireguard_monitor.py` - Integration tests for monitoring with database errors

**Configuration Files:**
- Database connection settings in app configuration
- SQLite pragma configuration for concurrent access

## 🎯 Implementation Priority

### **Critical Priority (Must Fix)**
1. **Error Handling in AlertHistory.add_alert()** - Prevent session corruption
2. **Session Rollback Management** - Recover from database errors
3. **Background Thread Session Isolation** - Prevent concurrent access issues

### **High Priority (Should Fix)**
4. **SQLAlchemy Connection Configuration** - Optimize for multi-threaded access
5. **Enhanced Error Logging** - Improve debugging and monitoring
6. **Transaction Boundary Management** - Ensure atomic operations

### **Medium Priority (Enhancement)**
7. **Retry Logic for Transient Errors** - Handle temporary database issues
8. **Database Health Monitoring** - Proactive issue detection
9. **Performance Optimization** - Optimize database operations

### **Low Priority (Nice to Have)**
10. **Alternative Alert Storage** - Fallback when database unavailable
11. **Database Metrics Collection** - Operational insights
12. **Connection Pool Monitoring** - Advanced diagnostics

## 📊 Success Criteria

### **Functional Success**
- ✅ No readonly database errors during normal operation
- ✅ Alert insertion continues to work despite transient database errors
- ✅ Monitoring system remains functional with degraded database access
- ✅ Alert history displays correctly in web interface

### **Technical Success**
- ✅ Proper SQLAlchemy session management in multi-threaded environment
- ✅ Database errors handled gracefully with automatic recovery
- ✅ Session state remains clean after database errors
- ✅ No database connection leaks or session corruption

### **Validation Criteria**
- Run monitoring for 24+ hours without readonly database errors
- Force database errors and verify system recovers automatically
- High-volume alert generation works without session issues
- Database operations remain stable under concurrent access

### **Operational Success**
- Clear error messages for database issues with actionable information
- Monitoring continues to function even with intermittent database problems
- Alert history functionality reliable and consistent
- No manual intervention required for database session recovery

### **Performance Success**
- Alert insertion latency remains low (< 100ms)
- Database connection pool prevents resource exhaustion
- Memory usage stable during extended monitoring operations
- No performance degradation from enhanced error handling