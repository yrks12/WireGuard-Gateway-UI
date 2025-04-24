# Task S: System Metrics Integration

## Description
- Backend: Gather CPU/RAM via psutil.
- Frontend: Show live gauges or sparkline charts, refresh every 30 s.

## Steps
1. Implement backend metrics collection
   - Create metrics service using psutil
   - Implement CPU usage monitoring
   - Implement memory usage monitoring
   - Add disk and network metrics if desired

2. Create metrics API
   - Implement GET /metrics endpoint
   - Add historical data storage if needed
   - Create efficient serialization format
   - Implement caching to reduce system impact

3. Create frontend visualizations
   - Implement gauge components for CPU/RAM
   - Create sparkline/line charts for trends
   - Add threshold indicators
   - Implement auto-refresh mechanism

4. Integrate with dashboard
   - Add metrics panel to dashboard
   - Create collapsible/expandable detailed view
   - Implement refresh controls
   - Add export functionality if needed

## Human Verification Checkpoints
- [ ] Backend correctly collects CPU and RAM metrics
- [ ] API endpoint returns valid metrics data
- [ ] Frontend displays metrics in gauges/charts
- [ ] Automatic refresh occurs every 30 seconds
- [ ] Test system monitoring:
  - [ ] Verify CPU metrics accuracy
  - [ ] Verify RAM metrics accuracy
  - [ ] Create system load, observe updates
  - [ ] Check that refresh interval is correct

## Dependencies
- Task N (Real-time status polling must be implemented) for backend
- Task O (Frontend skeleton must be implemented) for frontend

## Estimated Time
- 3-4 hours 