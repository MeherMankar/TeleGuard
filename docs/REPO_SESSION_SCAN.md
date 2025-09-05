# Repository Session Handling Scan

## Session Storage Locations

### 1. Models (models.py)
- **Account.session_string**: Encrypted session string storage
- **Account.encrypt_session()**: Encrypts session before storing
- **Account.decrypt_session()**: Decrypts stored session
- **Uses Fernet encryption from config.py**

### 2. Bot Main (bot.py)
- **Line ~30**: `self.user_clients: Dict[int, Dict[str, TelegramClient]]` - In-memory client storage
- **Line ~70**: `load_existing_sessions()` - Loads sessions from database on startup
- **Line ~90**: `start_user_client()` - Creates TelegramClient from session string
- **Line ~200**: Session creation during account addition (auth flow)

### 3. Authentication (auth_handler.py)
- Session string generation during authentication
- OTP destroyer session handling

### 4. Database (database.py)
- SQLite database with encrypted session storage
- No MongoDB integration currently

## Current Session Flow
1. User adds account → Authentication → Session string generated
2. Session encrypted with Fernet → Stored in SQLite Account.session_string
3. On bot startup → Sessions loaded → TelegramClient instances created
4. Sessions kept in memory in `user_clients` dictionary

## MongoDB Integration Points Needed
- Replace SQLite with MongoDB for live session storage
- Add session backup collections
- Add audit logging collections

## GitHub Integration Points Needed
- Session export to encrypted files
- Manifest generation and signing
- Batch push jobs
- History compaction jobs

## Security Considerations
- Current: Fernet encryption with local key file
- Needed: KMS integration for key management
- Needed: GPG signing for manifests
- Needed: User consent for GitHub uploads

## TODO Markers Added
- All session handling code marked with `# TODO: REVIEW - session export / session-file handling`