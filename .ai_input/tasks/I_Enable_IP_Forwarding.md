# Task I: Enable IP Forwarding

## Description
Ensure net.ipv4.ip_forward=1 via sysctl, persist in /etc/sysctl.conf if needed.

## Steps
1. Create IP forwarding service
   - Implement function to check current IP forwarding status
   - Create method to enable IP forwarding temporarily
   - Create method to enable IP forwarding permanently

2. Implement sysctl configuration
   - Create function to modify /etc/sysctl.conf
   - Implement backup mechanism before modifications
   - Add validation for successful changes

3. Add activation hooks
   - Connect to WireGuard activation workflow
   - Enable forwarding when first tunnel is activated
   - Add check during application startup

4. Create error handling
   - Detect permission issues
   - Implement fallback options
   - Provide clear error messages for troubleshooting

## Human Verification Checkpoints
- [ ] IP forwarding can be checked via the application
- [ ] IP forwarding can be enabled temporarily via sysctl
- [ ] IP forwarding setting persists after system reboot
- [ ] Verify with `cat /proc/sys/net/ipv4/ip_forward` shows "1"
- [ ] Test that WireGuard tunnel activation enables forwarding automatically

## Dependencies
- Task H (WireGuard CLI integration must be implemented)

## Estimated Time
- 2-3 hours 