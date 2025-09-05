# Manual QA Checklist - OTP Destroyer Enhancement

## Pre-Test Setup
- [ ] Backup branch `feature/otp-menu-ux-backup` exists
- [ ] Database migrations applied successfully
- [ ] Bot starts without errors
- [ ] Test account available for OTP testing

## Database Migration Tests
- [ ] New columns added to accounts table:
  - [ ] `otp_destroyer_enabled` (BOOLEAN)
  - [ ] `otp_destroyed_at` (TIMESTAMP)
  - [ ] `otp_destroyer_disable_auth` (TEXT)
  - [ ] `otp_audit_log` (TEXT/JSON)
  - [ ] `menu_message_id` (INTEGER)
- [ ] New columns added to users table:
  - [ ] `developer_mode` (BOOLEAN)
  - [ ] `main_menu_message_id` (INTEGER)
- [ ] Migration script runs without errors on fresh database
- [ ] Migration script handles existing databases (no duplicate columns)

## Menu System Tests

### Main Menu
- [ ] `/start` shows inline keyboard menu instead of text
- [ ] Main menu has all expected buttons:
  - [ ] 📱 Account Settings
  - [ ] 🛡️ OTP Settings  
  - [ ] 🔐 Sessions
  - [ ] 🔑 2FA Settings
  - [ ] 🟢 Online Maker
  - [ ] ❓ Help
  - [ ] ⚙️ Developer
- [ ] Menu message is persistent (edits instead of creating new messages)
- [ ] Menu message ID is stored in database

### Account Management
- [ ] "Account Settings" shows list of accounts
- [ ] Each account shows status indicators:
  - [ ] 🟢/🔴 for active/inactive
  - [ ] 🛡️/⚪ for OTP destroyer enabled/disabled
- [ ] Clicking account opens account management menu
- [ ] Account menu shows current OTP destroyer status
- [ ] "Back" buttons work correctly

### OTP Settings Menu
- [ ] OTP settings menu shows current status
- [ ] Enable/disable toggle works
- [ ] Audit log button shows historical entries
- [ ] Security settings accessible

## OTP Destroyer Functionality

### Core Features
- [ ] OTP destroyer can be enabled per account
- [ ] OTP destroyer can be disabled per account
- [ ] Status is persisted in database
- [ ] Only enabled accounts process OTP destruction

### Code Detection & Destruction
- [ ] Bot detects service messages from chat 777000
- [ ] Regex correctly extracts OTP codes from various formats:
  - [ ] "Login code: 12345"
  - [ ] "code: 1-2-3-4-5" 
  - [ ] "Your code is 987654"
- [ ] `InvalidateSignInCodesRequest` is called with extracted codes
- [ ] Success/failure is logged in audit trail
- [ ] Owner receives notification of destruction

### Security Features
- [ ] Disable password can be set for accounts
- [ ] Disabling OTP destroyer requires password when set
- [ ] Password is hashed before storage
- [ ] Invalid password attempts are logged
- [ ] Audit log tracks all enable/disable actions

### Audit Logging
- [ ] All OTP destroyer actions are logged with timestamps
- [ ] Audit entries include:
  - [ ] Action type (enable/disable/invalidate)
  - [ ] Timestamp
  - [ ] User ID
  - [ ] Codes destroyed (if applicable)
  - [ ] Success/failure status
- [ ] Audit log is viewable through menu
- [ ] Log entries are limited (max 100, shows last 10)

## Developer Mode
- [ ] Developer mode can be toggled via menu
- [ ] When enabled, text commands are available:
  - [ ] `/add`, `/remove`, `/accs`, `/toggle_protection`
- [ ] When disabled, text commands are hidden
- [ ] Developer mode status persists across sessions

## Error Handling & Edge Cases
- [ ] Invalid callback data handled gracefully
- [ ] Database errors don't crash bot
- [ ] Network errors during code invalidation are logged
- [ ] Menu works with no accounts
- [ ] Menu works with many accounts (>10)
- [ ] Concurrent OTP destruction attempts handled
- [ ] Invalid account IDs in callbacks handled

## Performance & Reliability
- [ ] Menu responses are fast (<2 seconds)
- [ ] OTP destruction happens quickly (<5 seconds)
- [ ] Database queries are efficient
- [ ] Memory usage remains stable
- [ ] No message spam (menus edit instead of creating new)

## Security Validation
- [ ] Session files remain encrypted
- [ ] Database credentials not exposed in logs
- [ ] OTP codes not logged in plaintext
- [ ] Disable passwords properly hashed
- [ ] User isolation (users can't access others' accounts)

## Integration Tests
- [ ] Real OTP code destruction test:
  1. Enable OTP destroyer for test account
  2. Trigger login from another device
  3. Verify code is invalidated
  4. Verify "code expired" error on login attempt
  5. Verify audit log entry created
  6. Verify owner notification sent

## Rollback Testing
- [ ] Can revert to backup branch successfully
- [ ] Database rollback procedure works
- [ ] Session files remain intact after rollback
- [ ] No data loss during rollback

## Documentation
- [ ] README updated with new features
- [ ] Migration instructions clear
- [ ] Security considerations documented
- [ ] QA checklist complete

## Sign-off
- [ ] All critical tests pass
- [ ] No security vulnerabilities identified  
- [ ] Performance acceptable
- [ ] Ready for production deployment

**Tester:** ________________  
**Date:** ________________  
**Version:** ________________