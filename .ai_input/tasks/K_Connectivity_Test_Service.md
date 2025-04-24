# Task K: Connectivity Test Service

## Description
On activation, ping a known host in client subnet, record latency and success/failure.

## Steps
1. Create connectivity testing module
   - Implement ICMP ping functionality
   - Add configurable target host selection
   - Create timeout and retry logic
   - Implement result storage mechanism

2. Integrate with client activation
   - Add hook to perform test after tunnel activation
   - Create background task for periodic testing
   - Implement test history storage

3. Create testing API
   - Implement endpoint to trigger manual test
   - Create endpoint to retrieve test history
   - Add support for custom target selection

4. Implement result handling
   - Format test results for frontend consumption
   - Create alerts for failed tests
   - Implement historical trend analysis

## Human Verification Checkpoints
- [ ] Ping test executes successfully to a target host
- [ ] Test results (latency, success/failure) are properly recorded
- [ ] Automatic tests run after tunnel activation
- [ ] Manual tests can be triggered via API
- [ ] Test history is retrievable via API
- [ ] Verify with real tunnel:
  - [ ] Activate tunnel, observe automatic test
  - [ ] Check test results are accurate
  - [ ] Run manual test, verify results match

## Dependencies
- Task J (Iptables manager must be implemented)
- Task H (WireGuard CLI integration must be implemented)

## Estimated Time
- 3-4 hours 