# 🤖 TeleGuard - Telegram Account Manager

A professional Telegram bot for managing multiple user accounts with advanced OTP destroyer protection against unauthorized access attempts.

**Developed by:**
- [@Meher_Mankar](https://t.me/Meher_Mankar)
- [@Gutkesh](https://t.me/Gutkesh)

**Support:** [Contact Support](https://t.me/ContactXYZrobot)  
**Documentation:** [📚 Wiki](https://github.com/MeherMankar/TeleGuard/wiki)  
**Repository:** [GitHub](https://github.com/MeherMankar/TeleGuard)

## ⚡ Quick Start

> **📚 For detailed setup instructions, see the [Installation Guide](https://github.com/MeherMankar/TeleGuard/wiki/Installation)**

1. **Clone Repository**
   ```bash
   git clone https://github.com/MeherMankar/TeleGuard.git
   cd TeleGuard
   ```

2. **Install Dependencies**
   ```bash
   pip install -r config/requirements.txt
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

**Next Steps:** Follow the [Quick Start Guide](https://github.com/MeherMankar/TeleGuard/wiki/Quick-Start) for first-time setup.

## 🔧 Configuration

> **📚 Complete configuration guide: [Configuration](https://github.com/MeherMankar/TeleGuard/wiki/Configuration)**

### Required Environment Variables
```bash
# Telegram API (get from https://my.telegram.org)
API_ID=your_api_id_here
API_HASH=your_api_hash_here

# Bot Token (get from @BotFather)
BOT_TOKEN=your_bot_token_here

# Database
MONGO_URI=mongodb://localhost:27017/
DATABASE_URL=sqlite+aiosqlite:///bot_data.db
```

### Optional Features
```bash
# Session Backup (recommended for production)
SESSION_BACKUP_ENABLED=true
GITHUB_REPO=git@github.com:username/sessions-backup.git
GPG_KEY_ID=your_gpg_key_id
FERNET_KEY=your_base64_fernet_key

# Security Settings
MAX_ACCOUNTS=10
RATE_LIMIT_ENABLED=true
AUDIT_LOG_RETENTION_DAYS=30
```

## 🚀 Features

> **📚 Detailed feature documentation: [Features](https://github.com/MeherMankar/TeleGuard/wiki/Features)**

| Feature | Description | Status |
|---------|-------------|--------|
| 🛡️ **[OTP Destroyer](https://github.com/MeherMankar/TeleGuard/wiki/OTP-Destroyer-Protection)** | Real-time protection against unauthorized login attempts | ✅ Active |
| 👤 **[Account Management](https://github.com/MeherMankar/TeleGuard/wiki/Account-Management)** | Manage up to 10 Telegram accounts per user | ✅ Active |
| 🔐 **[Security Features](https://github.com/MeherMankar/TeleGuard/wiki/Security-Features)** | 2FA management, session backup, audit logging | ✅ Active |
| ⚡ **[Automation Engine](https://github.com/MeherMankar/TeleGuard/wiki/Automation-Engine)** | Online maker, scheduled tasks, auto-reply | ✅ Active |
| 📱 **Profile Manager** | Update names, photos, bios, usernames | ✅ Active |
| 🔑 **2FA Management** | Set, change, remove two-factor authentication | ✅ Active |

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
- **Auto-Reply**: Automated message responses
- **Bulk Operations**: Mass account management

## 📱 Usage

> **📚 Complete usage guide: [First Steps](https://github.com/MeherMankar/TeleGuard/wiki/First-Steps)**

### Getting Started
1. Send `/start` to your bot
2. Use the **[Menu System](https://github.com/MeherMankar/TeleGuard/wiki/Menu-System)** to navigate features
3. Add accounts via "📱 Account Settings" → "➕ Add Account"
4. Enable OTP protection in "🛡️ OTP Settings"

### Main Menu Navigation
```
🤖 TeleGuard - Account Manager

👤 Profile Manager     📱 Account Settings
🛡️ OTP Settings       🔐 Sessions
🔑 2FA Settings       ⚙️ Bot Settings
```

### Key Features Access
- **👤 Profile Manager**: Update account profiles and information
- **📱 Account Settings**: Core account management
- **🛡️ OTP Settings**: Configure OTP destroyer protection
- **🔐 Sessions**: Manage active login sessions
- **🔑 2FA Settings**: Two-factor authentication management

### Developer Mode
Enable in **⚙️ Bot Settings** → **🔧 Developer Mode** for text commands:
- `/add` - Add new account
- `/accs` - List accounts
- `/remove` - Remove account
- `/toggle` - Toggle OTP protection
- `/status` - Bot status

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
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  OTP Destroyer  │    │  Database Layer │    │ Session Backup  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🔒 Security

### Data Protection
- **No Personal Data Storage**: Profile information not stored locally
- **Encrypted Sessions**: All session data encrypted with Fernet
- **Secure Logging**: No sensitive information in logs
- **Password Protection**: 2FA passwords hashed with SHA-256

### Session Backup Security
- **Triple Encryption**: Fernet + GPG + GitHub private repository
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
telegram-account-manager/
├── src/                    # Source code
│   ├── bot.py             # Main bot logic
│   ├── menu_system.py     # Inline keyboard system
│   ├── models.py          # Database models
│   └── ...
├── config/                # Configuration files
├── tests/                 # Test suite
├── docs/                  # Documentation
└── scripts/               # Utility scripts
```

### Running Tests
```bash
python -m pytest tests/
```

### Contributing
1. Fork the repository
2. Create feature branch
3. Make changes with tests
4. Submit pull request

## 📋 Requirements

- Python 3.8+
- MongoDB (optional, for session backup)
- Git + GPG (optional, for session backup)
- Telegram API credentials

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
| **Database Connection** | Check MongoDB/SQLite configuration | [Database Issues](https://github.com/MeherMankar/TeleGuard/wiki/Troubleshooting#database-issues) |

### Getting Help
- **📚 Documentation**: [Wiki](https://github.com/MeherMankar/TeleGuard/wiki)
- **🐛 Bug Reports**: [GitHub Issues](https://github.com/MeherMankar/TeleGuard/issues)
- **💬 Support**: [Contact Support](https://t.me/ContactXYZrobot)
- **❓ FAQ**: [Frequently Asked Questions](https://github.com/MeherMankar/TeleGuard/wiki/FAQ)

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🔗 Links

### 📚 Documentation
- **[📖 Complete Wiki](https://github.com/MeherMankar/TeleGuard/wiki)** - Full documentation
- **[⚡ Quick Start](https://github.com/MeherMankar/TeleGuard/wiki/Quick-Start)** - 5-minute setup guide
- **[🛡️ OTP Destroyer](https://github.com/MeherMankar/TeleGuard/wiki/OTP-Destroyer-Protection)** - Security feature guide
- **[📱 Account Management](https://github.com/MeherMankar/TeleGuard/wiki/Account-Management)** - Account management guide
- **[🔧 Configuration](https://github.com/MeherMankar/TeleGuard/wiki/Configuration)** - Complete configuration reference
- **[🆘 Troubleshooting](https://github.com/MeherMankar/TeleGuard/wiki/Troubleshooting)** - Problem solving guide

### 🔗 External Links
- **[📡 API Reference](https://github.com/MeherMankar/TeleGuard/wiki/API-Reference)** - Developer API docs
- **[🐛 Report Issues](https://github.com/MeherMankar/TeleGuard/issues)** - Bug reports and feature requests
- **[💬 Support Chat](https://t.me/ContactXYZrobot)** - Get help from developers
- **[🔒 Security Policy](https://github.com/MeherMankar/TeleGuard/blob/main/SECURITY.md)** - Security guidelines

---

**⚠️ Disclaimer**: This software is for educational and legitimate account management purposes only. Users are responsible for compliance with applicable laws and terms of service.