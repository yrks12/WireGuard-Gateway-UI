# Task U: Unit Tests (Backend)

## Description
Write pytest suites covering parser, validation, CLI wrappers, iptables manager, route generator.

## Steps
1. Set up testing framework
   - Configure pytest environment
   - Create fixture system for common test resources
   - Implement mock objects for system dependencies
   - Set up test database if needed

2. Write parser and validation tests
   - Create tests for WireGuard config parsing
   - Implement validation logic tests
   - Add tests for error handling
   - Create test cases with various config formats

3. Implement CLI and system tests
   - Create mock subprocess for WireGuard commands
   - Implement tests for WireGuard CLI wrapper
   - Add tests for iptables manager
   - Create tests for IP forwarding functionality

4. Add service layer tests
   - Implement route generator tests
   - Create client service tests
   - Add connectivity test service tests
   - Implement metrics service tests

## Human Verification Checkpoints
- [ ] Test suite runs successfully with pytest
- [ ] Tests cover all key components
- [ ] Mocks properly simulate system dependencies
- [ ] All tests pass in CI environment
- [ ] Test coverage meets acceptable threshold (e.g., >80%)
- [ ] Verify that tests catch regressions:
  - [ ] Introduce deliberate bug, confirm test fails
  - [ ] Fix bug, confirm test passes

## Dependencies
- Tasks D-N (All backend components must be implemented)

## Estimated Time
- 4-5 hours 