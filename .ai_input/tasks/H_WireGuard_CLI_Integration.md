# Task H: WireGuard CLI Integration

## Description
Wrap wg-quick up/down in a Python module, capture stdout/stderr, handle errors.

## Steps
1. Create WireGuard service module
   - Implement function to execute wg-quick commands
   - Create wrapper for 'up' operation
   - Create wrapper for 'down' operation
   - Add status check functionality

2. Implement subprocess handling
   - Set up secure subprocess execution
   - Capture and parse command output
   - Implement timeout mechanism
   - Handle permission issues (sudo requirements)

3. Create error handling
   - Define error types for different failure modes
   - Implement proper exception handling
   - Format error messages for frontend consumption

4. Add logging
   - Log all WireGuard commands and outputs
   - Create audit trail for operations
   - Include timestamps and operation status

## Human Verification Checkpoints
- [ ] `wg-quick up` command executes successfully via Python
- [ ] `wg-quick down` command executes successfully via Python
- [ ] Command outputs and errors are properly captured
- [ ] Error conditions are handled gracefully
- [ ] Test with actual WireGuard configs:
  - [ ] Activate a tunnel
  - [ ] Verify tunnel is up (using `wg show`)
  - [ ] Deactivate tunnel
  - [ ] Verify tunnel is down

## Dependencies
- Task G (Config persistence must be implemented)

## Estimated Time
- 3-4 hours 