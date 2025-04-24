# Task R: Activation/Deactivation Controls

## Description
Buttons to call backend API for up/down; show loading state and success/error feedback.

## Steps
1. Create control components
   - Implement toggle or button components
   - Create loading state indicators
   - Implement success/error feedback elements
   - Add confirmation dialog for state changes

2. Connect with activation API
   - Create activation service module
   - Implement API calls to backend
   - Add proper error handling
   - Create retry mechanism for failures

3. Implement state management
   - Update global state with client status
   - Create optimistic UI updates
   - Handle concurrency issues
   - Implement proper state rollback on failure

4. Add user feedback
   - Create toast notifications for success/failure
   - Implement detailed error messages
   - Add action logs for user reference
   - Create help tooltips for common issues

## Human Verification Checkpoints
- [ ] Activation button correctly calls API and shows loading state
- [ ] Deactivation button correctly calls API and shows loading state
- [ ] Success/error feedback is clearly displayed
- [ ] UI updates promptly after status change
- [ ] Test with real client:
  - [ ] Activate client, verify interface comes up
  - [ ] Deactivate client, verify interface goes down
  - [ ] Test error handling (e.g., trigger error and verify feedback)

## Dependencies
- Task P (Dashboard client list must be implemented)
- Task Q (Client detail view must be implemented)
- Task M (CRUD API must be implemented)

## Estimated Time
- 2-3 hours 