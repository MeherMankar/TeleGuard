# Session Protection System

## Overview

TeleGuard includes a comprehensive session protection system to prevent `AUTH_KEY_UNREGISTERED` (401) and `AUTH_KEY_DUPLICATED` (406) errors that cause session revocation.

## Features

- **AUTH_KEY Error Detection**: Automatically detects and handles session revocation
- **Session Locking**: Prevents multiple processes from using the same session
- **Rate Limiting**: Token bucket rate limiter to prevent abuse-like behavior
- **Emergency Shutdown**: Safe shutdown with detailed logging and admin alerts
- **Exponential Backoff**: Intelligent retry mechanism with jitter
- **Activity Monitoring**: Comprehensive logging and periodic summaries

## Configuration

### Environment Variables

```bash
# Required
PHONE_NUMBER=+1234567890                    # Your phone number for alerts

# Rate Limiting (messages/actions per time period)
MAX_MESSAGES_PER_MINUTE=20                  # Default: 20
MAX_JOINS_PER_HOUR=10                       # Default: 10  
MAX_FORWARDS_PER_MINUTE=10                  # Default: 10
MAX_BULK_PER_MINUTE=5                       # Default: 5

# Retry Settings
MAX_RETRY_ATTEMPTS=5                        # Default: 5
RETRY_BASE_DELAY=0.5                        # Default: 0.5 seconds
RETRY_MAX_DELAY=60.0                        # Default: 60 seconds

# Telegram Logging (for admin alerts)
LOG_BOT_TOKEN=123456:ABC-DEF...             # Bot token for alerts
LOG_CHAT_ID=-1001234567890                  # Chat ID for alerts
TELEGRAM_LOGGING_ENABLED=true               # Default: true

# Session Lock
SESSION_LOCK_ENABLED=true                   # Default: true
SESSION_LOCK_TIMEOUT=300                    # Default: 5 minutes

# Emergency Settings
AUTO_SHUTDOWN_ON_AUTH_ERROR=true            # Default: true
DELETE_SESSION_ON_REVOKE=false              # Default: false (manual only)
NOTIFY_ADMIN_ON_ERROR=true                  # Default: true

# Logging
LOG_DIR=logs                                # Default: logs
SUMMARY_INTERVAL=36000                      # Default: 10 hours
```

## Recovery Procedures

### When AUTH_KEY_UNREGISTERED Occurs

1. **Stop all bot processes immediately**
   ```bash
   # Linux/macOS
   pkill -f "python.*teleguard"
   
   # Windows
   taskkill /f /im python.exe
   ```

2. **Delete session files**
   ```bash
   # Linux/macOS
   rm *.session *.session-journal *.lock
   
   # Windows
   del *.session *.session-journal *.lock
   ```

3. **Check for conflicting processes**
   ```bash
   # Look for other bots using the same account
   ps aux | grep telegram
   netstat -tulpn | grep :443
   ```

4. **Re-authenticate manually**
   ```bash
   python main.py
   # Follow the authentication prompts
   ```

### API Credentials Rotation

If session issues persist, rotate your API credentials:

1. **Visit https://my.telegram.org**
2. **Go to API Development Tools**
3. **Create a new application**
4. **Update your .env file**:
   ```bash
   API_ID=new_api_id
   API_HASH=new_api_hash
   ```
5. **Delete old session files and re-authenticate**

## Usage

### Initialize Session Guardian

```python
from teleguard.core.session_guardian import init_guardian
from teleguard.utils.guardian_config import load_guardian_config
from teleguard.utils.protected_client import create_protected_client

# Load configuration
config = load_guardian_config()

# Initialize guardian
guardian = init_guardian(config)

# Create protected client
client = create_protected_client('session_name', api_id, api_hash)
```

### Protected Operations

The system automatically protects dangerous operations:

```python
# These are automatically rate-limited and protected
await client.send_message("chat", "message")
await client.join_channel("channel")
await client.forward_messages("from_chat", "to_chat", message_ids)
```

### Manual Rate Limiting

```python
# Apply custom rate limiting
await guardian.rate_limit('custom_operation', tokens=2)

# Log actions for monitoring
guardian.log_action('custom_action', 'target', success=True)
```

## Testing

### Run Unit Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run all tests
python -m pytest tests/test_session_guardian.py -v

# Run specific test
python -m pytest tests/test_session_guardian.py::TestSessionGuardian::test_auth_key_error_detection -v
```

### Simulate AUTH_KEY_UNREGISTERED

```python
# Test script to simulate auth error
import asyncio
from teleguard.core.session_guardian import init_guardian
from teleguard.utils.guardian_config import DEFAULT_TEST_CONFIG

async def test_auth_error():
    guardian = init_guardian(DEFAULT_TEST_CONFIG)
    
    # Simulate auth error
    error = Exception("AUTH_KEY_UNREGISTERED")
    await guardian.handle_auth_key_error(error)

asyncio.run(test_auth_error())
```

## Admin Alert Messages

### Critical Alert Template

When AUTH_KEY_UNREGISTERED occurs, admins receive:

```
🚨 CRITICAL: Session Revoked

📱 Phone: +1234567890
🕐 Time: 2024-01-15T10:30:00Z
🖥️ Host: server-01
🆔 PID: 12345
❌ Error: AUTH_KEY_UNREGISTERED

🔧 Manual Recovery Required:
1. Stop all bot processes
2. Delete session file: rm *.session
3. Run: python main.py to re-authenticate
4. Check for conflicting processes

📊 Last Actions:
✅ send_message -> @channel
❌ join_channel -> @spam_channel
✅ forward_messages -> @target

⚠️ DO NOT auto-restart until manual recovery is complete.
Check logs: tail -f logs/session_guardian.log
```

### Telegram Support Message Template

```
Subject: Account Session Revocation - Technical Issue

Hello Telegram Support,

My account (+1234567890) is experiencing repeated session revocations with error "AUTH_KEY_UNREGISTERED" (401).

Technical Details:
- Using official Telegram API via Telethon library
- Legitimate bot for personal account management
- No spam or abuse activities
- Sessions revoked every few hours despite normal usage

Request:
Please investigate why my account sessions are being invalidated and whitelist my API usage if possible.

Account: +1234567890
API ID: [your_api_id]
Timestamp: [current_timestamp]

Thank you for your assistance.
```

## Monitoring

### Session Health Check

```bash
# Check session health (if implemented in your bot)
curl -X GET http://localhost:8080/health

# Or via command
python -c "
from teleguard.core.session_guardian import get_guardian
guardian = get_guardian()
if guardian:
    print('Guardian active')
    print(f'Actions logged: {len(guardian.action_history)}')
"
```

### Log Analysis

```bash
# Monitor real-time logs
tail -f logs/session_guardian.log

# Search for auth errors
grep -i "auth_key" logs/session_guardian.log

# Check rate limiting
grep -i "rate limit" logs/session_guardian.log
```

## Best Practices

1. **Single Session Rule**: Never run multiple bots with the same session
2. **Conservative Limits**: Start with low rate limits and increase gradually
3. **Monitor Logs**: Regularly check logs for warnings
4. **Backup Sessions**: Keep encrypted backups of working sessions
5. **Rotate Credentials**: Periodically rotate API credentials
6. **Test Recovery**: Regularly test your recovery procedures

## Troubleshooting

### Common Issues

**Session Lock Errors**
```
RuntimeError: Cannot acquire session lock
```
- Another process is using the session
- Check for running instances: `ps aux | grep python`
- Remove stale lock files: `rm *.lock`

**Rate Limit Too Strict**
```
Rate limiting message, waiting 30.0s
```
- Increase rate limits in environment variables
- Check if operations are batched efficiently

**Alert Not Sent**
```
Failed to send alert: 401 Unauthorized
```
- Verify LOG_BOT_TOKEN is correct
- Check LOG_CHAT_ID permissions
- Ensure bot is added to the alert chat

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Security Considerations

- **Never commit session files** to version control
- **Encrypt session backups** if stored remotely  
- **Use environment variables** for all secrets
- **Monitor for unauthorized access** via logs
- **Rotate credentials regularly** as a security measure
- **Limit bot permissions** to minimum required scope