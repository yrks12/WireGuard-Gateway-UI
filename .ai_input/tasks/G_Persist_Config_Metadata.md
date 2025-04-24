# Task G: Persist Config & Metadata

## Description
Move valid .conf into /etc/wireguard/, record metadata (name, path, subnet, public key) in JSON or SQLite.

## Steps
1. Create storage utility
   - Design database schema (SQLite) or JSON structure
   - Implement CRUD operations for client metadata
   - Create unique ID generation mechanism

2. Implement file storage
   - Create function to move config from temp to permanent location
   - Ensure proper permissions (600) for config files
   - Handle name conflicts with versioning

3. Extract and store metadata
   - Parse config for essential data (name, public key, subnet)
   - Save metadata to database/JSON with file path
   - Link config file to metadata record

4. Implement API endpoints
   - Update existing endpoints to use persistence layer
   - Create GET endpoint to retrieve stored configs

## Human Verification Checkpoints
- [ ] Config files are correctly moved to /etc/wireguard/ with appropriate permissions
- [ ] Metadata is correctly extracted and stored
- [ ] Database/JSON file is created with proper structure
- [ ] API returns proper list of stored configs
- [ ] Test retrieving stored configs after server restart

## Dependencies
- Task F (Subnet prompt logic must be implemented)

## Estimated Time
- 3-4 hours 