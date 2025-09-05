# Session Backup System Implementation

## Overview

This implementation provides a robust session persistence pipeline that:
- Stores encrypted sessions in MongoDB as live/temporary storage
- Pushes encrypted session files to a dedicated GitHub repository every 30 minutes
- Compacts GitHub repository history every 8 hours to maintain clean history
- Ensures encryption, atomicity, retries, signed manifests, and audit logging

## Architecture

### Components

1. **crypto_utils.py** - Encryption utilities using Fernet
2. **mongo_store.py** - MongoDB integration for temporary storage
3. **session_backup.py** - Main backup manager with GitHub integration
4. **session_scheduler.py** - Automated job scheduling
5. **Integration in bot.py** - Session backup during account creation

### Data Flow

```
Account Creation → Session String → Encrypt → MongoDB (temp) → GitHub (30min) → History Compact (8h)
```

## MongoDB Collections

### sessions_temp
```json
{
  "_id": ObjectId,
  "account_id": "phone_number_or_id",
  "enc_blob": Binary,              // Encrypted session bytes
  "sha256": "hexstring",           // SHA256 of encrypted bytes
  "created_at": ISODate,
  "last_updated": ISODate,
  "persisted_to_github": false,
  "github_commit": null,           // Commit SHA once pushed
  "github_path": null,             // Path in GitHub repo
  "manifest_version": null         // Manifest version that included this
}
```

### session_audit
```json
{
  "_id": ObjectId,
  "account_id": "id_or_null",
  "action": "push_to_github|compact_history",
  "details": {...},               // Response, commit, errors
  "ts": ISODate,
  "initiator": "system|scheduler"
}
```

## GitHub Repository Structure

```
sessions-repo/
├── sessions/
│   ├── +1234567890.enc         // Encrypted session files
│   └── +9876543210.enc
├── manifests/
│   ├── sessions.json           // Signed manifest
│   └── sessions.json.sig       // GPG signature
└── README.md                   // Verification instructions
```

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `MONGO_URI` | MongoDB connection string | Yes | `mongodb://localhost:27017/` |
| `GITHUB_REPO` | Git repository URL | Yes | - |
| `GIT_WORKDIR` | Local git workspace | No | `/tmp/sessions_repo` |
| `GPG_KEY_ID` | GPG key for signing | No | - |
| `SESSION_BACKUP_ENABLED` | Enable/disable backups | No | `false` |
| `FERNET_KEY` | Encryption key (base64) | Yes | - |

## Security Features

### Encryption
- All sessions encrypted with Fernet before storage
- SHA256 hashing for integrity verification
- Key management via environment variables (KMS recommended)

### Atomicity
- MongoDB sessions not deleted until GitHub push confirmed
- History compaction creates backup branches before rewriting
- Rollback procedures documented

### Audit Trail
- All operations logged in `session_audit` collection
- GPG-signed manifests for verification
- Complete audit history maintained

## Scheduled Jobs

### Session Push (Every 30 minutes)
1. Query unpersisted sessions from MongoDB
2. Clone/update local GitHub repository
3. Write encrypted session files
4. Generate and sign manifest
5. Commit and push to GitHub
6. Mark sessions as persisted in MongoDB
7. Log audit events

### History Compaction (Every 8 hours)
1. Create timestamped backup branch
2. Create orphan branch with current files only
3. Force-push to replace main branch
4. Log compaction event
5. Keep backup branch for 30 days

### MongoDB Cleanup (Daily)
- Remove old persisted sessions (7+ days)
- Maintain audit log retention

## Commands

### User Commands
- `/verify_session <account_id>` - Verify session backup status and provide verification instructions

### Admin Commands
- `/backup_now` - Manually trigger session backup
- `/compact_now` - Manually trigger history compaction

## Manual Verification

Users can verify their session backups:

1. **Download files:**
   ```bash
   curl -O https://raw.githubusercontent.com/user/sessions-repo/main/sessions/ACCOUNT_ID.enc
   curl -O https://raw.githubusercontent.com/user/sessions-repo/main/manifests/sessions.json
   curl -O https://raw.githubusercontent.com/user/sessions-repo/main/manifests/sessions.json.sig
   ```

2. **Verify signature:**
   ```bash
   gpg --verify sessions.json.sig sessions.json
   ```

3. **Check SHA256:**
   ```bash
   sha256sum sessions/ACCOUNT_ID.enc
   # Compare with hash in sessions.json
   ```

## Error Handling

### Push Failures
- Exponential backoff retry logic
- Admin alerts on repeated failures
- Sessions remain in MongoDB until confirmed

### Rate Limiting
- GitHub API rate limit detection
- Automatic backoff and retry
- Job rescheduling on limits

### Compaction Failures
- Backup branch creation before any destructive operations
- Rollback procedures documented
- Immediate admin alerts

## Rollback Procedures

### Restore from Backup Branch
```bash
git push origin backup_history_YYYYMMDDHHMMSS:main
```

### Recover Deleted Session
1. Check `backup_history_*` branches
2. Extract session from backup
3. Re-import to MongoDB if needed

## Testing

Run the test suite:
```bash
python -m pytest test_session_backup.py -v
```

Tests cover:
- Encryption/decryption roundtrips
- MongoDB operations
- Manifest generation
- Error conditions
- Integration scenarios

## Migration from Existing System

1. **Backup current data:**
   ```bash
   git checkout -b backup/pre-session-github-$(date +%Y%m%d)
   ```

2. **Install dependencies:**
   ```bash
   pip install pymongo APScheduler python-gnupg
   ```

3. **Configure environment:**
   - Set MongoDB URI
   - Set GitHub repository
   - Configure GPG key
   - Enable session backup

4. **Initialize MongoDB:**
   - Indexes created automatically on first run
   - Existing sessions will be backed up on next update

5. **Verify operation:**
   - Check logs for successful initialization
   - Test with `/verify_session` command
   - Monitor scheduled job execution

## Monitoring

### Log Messages
- Session storage: `Session backed up to MongoDB for {account_id}`
- Push success: `Successfully pushed {count} sessions`
- Compaction: `History compacted successfully, backup: {branch}`

### Audit Events
- All operations logged with timestamps
- Query audit collection for statistics
- Monitor for failure patterns

## Production Considerations

1. **Use KMS for encryption keys** instead of environment variables
2. **Set up MongoDB replica set** for high availability
3. **Configure GitHub repository access** with deploy keys
4. **Set up monitoring alerts** for backup failures
5. **Implement log rotation** for audit collections
6. **Regular backup verification** procedures
7. **Document recovery procedures** for team

## Compliance

- **GDPR**: User consent required before GitHub upload
- **Data retention**: Configurable cleanup policies
- **Audit requirements**: Complete operation logging
- **Security**: End-to-end encryption with key management