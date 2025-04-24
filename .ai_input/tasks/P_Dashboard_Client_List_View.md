# Task P: Dashboard Client List View

## Description
Table showing all clients with columns: Name, Subnet, Status, Last Handshake, Actions.

## Steps
1. Create dashboard component
   - Implement responsive layout for dashboard
   - Create header with metrics and actions
   - Implement filter and search functionality
   - Add error handling for API failures

2. Implement client table
   - Create table component with sortable columns
   - Implement pagination if needed
   - Create status indicator (active/inactive)
   - Format last handshake time properly

3. Add action buttons
   - Create activate/deactivate toggle
   - Implement view details button
   - Add delete client functionality
   - Create confirmation dialogs for destructive actions

4. Connect with API
   - Implement data fetching from client API
   - Create loading states
   - Add error handling
   - Implement refresh mechanism

## Human Verification Checkpoints
- [ ] Dashboard loads and displays clients from API
- [ ] Table shows all required columns
- [ ] Status is correctly indicated
- [ ] Last handshake time format is human-readable
- [ ] Action buttons are present and visually distinct
- [ ] Test actions:
  - [ ] Activate button works
  - [ ] Deactivate button works
  - [ ] View details navigates to correct page
  - [ ] Delete shows confirmation and works

## Dependencies
- Task O (Frontend skeleton must be implemented)
- Task M (CRUD API for clients must be implemented)

## Estimated Time
- 3-4 hours 