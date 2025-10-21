# OTP Destroyer & Forward Fixes

## Issues Fixed

### 1. Handler Registration Problems
- **Problem**: OTP handlers weren't being registered properly for active clients
- **Fix**: Enhanced `register_handlers()` method with better error handling and logging
- **Location**: `teleguard/core/otp_manager.py`

### 2. Missing Handler Re-registration
- **Problem**: When enabling/disabling OTP features, handlers weren't being refreshed
- **Fix**: Added automatic handler re-registration in `toggle_destroyer()` and `toggle_forward()`
- **Location**: `teleguard/core/otp_manager.py`

### 3. Connection Validation
- **Problem**: Handlers were being registered on disconnected clients
- **Fix**: Added proper connection checks before registering handlers
- **Location**: `teleguard/core/otp_destroyer.py` and `teleguard/core/otp_manager.py`

### 4. Initialization Issues
- **Problem**: OTP handlers weren't being registered during bot startup
- **Fix**: Added handler registration during OTP manager initialization
- **Location**: `teleguard/core/bot_manager.py`

## New Debug Features

### Admin Commands Added
1. **`/otp_debug`** - Shows detailed OTP status:
   - OTP Manager status
   - Registered handler count
   - Account OTP settings
   - Client connection status

2. **`/otp_fix`** - Force re-register OTP handlers:
   - Clears existing handlers
   - Re-registers for all active clients
   - Shows before/after handler counts

### Test Scripts
1. **`test_otp.py`** - Database OTP settings checker
2. **`start_bot.py`** - Simple bot startup for testing

## How to Test

1. **Start the bot**:
   ```bash
   python start_bot.py
   ```

2. **Check OTP status** (admin only):
   ```
   /otp_debug
   ```

3. **Fix OTP handlers** if needed (admin only):
   ```
   /otp_fix
   ```

4. **Test OTP functionality**:
   - Add an account via `/start`
   - Enable OTP Destroyer in account settings
   - Send yourself a login code from another device
   - Check if it gets destroyed/forwarded

## Key Improvements

- ✅ Better error handling and logging
- ✅ Automatic handler re-registration
- ✅ Connection validation
- ✅ Debug commands for troubleshooting
- ✅ Proper initialization sequence
- ✅ Status feedback during startup

## Expected Behavior

- **OTP Destroyer ON**: Login codes are automatically invalidated and user gets notification
- **OTP Forward ON**: Login codes are forwarded to user via bot (when destroyer is OFF)
- **Both OFF**: Login codes remain in Telegram normally

The fixes ensure handlers are properly registered and active for all connected accounts.