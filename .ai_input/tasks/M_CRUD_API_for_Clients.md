# Task M: CRUD API for Clients

## Description
Expose REST endpoints to list, view, activate, deactivate, delete client entries.

## Steps
1. Create client controller
   - Implement GET /clients endpoint (list all clients)
   - Create GET /clients/{id} endpoint (view specific client)
   - Implement DELETE /clients/{id} endpoint

2. Implement activation endpoints
   - Create POST /clients/{id}/activate endpoint
   - Create POST /clients/{id}/deactivate endpoint
   - Add status tracking and response handling

3. Integrate with existing services
   - Connect with WireGuard CLI service
   - Link with iptables manager
   - Utilize connectivity test service
   - Integrate with route generator

4. Add request validation and error handling
   - Implement input validation
   - Create comprehensive error responses
   - Add transaction handling for multi-step operations

## Human Verification Checkpoints
- [ ] API returns list of all clients
- [ ] Individual client details can be retrieved
- [ ] Client can be activated via API
- [ ] Client can be deactivated via API
- [ ] Client can be deleted via API
- [ ] All operations trigger appropriate backend actions
- [ ] Test complete workflow:
  - [ ] Upload config
  - [ ] List clients, find new client
  - [ ] Activate client
  - [ ] Verify tunnel and rules are active
  - [ ] Deactivate client
  - [ ] Verify tunnel and rules are removed
  - [ ] Delete client
  - [ ] Verify client is removed from listing

## Dependencies
- Task K (Connectivity test service must be implemented)
- Task J (Iptables manager must be implemented)
- Task H (WireGuard CLI integration must be implemented)
- Task L (Route command generator must be implemented)

## Estimated Time
- 3-4 hours 