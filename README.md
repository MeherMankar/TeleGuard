# 🤖 TeleGuard - Telegram Account Manager

A professional Telegram bot for managing multiple user accounts with advanced OTP destroyer protection against unauthorized access attempts.

**Developed by:**
- [@Meher_Mankar](https://t.me/Meher_Mankar)
- [@Gutkesh](https://t.me/Gutkesh)

**Support:** [Contact Support](https://t.me/ContactXYZrobot)
**Documentation:** [📚 Wiki](https://github.com/MeherMankar/TeleGuard/wiki)
**Repository:** [GitHub](https://github.com/MeherMankar/TeleGuard)

## ⚡ Quick Start

### 🚀 One-Click Deploy

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/MeherMankar/TeleGuard)

### 🖥️ Local Installation

1. **Clone Repository**
   ```bash
   git clone https://github.com/MeherMankar/TeleGuard.git
   cd TeleGuard
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**
   ```bash
   cp config/.env.example config/.env
   # Edit config/.env with your credentials
   ```

4. **Run Bot**
   ```bash
   python main.py
   ```

### ☁️ Cloud Deployment

- **Heroku**: Use one-click deploy button above or `./deploy/heroku.sh`
- **Koyeb**: Run `./deploy/koyeb.sh` for free tier deployment
- **Docker**: `docker-compose up -d`

## 🔧 Configuration

### Required Environment Variables
```bash
# Telegram API (get from https://my.telegram.org)
API_ID=your_api_id_here
API_HASH=your_api_hash_here

# Bot Token (get from @BotFather)
BOT_TOKEN=your_bot_token_here

# Admin Access
ADMIN_IDS=123456789,987654321
```

### Optional Settings
```bash
# Database (auto-configured for cloud platforms)
DATABASE_URL=sqlite+aiosqlite:///bot_data.db

# Security & Limits
MAX_ACCOUNTS=10
RATE_LIMIT_ENABLED=true

# Session Backup (production)
SESSION_BACKUP_ENABLED=true
GITHUB_REPO=git@github.com:username/sessions-backup.git
GPG_KEY_ID=your_gpg_key_id
FERNET_KEY=your_base64_fernet_key
TELEGRAM_BACKUP_CHANNEL=-1001234567890
```

## 🚀 Features

| Feature | Description | Status |
|---------|-------------|--------|
| 🛡️ **OTP Destroyer** | Real-time protection against unauthorized login attempts | ✅ Active |
| 👤 **Account Management** | Manage up to 10 Telegram accounts per user | ✅ Active |
| 🔐 **Security Features** | 2FA management, session backup, audit logging | ✅ Active |
| ⚡ **Automation Engine** | Online maker, scheduled tasks, auto-reply | ✅ Active |
| 📱 **Profile Manager** | Update names, photos, bios, usernames | ✅ Active |
| 🔑 **2FA Management** | Set, change, remove two-factor authentication | ✅ Active |
| 🎭 **Activity Simulator** | Human-like activity to avoid detection | ✅ Active |
| 💬 **Unified Messaging** | Smart message routing, auto-reply, templates | ✅ Active |
| 📨 **DM Reply Manager** | Centralized DM management with topic creation | ✅ Active |
| 📢 **Channel Manager** | Join, leave, create, manage channels | ✅ Active |
| 👥 **Contact Export** | Export Telegram contacts to CSV format | ✅ Active |
| 🤖 **Bot Message Handling** | Direct bot notifications without topics | ✅ Active |
| 💾 **Expanded Backups** | User settings, IDs, and sessions to Telegram | ✅ Active |
| ☁️ **Cloud Ready** | Deploy on Heroku, Koyeb, Docker | ✅ Active |

### 🛡️ OTP Destroyer Protection
- **Real-time Protection**: Automatically invalidates unauthorized login codes
- **Telegram API Integration**: Uses official `account.invalidateSignInCodes`
- **Instant Alerts**: Notifies users when attacks are blocked
- **Zero False Positives**: Only triggers on actual login attempts

### 👤 Account Management
- **Multi-Account Support**: Manage up to 10 accounts per user
- **Secure Storage**: Military-grade Fernet encryption for sessions
- **Profile Management**: Update names, usernames, bios, and photos
- **Session Control**: View and terminate active sessions

### 🔐 Security Features
- **2FA Management**: Set, change, and remove two-factor authentication
- **Session Backup**: Automated GitHub backup with GPG signing
- **Audit Logging**: Complete activity tracking
- **Rate Limiting**: Protection against abuse

### ⚡ Automation
- **Online Maker**: Keep accounts online automatically
- **Scheduled Tasks**: Automated actions and workflows
- **Smart Auto-Reply**: Keyword-based and time-aware responses
- **DM Reply Management**: Centralized inbox with forum topics
- **Contact Export**: Export contacts to CSV with comprehensive data
- **Bulk Operations**: Mass account management

## 📱 Usage

### Getting Started
1. Send `/start` to your bot
2. Use the persistent menu buttons to navigate
3. Add accounts via "📱 Account Settings"
4. Enable OTP protection in "🛡️ OTP Manager"

### Main Menu
```
📱 Account Settings    🛡️ OTP Manager
💬 Messaging          📢 Channels
❓ Help               🆘 Support
⚙️ Developer (Admin Only)
```

### Core Features
- **📱 Account Settings**: Add, remove, manage accounts
- **🛡️ OTP Manager**: Configure OTP destroyer protection
- **💬 Unified Messaging**: Smart routing, auto-reply, templates
- **📨 DM Reply**: Forum-based centralized DM management
- **📢 Channels**: Join, leave, create, manage channels
- **👥 Contacts**: Export contacts to CSV format
- **🎭 Activity Simulator**: Human-like activity simulation
- **🔐 Sessions**: View and terminate active sessions
- **🔑 2FA**: Set, change, remove two-factor authentication

### Account Management
- **Add Account**: Phone number → OTP → 2FA (if enabled)
- **Remove Account**: Logout and delete all data
- **Profile Updates**: Names, usernames, bios, photos
- **Session Control**: View and terminate sessions

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Telegram Bot  │────│  Account Manager│────│   User Clients  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐              │
         └──────────────│  Menu System    │──────────────┘
                        └─────────────────┘
                                 │
    ┌────────────────────────────┼────────────────────────────┐
    │                            │                            │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Unified Messaging│    │   MongoDB DB    │    │  OTP Manager   │
│ • Auto-Reply     │    │ • Accounts      │    │ • Destroyer     │
│ • Topic Routing  │    │ • Settings      │    │ • Notifications │
│ • Bot Filtering  │    │ • Mappings      │    │ • Prevention    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🔒 Security

### Data Protection
- **Full Data Encryption**: All user data encrypted at rest with Fernet
- **Encrypted Sessions**: Session strings double-encrypted for security
- **Secure Database**: MongoDB with comprehensive field-level encryption
- **Secure Logging**: No sensitive information in logs
- **Password Protection**: 2FA passwords hashed with SHA-256

### Session Backup Security
- **Triple Encryption**: Fernet + GPG + GitHub private repository
- **Telegram Backups**: Encrypted user settings and session files
- **Database Encryption**: All sensitive fields encrypted at storage level
- **Integrity Verification**: GPG signatures for all backups
- **Automated Rotation**: History compaction every 8 hours
- **Access Control**: Private repository with SSH key authentication

## 📊 Monitoring

### Log Levels
- **INFO**: Normal operations and user actions
- **WARNING**: Rate limits and recoverable issues
- **ERROR**: Authentication failures and system errors

### Health Checks
- Account connectivity status
- Session backup verification
- OTP destroyer statistics
- Automation engine performance

## 🛠️ Development

### Project Structure
```
TeleGuard/
├── teleguard/             # Main package
│   ├── core/             # Core functionality
│   ├── handlers/         # Event handlers
│   ├── utils/            # Utilities
│   └── workers/          # Background workers
├── config/               # Configuration
├── deploy/               # Deployment scripts
├── tests/                # Test suite
└── main.py              # Entry point
```

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/

# Run locally
python main.py
```

### Deployment
```bash
# Heroku
./deploy/heroku.sh

# Koyeb
./deploy/koyeb.sh

# Docker
docker-compose up -d
```

## 📋 Requirements

### Minimum Requirements
- Python 3.11+
- Telegram API credentials (API_ID, API_HASH)
- Bot token from @BotFather

### Optional
- MongoDB (primary database - auto-configured)
- PostgreSQL (legacy support)
- Git + GPG (for session backup)
- Docker (for containerized deployment)

## ⚠️ Important Notes

### Legal Compliance
- Use only for legitimate account management
- Comply with Telegram's Terms of Service
- Respect local laws and regulations

### Rate Limits
- Telegram enforces API rate limits
- Bot includes automatic rate limit handling
- Use different phone numbers if rate limited

### Security Best Practices
- Keep `.env` file secure and private
- Use strong passwords for 2FA
- Regularly update dependencies
- Monitor logs for suspicious activity

## 🆘 Troubleshooting

> **📚 Complete troubleshooting guide: [Troubleshooting](https://github.com/MeherMankar/TeleGuard/wiki/Troubleshooting)**

### Quick Fixes

| Issue | Solution | Guide |
|-------|----------|-------|
| **Rate Limiting** | Wait for cooldown or use different number | [Rate Limits](https://github.com/MeherMankar/TeleGuard/wiki/Troubleshooting#rate-limiting) |
| **2FA Required** | Provide 2FA password when prompted | [2FA Issues](https://github.com/MeherMankar/TeleGuard/wiki/Troubleshooting#2fa-issues) |
| **Session Errors** | Re-add affected accounts | [Session Problems](https://github.com/MeherMankar/TeleGuard/wiki/Troubleshooting#session-issues) |
| **Database Connection** | Check MongoDB configuration | [Database Issues](https://github.com/MeherMankar/TeleGuard/wiki/Troubleshooting#database-issues) |
| **Auto-Reply Not Working** | Check account and settings enabled | [Auto-Reply Guide](https://github.com/MeherMankar/TeleGuard/wiki/Auto-Reply) |
| **Duplicate Messages** | Restart bot to clear handler duplicates | [Handler Issues](https://github.com/MeherMankar/TeleGuard/wiki/Troubleshooting#handlers) |

### Manual Backup Commands (Admin Only)
- **`/backup_status`** - Check backup system status
- **`/backup_now`** - Trigger session backup to GitHub
- **`/backup_settings`** - Backup user settings to Telegram (encrypted)
- **`/backup_ids`** - Backup user IDs to Telegram (unencrypted)
- **`/backup_sessions`** - Backup session files to Telegram (encrypted)
- **`/backup_all`** - Trigger all backup types at once
- **`/compact_now`** - Compact GitHub repository history
- **`/migrate_encrypt_data`** - Encrypt existing unencrypted data
- **`python manual_backup.py`** - Run manual backup script

### Getting Help
- **🐛 Bug Reports**: [GitHub Issues](https://github.com/MeherMankar/TeleGuard/issues)
- **💬 Support**: [Contact Support](https://t.me/ContactXYZrobot)
- **📖 Documentation**: Check code comments and examples
- **🚀 Deployment**: See `deploy/README.md`

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🔗 Links

### 📚 Documentation
- **[📖 Complete Wiki](https://github.com/MeherMankar/TeleGuard/wiki)** - Full documentation
- **[⚡ Quick Start](https://github.com/MeherMankar/TeleGuard/wiki/Quick-Start)** - 5-minute setup guide
- **[🛡️ OTP Destroyer](https://github.com/MeherMankar/TeleGuard/wiki/OTP-Destroyer-Protection)** - Security feature guide
- **[📱 Account Management](https://github.com/MeherMankar/TeleGuard/wiki/Account-Management)** - Account management guide
- **[📨 DM Reply Feature](https://github.com/MeherMankar/TeleGuard/wiki/DM-Reply-Feature)** - Centralized DM management guide
- **[🔧 Configuration](https://github.com/MeherMankar/TeleGuard/wiki/Configuration)** - Complete configuration reference
- **[🆘 Troubleshooting](https://github.com/MeherMankar/TeleGuard/wiki/Troubleshooting)** - Problem solving guide

### 🔗 Links
- **[🐛 Report Issues](https://github.com/MeherMankar/TeleGuard/issues)** - Bug reports and feature requests
- **[💬 Support Chat](https://t.me/ContactXYZrobot)** - Get help from developers
- **[🚀 Deploy Guide](https://github.com/MeherMankar/TeleGuard/wiki/Deployment)** - Cloud deployment instructions
- **[🔒 Security](https://github.com/MeherMankar/TeleGuard/wiki/Security)** - Security guidelines

---

**⚠️ Disclaimer**: This software is for educational and legitimate account management purposes only. Users are responsible for compliance with applicable laws and terms of service.
