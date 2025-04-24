# Task F: Subnet Prompt Logic

## Description
On validation failure, store state and expose API to accept user's subnet input then re-validate.

## Steps
1. Create temporary state storage
   - Design data structure to store config pending subnet input
   - Implement storage mechanism (in-memory or DB)
   - Generate unique identifier for each pending config

2. Implement API for subnet submission
   - Create POST /clients/subnet endpoint
   - Accept subnet parameter and config identifier
   - Retrieve stored config using identifier

3. Update config with custom subnet
   - Replace 0.0.0.0/0 with user-provided subnet
   - Validate the new subnet (format, range)
   - Update the stored config

4. Implement response handling
   - Return updated config to frontend
   - Include validation status in response

## Human Verification Checkpoints
- [ ] System correctly stores configs pending subnet input
- [ ] Subnet submission endpoint accepts valid subnet format
- [ ] Config correctly updated with new subnet
- [ ] Validation passes when proper subnet is provided
- [ ] Test with real WireGuard config file, ensure AllowedIPs gets updated

## Dependencies
- Task E (AllowedIPs validation must be implemented)

## Estimated Time
- 2-3 hours 