# TeleGuard Backup System

Automated backup architecture with Redis caching, MongoDB primary storage, and multiple backup destinations.

## Architecture

- **Primary Database**: MongoDB (async with Motor)
- **Cache Layer**: Redis (for ephemeral data and fallback)
- **Backup Destinations**:
  - Telegram Channel (hourly uploads, 8-hour cleanup)
  - GitHub Repository (hourly commits, 8-hour history cleanup)
  - Public Encrypted Snapshots (AES-GCM encrypted for transparency)

## Environment Variables

### Required
```bash
# Database
MONGODB_URI=mongodb://localhost:27017/teleguard
REDIS_URL=redis://localhost:6379

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHANNEL_ID=-1001234567890

# GitHub
GITHUB_REPO=https://github.com/username/repo.git
GITHUB_TOKEN=ghp_your_token_here

# Encryption (32 bytes base64)
ENCRYPTION_KEY=base64_encoded_32_byte_key
```

### Optional
```bash
# Backup settings
GITHUB_BACKUP_BRANCH=backups
SNAPSHOT_DIR=/tmp/teleguard_snapshots
```

## Backup Schedule

### Hourly (every hour at :00)
1. Create JSON snapshot of all MongoDB collections
2. Push plain snapshot to GitHub private branch
3. Encrypt snapshot with AES-GCM
4. Push encrypted snapshot to public GitHub path
5. Upload snapshot to Telegram backup channel
6. Store tracking metadata in MongoDB

### Every 8 Hours (at :05)
1. Create orphan Git branch with only latest snapshot
2. Force push to remove commit history
3. Delete Telegram messages older than 8 hours

## Security

### Data Encryption
- **AES-GCM**: Symmetric encryption for public snapshots
- **Key Management**: 32-byte key stored in environment variables
- **Nonce**: Random 12-byte nonce for each encryption

### Access Control
- **Private GitHub**: Full snapshots in private repository
- **Public Encrypted**: Encrypted snapshots for transparency
- **Telegram Channel**: Bot admin access required

## Operational Considerations

### GitHub Rate Limits
- API calls are minimal (only for authentication)
- Uses Git CLI for actual operations
- Force push happens only every 8 hours

### Telegram Limits
- File uploads limited to 50MB per file
- Message deletion requires admin privileges
- Bot must be admin in backup channel

### Storage Requirements
- **MongoDB**: Primary data storage
- **Redis**: Ephemeral cache (optional)
- **Local Temp**: Snapshot files (cleaned automatically)
- **GitHub**: Repository storage (history cleaned every 8 hours)

### Monitoring
- All operations logged with structured logging
- Failed operations continue with warnings
- Health status available through existing health check system

## Usage

The backup system starts automatically with the bot:

```python
# Automatic startup in bot_manager.py
from teleguard.sync.scheduler import start_scheduler
start_scheduler(bot_client)
```

### Manual Operations
```python
from teleguard.sync.backups import create_snapshot, encrypt_snapshot

# Create snapshot
snapshot_path = await create_snapshot()

# Encrypt for public access
with open(snapshot_path, 'rb') as f:
    encrypted = encrypt_snapshot(f.read())
```

## Public Snapshot Verification

Users can verify encrypted snapshots exist but cannot read contents without the private key:

```python
from teleguard.sync.crypto import decrypt_bytes

# Only works with the private ENCRYPTION_KEY
decrypted = decrypt_bytes(encrypted_snapshot_bytes)
```

## Troubleshooting

### Common Issues

1. **MongoDB Connection Failed**
   - Check MONGODB_URI environment variable
   - Verify MongoDB server is running
   - Check network connectivity

2. **Redis Connection Failed**
   - System continues without Redis (fallback mode)
   - Check REDIS_URL environment variable
   - Verify Redis server is running

3. **GitHub Push Failed**
   - Check GITHUB_TOKEN permissions
   - Verify repository exists and is accessible
   - Check network connectivity

4. **Telegram Upload Failed**
   - Verify bot is admin in backup channel
   - Check TELEGRAM_CHANNEL_ID format (negative for channels)
   - Ensure file size is under 50MB

### Logs
All backup operations are logged with INFO level:
```
2024-01-01 12:00:00 - teleguard.sync.scheduler - INFO - Starting hourly backup job
2024-01-01 12:00:05 - teleguard.sync.backups - INFO - Created snapshot: teleguard_snapshot_20240101_120005.json (1234 records)
2024-01-01 12:00:10 - teleguard.sync.github_sync - INFO - Pushed hourly snapshot to GitHub: teleguard_snapshot_20240101_120005.json
```

## Testing

Run individual components:

```python
# Test snapshot creation
from teleguard.sync.backups import create_snapshot
snapshot_path = await create_snapshot()

# Test encryption
from teleguard.sync.crypto import encrypt_bytes, decrypt_bytes
encrypted = encrypt_bytes(b"test data")
decrypted = decrypt_bytes(encrypted)

# Test GitHub operations (requires valid repo)
from teleguard.sync.github_sync import push_hourly_snapshot
push_hourly_snapshot("/path/to/snapshot.json")
```