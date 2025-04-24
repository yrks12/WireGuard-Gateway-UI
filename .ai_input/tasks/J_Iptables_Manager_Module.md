# Task J: Iptables Manager Module

## Description
Create functions to add/remove NAT (POSTROUTING MASQUERADE) and FORWARD rules for each peer interface.

## Steps
1. Create iptables service module
   - Implement function to execute iptables commands securely
   - Create method to check existing rules
   - Implement rule addition with idempotence (don't add if exists)
   - Implement rule removal

2. Implement NAT rules management
   - Create function to add POSTROUTING MASQUERADE rule for interface
   - Create function to remove POSTROUTING MASQUERADE rule
   - Create utility to find interface by name

3. Implement FORWARD rules management
   - Create function to add FORWARD rules for client subnets
   - Create function to add RELATED,ESTABLISHED rules
   - Create function to remove all rules for a given interface

4. Add persistence mechanism
   - Integrate with iptables-persistent
   - Implement rule saving functionality
   - Create backup mechanism for current ruleset

## Human Verification Checkpoints
- [ ] NAT rules can be added via the application
- [ ] FORWARD rules can be added via the application
- [ ] Rules are correctly removed when requested
- [ ] Verify rules are applied with `sudo iptables -L -t nat` and `sudo iptables -L`
- [ ] Rules persist after system reboot
- [ ] Test with real WireGuard interface:
  - [ ] Activate interface, verify rules applied
  - [ ] Deactivate interface, verify rules removed

## Dependencies
- Task I (IP forwarding must be implemented)

## Estimated Time
- 4-5 hours 