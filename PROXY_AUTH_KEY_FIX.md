# Proxy Assignment - How It Works

## How Official Telegram Clients Handle Proxy Changes

When you change proxy in official Telegram clients (Telegram, Telegram X, Plus):

1. **Disconnect** from current connection
2. **Reconnect** using the new proxy
3. **Same session** - no re-authentication needed
4. **Seamless** - happens in background

## How TeleGuard Now Handles It

TeleGuard now works **exactly like official clients**:

1. ✅ Assign proxy to account
2. ✅ Automatically disconnect old connection
3. ✅ Reconnect with new proxy
4. ✅ Same session - no re-login needed
5. ✅ Seamless transition

## Technical Implementation

```python
# When you assign a proxy:
1. Save proxy_id to account in database
2. Disconnect current client connection
3. Create new client with same session + new proxy
4. Reconnect to Telegram through proxy
5. Done! Same session, new IP
```

## Why This Works

- **Same session string** = Same auth_key
- **Disconnect first** = Clean connection closure
- **Reconnect with proxy** = New connection from proxy IP
- **Telegram sees** = Normal reconnection (like network change)
- **No AUTH_KEY_DUPLICATED** = Only one active connection

## What Changed

### Before (Wrong):
- Assigned proxy but kept old connection active
- Two connections: one direct, one through proxy
- Telegram saw duplicate auth_key from different IPs
- Result: AUTH_KEY_DUPLICATED error

### Now (Correct):
- Disconnect old connection completely
- Only one connection: through proxy
- Telegram sees normal reconnection
- Result: Success ✅

## Usage

1. Go to Account Settings → Proxy Management
2. Assign proxy to account
3. Bot automatically reconnects
4. Done! No manual restart needed

## Summary

**TeleGuard now handles proxies exactly like official Telegram clients** - seamless proxy switching without re-authentication.
