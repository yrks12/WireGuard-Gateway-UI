# Task D: Config Upload Endpoint

## Description
Implement POST /clients/upload to accept .conf files, save temporarily, return parse result.

## Steps
1. Create route handler for file uploads
   - Implement POST /clients/upload endpoint
   - Set up file validation middleware (ensure .conf extension)
   - Configure temporary file storage

2. Implement WireGuard config parser
   - Create utility to parse [Interface] and [Peer] sections
   - Extract key information (public key, AllowedIPs)
   - Validate basic config structure

3. Create response handler
   - Format parsed data for client
   - Include validation results
   - Handle errors gracefully

4. Add security measures
   - Limit file size
   - Sanitize filenames
   - Implement rate limiting

## Human Verification Checkpoints
- [ ] Endpoint accepts valid .conf files
- [ ] Temporary files are stored securely
- [ ] Parser correctly extracts [Interface] and [Peer] information
- [ ] Response contains all necessary information for frontend
- [ ] Invalid files are rejected with appropriate error messages
- [ ] Test with actual WireGuard .conf files from PRD examples

## Dependencies
- Task C (Backend framework must be scaffolded)

## Estimated Time
- 3-4 hours 