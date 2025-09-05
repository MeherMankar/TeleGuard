# RambaZamba OTP Destroyer Enhancement - Upgrade Guide

## Overview

This upgrade transforms RambaZamba from a text-command bot to a modern menu-driven interface with enhanced OTP destroyer functionality, audit logging, and security features.

## 🚨 IMPORTANT - Backup First

**Before upgrading, ensure you have:**
1. ✅ Backup branch: `feature/otp-menu-ux-backup`
2. ✅ Database backup: Copy `bot_data.db` to safe location
3. ✅ Session files backup: Copy all `.session` files
4. ✅ Environment backup: Copy `.env` and `secret.key`

## New Features

### 🎛️ Menu System
- **Inline Keyboard Interface**: Replace text commands with interactive menus
- **Persistent Menus**: Messages update instead of creating spam
- **Developer Mode**: Toggle between menu and text command interfaces

### 🛡️ Enhanced OTP Destroyer
- **Per-Account Control**: Enable/disable OTP destroyer per account
- **Audit Logging**: Complete history of all OTP destruction events
- **Secure Disable**: Password protection for disabling OTP destroyer
- **Real-time Alerts**: Immediate notifications when codes are destroyed

### 🔒 Security Enhancements
- **Password Protection**: Secure disable flow for OTP destroyer
- **Audit Trail**: Complete logging of all security events
- **User Isolation**: Enhanced separation between user accounts

## Database Changes

New columns added:

**accounts table:**
- `otp_destroyer_enabled` - Per-account OTP destroyer toggle
- `otp_destroyed_at` - Timestamp of last OTP destruction
- `otp_destroyer_disable_auth` - Hashed password for secure disable
- `otp_audit_log` - JSON audit trail
- `menu_message_id` - Persistent menu message tracking

**users table:**
- `developer_mode` - Enable/disable text commands
- `main_menu_message_id` - Main menu message tracking

## Installation Steps

### 1. Stop Current Bot
```bash
# Stop your current bot process
pkill -f bot.py
```

### 2. Backup Current Installation
```bash
# Create backup directory
mkdir -p backups/$(date +%Y%m%d)

# Backup database and sessions
cp bot_data.db backups/$(date +%Y%m%d)/
cp *.session backups/$(date +%Y%m%d)/
cp .env backups/$(date +%Y%m%d)/
cp secret.key backups/$(date +%Y%m%d)/
```

### 3. Update Code
```bash
# Switch to feature branch
git checkout feature/otp-menu-ux

# Install any new dependencies
pip install -r requirements.txt
```

### 4. Run Database Migrations
```bash
# Run migrations (automatic on bot start, or manually)
python migrations.py
```

### 5. Start Enhanced Bot
```bash
# Start the enhanced bot
python bot.py
```

## Usage Changes

### Before (Text Commands)
```
/start
/add
/toggle_protection
/accs
```

### After (Menu System)
```
/start → Interactive Menu
├── 📱 Account Settings
├── 🛡️ OTP Settings  
├── 🔐 Sessions
└── ⚙️ Developer Mode (enables text commands)
```

## Migration Guide

### For Existing Users

1. **First Login**: Use `/start` to see the new menu system
2. **Enable Developer Mode**: If you prefer text commands, use menu → Developer Mode
3. **Configure OTP Destroyer**: 
   - Go to Account Settings → Select Account → OTP Settings
   - Enable OTP Destroyer per account
   - Set disable password for security

### For Existing Accounts

- All existing accounts are preserved
- OTP destroyer is **disabled by default** (must be manually enabled)
- Old protection settings are maintained for compatibility

## New Workflow Examples

### Enable OTP Destroyer
1. `/start` → Main Menu
2. "📱 Account Settings" → Select Account
3. "🛡️ OTP Destroyer" → Enable
4. Optionally set disable password

### View Audit Log
1. Main Menu → "📱 Account Settings"
2. Select Account → "📋 View Audit Log"
3. See complete history of OTP events

### Secure Disable
1. Account Settings → OTP Settings
2. "🔒 Set Disable Password" (one-time setup)
3. Future disable attempts require password

## Testing Your Installation

### Quick Test Checklist
- [ ] Bot starts without errors
- [ ] `/start` shows interactive menu
- [ ] Account list displays correctly
- [ ] OTP destroyer can be enabled/disabled
- [ ] Audit log shows entries
- [ ] Developer mode toggle works

### OTP Destroyer Test
1. Enable OTP destroyer for test account
2. Attempt login from another device
3. Verify code is destroyed and login fails
4. Check audit log for destruction entry
5. Verify alert notification received

## Troubleshooting

### Migration Issues
```bash
# If migration fails, check logs
python migrations.py

# Manual column addition if needed
sqlite3 bot_data.db "ALTER TABLE accounts ADD COLUMN otp_destroyer_enabled BOOLEAN DEFAULT FALSE;"
```

### Menu Not Working
- Ensure bot has proper permissions
- Check for callback query handler registration
- Verify database migrations completed

### OTP Destroyer Not Working
- Verify account has `otp_destroyer_enabled = TRUE`
- Check client connection for monitored account
- Ensure service message listener is active

## Rollback Procedure

If issues occur:

```bash
# 1. Stop enhanced bot
pkill -f bot.py

# 2. Switch to backup branch
git checkout feature/otp-menu-ux-backup

# 3. Restore database
cp backups/$(date +%Y%m%d)/bot_data.db ./

# 4. Restore sessions
cp backups/$(date +%Y%m%d)/*.session ./

# 5. Start original bot
python bot.py
```

## Support

### Getting Help
- Check `manual_qa_checklist.md` for testing procedures
- Review logs for error messages
- Test with disposable account first

### Reporting Issues
Include in bug reports:
- Bot logs (redact sensitive info)
- Database schema version
- Steps to reproduce
- Expected vs actual behavior

## Security Notes

### Important Security Changes
- OTP destroyer now requires explicit per-account enabling
- Disable passwords are hashed (SHA-256)
- All actions are audit logged
- User isolation enhanced

### Best Practices
- Set disable passwords for critical accounts
- Regularly review audit logs
- Test OTP destroyer with disposable accounts first
- Keep backups of session files encrypted

---

**Upgrade completed successfully!** 🎉

Your RambaZamba bot now has enhanced OTP destroyer capabilities with a modern menu interface.