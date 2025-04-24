# Task N: Real-Time Status Polling

## Description
Implement periodic (e.g. WebSocket or polling) fetch of each client's last handshake, ping status, system metrics.

## Steps
1. Create status polling service
   - Implement WireGuard status retrieval (last handshake)
   - Create system metrics collection (CPU, RAM)
   - Implement ping status retrieval
   - Create data aggregation mechanism

2. Implement real-time communication
   - Choose technology (WebSocket or HTTP polling)
   - Set up server-side event handling
   - Configure update frequency
   - Implement client connection management

3. Create API endpoints
   - Implement GET /status for one-time polling
   - Create WebSocket endpoint if applicable
   - Add configuration options for polling frequency

4. Optimize for performance
   - Implement caching for frequent requests
   - Create batching for multiple metrics
   - Minimize system impact of polling operations

## Human Verification Checkpoints
- [ ] System correctly retrieves last handshake time for tunnels
- [ ] CPU and RAM usage metrics are collected
- [ ] Real-time updates are sent to frontend
- [ ] Status updates contain all required information
- [ ] Test with real tunnels:
  - [ ] Activate tunnel
  - [ ] Observe real-time status updates
  - [ ] Verify handshake time updates correctly
  - [ ] Verify system metrics are accurate

## Dependencies
- Task M (CRUD API for clients must be implemented)

## Estimated Time
- 3-4 hours 