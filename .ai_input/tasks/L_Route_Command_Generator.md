# Task L: Route Command Generator

## Description
Compute and return ip route add <subnet> via <gateway-LAN-IP> dev <iface> string for display.

## Steps
1. Create route command generator module
   - Implement function to determine gateway LAN IP
   - Create method to identify main network interface
   - Implement command string formatting

2. Integrate with client metadata
   - Extract client subnet from stored metadata
   - Link generator with client activation process
   - Update client record with generated command

3. Create API endpoint
   - Implement endpoint to retrieve route command
   - Create batch endpoint for all active clients
   - Add support for custom interface selection

4. Implement advanced features
   - Add support for different router command formats
   - Create copy-to-clipboard functionality for frontend
   - Implement command verification logic

## Human Verification Checkpoints
- [ ] System correctly identifies gateway LAN IP
- [ ] Route command is correctly generated in format: `ip route add <subnet> via <gateway-LAN-IP> dev <iface>`
- [ ] Command is stored with client metadata
- [ ] API returns correct route command for each client
- [ ] Test with real client subnet:
  - [ ] Activate tunnel
  - [ ] Verify command format is correct
  - [ ] Apply command on router (if possible)
  - [ ] Verify routing works as expected

## Dependencies
- Task G (Config persistence must be implemented)

## Estimated Time
- 2-3 hours 