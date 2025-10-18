# TeleGuard Database Architecture

## Overview

TeleGuard now uses a dual-database architecture optimized for different data types:

- **Redis**: Ephemeral cache for temporary data (rate limits, session tokens, OTP codes)
- **MongoDB**: Durable storage for persistent data (users, accounts, settings, audit logs)

## Architecture

```text
┌─────────────────┐    ┌─────────────────┐
│   Application   │────│ Database Manager│
└─────────────────┘    └─────────────────┘
                                │
                    ┌───────────┼───────────┐
                    │                       │
            ┌───────▼────────┐    ┌────────▼────────┐
            │ Redis Cache    │    │ MongoDB Storage │
            │ (Ephemeral)    │    │ (Durable)       │
            └────────────────┘    └─────────────────┘
```

## Data Distribution

### Redis Cache (Ephemeral)
- **Rate Limits**: Sliding window counters with automatic expiry
- **Session Tokens**: Temporary authentication tokens (1 hour TTL)
- **OTP Codes**: One-time passwords (5 minutes TTL)
- **Temporary Cache**: Short-lived application data (30 minutes TTL)

### MongoDB Storage (Durable)
- **Users**: User profiles and settings
- **Accounts**: Telegram account information
- **Sessions**: Encrypted session strings
- **User Settings**: Application preferences
- **Audit Logs**: Security and activity logging
- **Backups**: Data snapshots for recovery

## Configuration

### Environment Variables

```bash
# MongoDB (Required)
MONGO_URI=mongodb://localhost:27017/teleguard
MONGODB_URI=mongodb://localhost:27017/teleguard

# Redis (Required)
REDIS_URL=redis://localhost:6379/0

# Redis Settings
REDIS_MAX_CONNECTIONS=20
REDIS_RETRY_ON_TIMEOUT=true
REDIS_HEALTH_CHECK_INTERVAL=30

# Cache TTL Settings (seconds)
CACHE_TTL_SESSION_TOKEN=3600    # 1 hour
CACHE_TTL_OTP_CODE=300          # 5 minutes
CACHE_TTL_TEMP_DATA=1800        # 30 minutes
CACHE_TTL_RATE_LIMIT=3600       # 1 hour
```

## Usage Examples

### Basic Usage

```python
from teleguard.core.database_manager import db_manager, init_database_manager

# Initialize
await init_database_manager()

# Rate limiting (Redis)
await db_manager.check_rate_limit(user_id, "login", limit=5, window=60)

# Session tokens (Redis)
await db_manager.store_session_token(user_id, "token", ttl=3600)
token = await db_manager.get_session_token(user_id)

# User management (MongoDB)
await db_manager.create_user(user_id, username="test")
user = await db_manager.get_user(user_id)

# Settings (MongoDB)
await db_manager.store_user_settings(user_id, {"theme": "dark"})
settings = await db_manager.get_user_settings(user_id)
```

### Rate Limiting

```python
# Check rate limit with automatic Redis sliding window
try:
    await db_manager.check_rate_limit(
        user_id=123456789,
        endpoint="api_call",
        limit=30,
        window=60
    )
    # Request allowed
except RateLimitError as e:
    # Rate limit exceeded
    remaining = await db_manager.get_rate_limit_remaining(
        user_id, "api_call", 30, 60
    )
```

### Session Management

```python
# Store temporary session token (Redis)
await db_manager.store_session_token(user_id, "temp_token", ttl=3600)

# Store permanent session data (MongoDB)
session_data = {"session_string": "encrypted_data"}
await db_manager.store_session(user_id, account_id, session_data)
```

## Performance Optimizations

### MongoDB Indexes
- `users.telegram_id` (unique)
- `accounts.user_id + phone` (unique)
- `sessions.user_id + account_id`
- `audit_logs.user_id + timestamp`

### Redis Optimizations
- Connection pooling (max 20 connections)
- Automatic retry on timeout
- Health check monitoring (30s interval)
- Sliding window rate limiting

### Connection Settings

#### MongoDB
- Write concern: `majority` (durability)
- Read preference: `primary`
- Connection pooling: 5-20 connections
- Retry writes enabled

#### Redis
- Decode responses: UTF-8
- Socket timeout: 5 seconds
- Retry on timeout enabled
- Health check interval: 30 seconds

## Fallback Behavior

### Redis Unavailable
- Rate limiting falls back to memory-based tracking
- Session tokens return `None` (graceful degradation)
- Cache operations silently fail
- Application continues functioning

### MongoDB Unavailable
- Application startup fails (critical data required)
- Existing Redis cache continues working
- Health checks report degraded status

## Monitoring

### Health Checks

```python
health = await db_manager.health_check()
# Returns:
# {
#     "redis": True/False,
#     "mongodb": True/False,
#     "redis_ping": True/False,
#     "mongodb_ping": True/False,
#     "initialized": True/False
# }
```

### Maintenance

```python
# Cleanup old audit logs (MongoDB)
await db_manager.cleanup_old_data()

# Redis data expires automatically via TTL
```

## Migration from Legacy System

The new system maintains backward compatibility:

```python
# Legacy imports still work
from teleguard.core.database import init_db, mongodb

# New unified interface
from teleguard.core.database_manager import db_manager, init_database_manager
```

## Security Features

### Data Encryption
- MongoDB: Field-level encryption for sensitive data
- Redis: Temporary data with automatic expiry
- Session strings: Double encryption (Fernet + MongoDB encryption)

### Access Control
- MongoDB: Authentication and authorization
- Redis: Connection-level security
- Rate limiting: Prevents abuse and DoS attacks

## Deployment Considerations

### Docker Compose

```yaml
version: '3.8'
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
    
  mongodb:
    image: mongo:7
    ports:
      - "27017:27017"
    environment:
      MONGO_INITDB_DATABASE: teleguard
    volumes:
      - mongodb_data:/data/db

  teleguard:
    build: .
    environment:
      - REDIS_URL=redis://redis:6379/0
      - MONGO_URI=mongodb://mongodb:27017/teleguard
    depends_on:
      - redis
      - mongodb

volumes:
  mongodb_data:
```

### Cloud Deployment
- **Redis**: Use managed Redis (AWS ElastiCache, Google Memorystore)
- **MongoDB**: Use MongoDB Atlas or managed MongoDB service
- **Scaling**: Both databases support horizontal scaling

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   - Check REDIS_URL environment variable
   - Verify Redis server is running
   - Application continues with fallback behavior

2. **MongoDB Connection Failed**
   - Check MONGO_URI environment variable
   - Verify MongoDB server is running
   - Application startup will fail (by design)

3. **Rate Limiting Not Working**
   - Check Redis connection status
   - Verify rate limit parameters
   - Falls back to memory-based limiting

### Debug Commands

```python
# Check database health
health = await db_manager.health_check()
print(health)

# Test Redis connection
await db_manager.redis.client.ping()

# Test MongoDB connection
await db_manager.mongo.client.admin.command("ping")
```