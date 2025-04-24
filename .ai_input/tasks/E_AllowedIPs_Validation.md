# Task E: AllowedIPs Validation

## Description
Parse peer AllowedIPs; block 0.0.0.0/0, return error prompting for specific subnet.

## Steps
1. Enhance the WireGuard config parser
   - Extract AllowedIPs from [Peer] section
   - Implement validation logic for CIDR notation

2. Create validation rules
   - Check for 0.0.0.0/0 in AllowedIPs
   - Validate subnet format (x.x.x.x/y)
   - Ensure subnet is valid (e.g., not 127.0.0.0/8)

3. Implement error handling
   - Return specific error for 0.0.0.0/0
   - Include guidance in error message to provide specific subnet
   - Handle multiple AllowedIPs entries

4. Update API response
   - Include validation errors in response
   - Format response for frontend consumption

## Human Verification Checkpoints
- [ ] Parser correctly identifies 0.0.0.0/0 in AllowedIPs
- [ ] Validation rejects configs with 0.0.0.0/0 and returns appropriate error
- [ ] Error message includes clear guidance for user
- [ ] Valid subnet formats are correctly accepted
- [ ] Test with multiple real WireGuard configs (some with 0.0.0.0/0, some with valid subnets)

## Dependencies
- Task D (Config upload endpoint must be implemented)

## Estimated Time
- 2-3 hours 