# Account Removal with Session Termination

## Overview

The account removal functionality has been enhanced to properly terminate Telegram sessions when removing accounts from TeleGuard, similar to how the official Telegram app handles logout.

## Changes Made

### 1. Enhanced Session Termination

When removing an account, TeleGuard now:
- **Calls `LogOutRequest()`** - Terminates the active Telegram session
- **Disconnects the client** - Closes the local connection
- **Removes from database** - Cleans up all stored data
- **Removes 2FA passwords** - Clears stored authentication data

### 2. Updated Methods

The following methods in `bot_manager.py` have been updated:

- `remove_account_by_id()` - Primary removal method with session termination
- `remove_user_account()` - Alternative removal method with session termination  
- `remove_account()` - Compatibility method (updated comments)

### 3. User Interface Updates

The menu system now clearly indicates:
- **Confirmation dialog** explains that the account will be "logged out from Telegram"
- **Success message** confirms "Session terminated from Telegram"
- **Clear warnings** that the action cannot be undone

## Technical Implementation

```python
# Before removal, terminate the Telegram session
from telethon.tl.functions.auth import LogOutRequest
await client(LogOutRequest())
logger.info(f"Terminated Telegram session for {account_name}")

# Then disconnect and cleanup
await client.disconnect()
```

## Benefits

1. **Complete Session Cleanup** - Sessions no longer appear in Telegram's "Active Sessions" 
2. **Security Enhancement** - Prevents unauthorized access to terminated accounts
3. **User Clarity** - Clear messaging about what happens during removal
4. **Telegram Compliance** - Follows official logout procedures

## User Experience

When a user removes an account:

1. **Warning Dialog** - Clearly explains session will be terminated
2. **Session Logout** - Account is logged out from Telegram servers
3. **Data Cleanup** - All TeleGuard data is removed
4. **Confirmation** - User receives confirmation of successful removal

## Error Handling

The implementation includes robust error handling:
- If `LogOutRequest()` fails, the client is still disconnected
- Warnings are logged for failed session terminations
- Database cleanup proceeds regardless of session termination status
- User receives appropriate error messages if removal fails

## Testing

A test script `test_logout.py` has been created to verify:
- `LogOutRequest` import functionality
- Basic request creation and usage
- Telethon compatibility

## Backward Compatibility

This update is fully backward compatible:
- Existing accounts continue to work normally
- No database schema changes required
- All existing functionality preserved