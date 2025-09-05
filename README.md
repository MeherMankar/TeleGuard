# 🤖 TeleGuard - Telegram Account Manager

A professional Telegram bot for managing multiple user accounts with advanced OTP destroyer protection against unauthorized access attempts.

**Developed by:**
- @Meher_Mankar
- @Gutkesh

**Support:** https://t.me/ContactXYZrobot

## ⚡ Quick Start

1. **Clone Repository**
   ```bash
   git clone https://github.com/mehermankar/teleguard.git
   cd telegram-account-manager
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**
   ```bash
   cp config/.env.example .env
   # Edit .env with your credentials
   ```

4. **Run Bot**
   ```bash
   python main.py
   ```

## 🔧 Configuration

### Required Environment Variables
```bash
# Telegram API (get from https://my.telegram.org)
API_ID=your_api_id
API_HASH=your_api_hash

# Bot Token (get from @BotFather)
BOT_TOKEN=your_bot_token

# Database
MONGO_URI=mongodb://localhost:27017/
```

### Optional Features
```bash
# Session Backup (recommended for production)
SESSION_BACKUP_ENABLED=true
GITHUB_REPO=git@github.com:username/sessions-repo.git
GPG_KEY_ID=your_gpg_key_id
FERNET_KEY=your_base64_fernet_key
```

## 🚀 Features

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
- **Auto-Reply**: Automated message responses (coming soon)
- **Bulk Operations**: Mass account management

## 📱 Usage

### Getting Started
1. Send `/start` to your bot
2. Use the inline menu system to navigate features
3. Add accounts via "Account Settings" → "Add Account"
4. Enable OTP protection in "OTP Settings"

### Menu Navigation
- **👤 Profile Manager**: Update account profiles and information
- **📱 Account Settings**: Core account management
- **🛡️ OTP Settings**: Configure OTP destroyer protection
- **🔐 Sessions**: Manage active login sessions
- **🔑 2FA Settings**: Two-factor authentication management

### Developer Mode
Enable in settings for text command access:
- `/add` - Add new account
- `/accs` - List accounts
- `/remove` - Remove account
- `/toggle_protection` - Toggle OTP destroyer

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Telegram Bot  │────│  Account Manager │────│   User Clients  │
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

### Common Issues

**Rate Limiting**
```
Error: A wait of X seconds is required
Solution: Wait for cooldown or use different number
```

**2FA Required**
```
Error: Two-factor authentication password required
Solution: Provide 2FA password when prompted
```

**Session Errors**
```
Error: Session revoked
Solution: Re-add affected accounts
```

**MongoDB Connection**
```
Error: ServerSelectionTimeoutError
Solution: Check MongoDB is running and MONGO_URI
```

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🔗 Links

- **Documentation**: [Wiki](../../wiki)
- **Issues**: [GitHub Issues](../../issues)

---

**⚠️ Disclaimer**: This software is for educational and legitimate account management purposes only. Users are responsible for compliance with applicable laws and terms of service.