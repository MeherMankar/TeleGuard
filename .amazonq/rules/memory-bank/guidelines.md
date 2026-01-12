# TeleGuard - Development Guidelines

## Code Quality Standards

### File Structure & Organization
- **Module docstrings**: Every module starts with a triple-quoted docstring describing purpose, authors, and repository
- **UTF-8 encoding declaration**: Files use `# -*- coding: utf-8 -*-` at the top when needed
- **Import organization**: Standard library imports first, then third-party, then local imports with clear separation
- **Relative imports**: Local imports use relative syntax (`from ..core import`, `from ..utils import`)

### Naming Conventions
- **Classes**: PascalCase (e.g., `MenuSystem`, `DeviceSnooper`, `BotManager`, `SessionProtection`)
- **Functions/Methods**: snake_case (e.g., `get_spoofed_device_params`, `start_user_client`, `check_message_safety`)
- **Private methods**: Prefix with single underscore (e.g., `_validate_configuration`, `_initialize_database`, `_is_suspicious_message`)
- **Constants**: UPPER_SNAKE_CASE for module-level constants
- **Variables**: snake_case with descriptive names (e.g., `user_clients`, `pending_actions`, `session_health`)

### Documentation Standards
- **Docstrings**: Triple-quoted strings for all public classes and methods
- **Inline comments**: Used sparingly for complex logic, not for obvious code
- **Type hints**: Partial usage with `typing` module (Dict, Optional, List, Any, Set, Callable)
- **Parameter documentation**: Docstrings include Args, Returns, and Raises sections where applicable

### Code Formatting
- **Line length**: Generally kept under 88-100 characters (Black formatter standard)
- **Indentation**: 4 spaces (no tabs)
- **String quotes**: Double quotes preferred for strings, single quotes for dict keys in some cases
- **F-strings**: Used extensively for string formatting (e.g., `f"Account {account_name} removed"`)
- **Trailing commas**: Used in multi-line collections for cleaner diffs

## Architectural Patterns

### Component-Based Architecture
- **ComponentManager pattern**: Centralized component lifecycle management with error handling
- **Dependency injection**: Components receive dependencies through constructors
- **Lazy initialization**: Components initialized on-demand with `initialize_component` method
- **Cleanup hooks**: Components implement `cleanup()`, `stop()`, or similar methods for resource cleanup

### Manager Pattern
- **BotManager**: Central orchestrator for bot lifecycle and component coordination
- **OTPManager**: Manages OTP destruction handlers across multiple accounts
- **ClientManager**: Handles Telethon client lifecycle and connection pooling
- **SessionProtection**: Global singleton for session safety checks

### Async/Await Patterns
- **Async-first design**: All I/O operations use async/await
- **Timeout handling**: Critical operations wrapped with `asyncio.wait_for(operation, timeout=X)`
- **Task creation**: Background tasks created with `asyncio.create_task()`
- **Concurrent operations**: Use `asyncio.gather()` for parallel execution
- **Error handling**: Try-except blocks around async operations with specific exception handling

### Database Patterns
- **MongoDB integration**: Using motor (async MongoDB driver) with `mongodb.db` global instance
- **Upsert operations**: `update_one(..., upsert=True)` for create-or-update semantics
- **ObjectId handling**: Import `from bson import ObjectId` for MongoDB document IDs
- **Cursor iteration**: `.to_list(length=None)` to convert cursors to lists
- **Atomic updates**: Use `$set`, `$unset`, `$inc`, `$addToSet` operators

## Common Implementation Patterns

### Error Handling Strategy
```python
try:
    # Main operation
    await some_operation()
except asyncio.TimeoutError:
    logger.warning("Operation timed out")
    # Handle timeout specifically
except Exception as e:
    logger.error(f"Operation failed: {e}")
    # Generic error handling
    raise TeleGuardError("Operation failed", details={"error": str(e)})
```

### Logging Pattern
- **Structured logging**: Use `logger.info()`, `logger.warning()`, `logger.error()`, `logger.debug()`
- **Context in logs**: Include relevant identifiers (user_id, account_name, task_id)
- **Error details**: Log full exception details with `exc_info=True` for debugging
- **Safe logging**: Remove emojis/Unicode for Windows console compatibility

### Session Management Pattern
```python
# Register session for protection
session_id = f"{user_id}_{account_name}"
session_protection.register_session(session_id, account_name)

# Store client reference
if user_id not in self.user_clients:
    self.user_clients[user_id] = {}
self.user_clients[user_id][account_name] = client
```

### Telethon Client Creation
```python
from .device_snooper import DeviceSnooper

device_params = DeviceSnooper.get_spoofed_device_params()
client = TelegramClient(
    StringSession(session_string),
    config.telegram.api_id,
    config.telegram.api_hash,
    connection_retries=2,
    retry_delay=2,
    timeout=10,
    **device_params
)
```

### Rate Limiting Pattern
```python
# Check safety before action
if not await session_protection.check_message_safety(session_id, message_content):
    return False

# Perform action
await client.send_message(target, message)

# Record action
await session_protection.record_message_sent(session_id)
```

### Menu System Pattern (Telethon Buttons)
```python
from telethon import Button

buttons = [
    [Button.inline("Option 1", "callback:action1")],
    [Button.inline("Option 2", "callback:action2")],
    [Button.inline("🔙 Back", "menu:main")]
]
await bot.send_message(user_id, text, buttons=buttons)
```

### Callback Handling Pattern
```python
@bot.on(events.CallbackQuery())
async def callback_handler(event):
    user_id = event.sender_id
    data = event.data.decode("utf-8")
    
    parts = data.split(":")
    action = parts[0]
    
    if action == "menu":
        await handle_menu(event, user_id, parts[1])
    elif action == "otp":
        await handle_otp(event, user_id, parts[1:])
```

### Database Query Patterns
```python
# Find one document
account = await mongodb.db.accounts.find_one(
    {"user_id": user_id, "name": account_name}
)

# Find multiple with filter
accounts = await mongodb.db.accounts.find(
    {"user_id": user_id, "is_active": True}
).to_list(length=None)

# Update with upsert
await mongodb.db.accounts.update_one(
    {"user_id": user_id, "name": account_name},
    {"$set": {"is_active": True}},
    upsert=True
)

# Delete documents
await mongodb.db.accounts.delete_many({"needs_reauth": True})
```

### Context Manager Pattern
```python
async def __aenter__(self):
    await self.start_bot()
    return self

async def __aexit__(self, exc_type, exc_val, exc_tb):
    await self.cleanup()

# Usage
async with BotManager() as bot:
    await bot.run()
```

## Security Practices

### Session String Handling
- **Double encryption**: Session strings encrypted with Fernet before storage
- **HTML entity decoding**: `html.unescape()` used to clean session strings
- **Validation**: Pre-validate sessions before creating clients
- **Conflict detection**: Handle AUTH_KEY_UNREGISTERED and AUTH_KEY_DUPLICATED errors

### Password Management
- **Encrypted storage**: 2FA passwords stored with AES-256 encryption
- **Secure removal**: Passwords removed from database when accounts are deleted
- **No plaintext**: Never log or display passwords in plaintext

### Rate Limiting
- **Message limits**: 50/20/10 messages per hour (normal/high/maximum protection)
- **Join limits**: 10/5/2 joins per day (normal/high/maximum protection)
- **Minimum delays**: 2/5/10 seconds between messages, 5/15/30 minutes between joins
- **Human-like behavior**: Random delays added after actions

### Input Validation
- **Phone number format**: Validated with country code
- **Session string length**: Minimum 50 characters required
- **Suspicious content**: Check for spam patterns in messages
- **User authorization**: Verify user permissions before operations

## Testing & Debugging

### Logging Levels
- **DEBUG**: Detailed information for diagnosing problems
- **INFO**: Confirmation that things are working as expected
- **WARNING**: Indication that something unexpected happened
- **ERROR**: Serious problem that prevented a function from executing

### Error Recovery
- **Retry mechanisms**: TaskQueue implements automatic retry with exponential backoff
- **Graceful degradation**: Continue operation even if non-critical components fail
- **User notifications**: Inform users about errors with actionable messages
- **Cleanup on failure**: Always cleanup resources in finally blocks

### Performance Optimization
- **Timeout enforcement**: All network operations have timeouts (2-15 seconds)
- **Concurrent loading**: Load multiple accounts in parallel with limits
- **Lazy loading**: Components initialized only when needed
- **Connection pooling**: Reuse Telethon clients instead of creating new ones

## Code Examples

### Adding a New Handler
```python
from ..handlers.base_handler import BaseHandler

class MyHandler(BaseHandler):
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
    
    def register_handlers(self):
        @self.bot.on(events.NewMessage(pattern="/mycommand"))
        async def handle_command(event):
            user_id = event.sender_id
            await event.reply("Command executed!")
    
    async def cleanup(self):
        # Cleanup resources
        pass
```

### Creating a Background Worker
```python
class MyWorker:
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.running = False
        self.task = None
    
    async def start(self):
        if self.running:
            return
        self.running = True
        self.task = asyncio.create_task(self._worker())
    
    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
    
    async def _worker(self):
        while self.running:
            try:
                # Do work
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker error: {e}")
```

### Database Operations
```python
# Create/Update account
await mongodb.db.accounts.update_one(
    {"user_id": user_id, "phone": phone},
    {
        "$set": {
            "name": account_name,
            "session_string": encrypted_session,
            "is_active": True,
            "added_at": datetime.now(timezone.utc)
        }
    },
    upsert=True
)

# Query with projection
account = await mongodb.db.accounts.find_one(
    {"_id": ObjectId(account_id)},
    {"session_string": 0}  # Exclude session_string
)

# Aggregation pipeline
stats = await mongodb.db.accounts.aggregate([
    {"$match": {"user_id": user_id}},
    {"$group": {"_id": "$is_active", "count": {"$sum": 1}}}
]).to_list(length=None)
```

## Best Practices Summary

1. **Always use async/await** for I/O operations
2. **Implement proper error handling** with specific exception types
3. **Add timeouts** to all network operations
4. **Log important events** with appropriate levels
5. **Clean up resources** in finally blocks or cleanup methods
6. **Validate user input** before processing
7. **Use type hints** for better code documentation
8. **Follow naming conventions** consistently
9. **Document complex logic** with comments
10. **Test error paths** not just happy paths
11. **Handle session conflicts** gracefully
12. **Protect against rate limits** with built-in delays
13. **Encrypt sensitive data** before storage
14. **Use context managers** for resource management
15. **Implement graceful shutdown** for all components
