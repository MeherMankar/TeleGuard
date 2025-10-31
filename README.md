# 🤖 TeleGuard - Advanced Telegram Account Manager

A professional, feature-rich Telegram bot for managing multiple user accounts with advanced security, automation, and centralized communication management.

**Developed by:**
- [@Meher_Mankar](https://t.me/Meher_Mankar)
- [@Gutkesh](https://t.me/Gutkesh)

**Support:** [Contact Support](https://t.me/ContactXYZrobot)  
**Repository:** [GitHub](https://github.com/MeherMankar/TeleGuard)

---

## 📑 Table of Contents

- [Quick Start](#-quick-start)
- [Features](#-features)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage Guide](#-usage-guide)
- [Advanced Features](#-advanced-features)
- [Security](#-security)
- [Troubleshooting](#-troubleshooting)
- [Development](#-development)
- [License](#-license)

---

## ⚡ Quick Start

### One-Click Deploy

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/MeherMankar/TeleGuard)

### Local Installation

```bash
# Clone repository
git clone https://github.com/MeherMankar/TeleGuard.git
cd TeleGuard

# Install dependencies
pip install -r requirements.txt

# Configure
cp config/.env.example config/.env
# Edit config/.env with your credentials

# Run
python main.py
```

---

## 🚀 Features

### 🛡️ OTP Protection System

**OTP Destroyer** - Real-time protection against unauthorized login attempts
- Automatically invalidates unauthorized login codes using Telegram's official API
- Instant notifications when attacks are blocked
- Zero false positives - only triggers on actual login attempts
- Works in real-time without delays

**OTP Forward** - Receive login codes via bot
- Forwards OTP codes to you through the bot
- Works when destroyer is disabled
- Useful for legitimate logins

**Temp OTP** - Temporary 5-minute access
- Temporarily disables destroyer for 5 minutes
- Forwards codes during this period
- Auto-expires after 5 minutes
- Perfect for when you need to login

**Commands:**
- `/otp_debug` - Check OTP handler status for all accounts
- `/otp_fix` - Force re-register OTP handlers
- `/test_otp` - Test OTP handler setup and configuration

### 📨 DM Management with Forum Topics

**Auto-Topic Creation**
- Every DM automatically creates a dedicated topic in your forum group
- Each conversation has its own persistent thread
- Topics named: "Sender Name → Account Name"
- No manual setup needed - works automatically

**Advanced Topic Actions**

1. **Close Topic = Block User**
   - Close any topic in Telegram
   - User automatically blocked on that account
   - Permanent block (manual unblock required)

2. **Clear Chat History**
   - Send `/clear_history` in any topic
   - Deletes entire chat history with that user
   - Works on both sides (you and them)
   - Irreversible action

3. **General Topic Broadcast**
   - Send message in General topic (ID=1)
   - Broadcasts to ALL users from ALL accounts
   - Smart routing: each account sends to its users
   - Perfect for announcements

4. **Manual Commands**
   - `/block` - Block user in current topic
   - `/clear_history` - Clear history in current topic
   - `/debug_topics` - Show all topic mappings

**Setup:**
1. Create a forum group in Telegram
2. Add bot as admin with topic management permissions
3. Send `/set_dm_group` to bot
4. Provide group ID (use @userinfobot to get it)
5. Done! All DMs now create topics automatically

### 👤 Account Management

**Multi-Account Support**
- Manage up to 10 Telegram accounts per user
- Add accounts via phone number + OTP + 2FA
- Import existing sessions (string or file)
- Export sessions for backup

**Profile Management**
- Update first name and last name
- Change username
- Update bio/about
- Change profile photo
- All changes applied instantly

**Session Control**
- View all active sessions
- Terminate specific sessions
- Monitor session health
- Session protection system

**2FA Management**
- Set two-factor authentication password
- Change existing 2FA password
- Remove 2FA protection
- Secure password storage (SHA-256 hashed)

### 💬 Messaging & Communication

**Smart Message Routing**
- Send messages from any account
- Target users, groups, or channels
- Template support for quick replies
- Message history tracking

**Auto-Reply System**
- Keyword-based auto-replies
- Time-aware responses
- Template integration
- Enable/disable per account

**Message Templates**
- Create reusable message templates
- Variables support
- Quick access from messaging menu
- Import/export templates

### 📢 Channel Management

**Channel Operations**
- Join channels/groups by username or link
- Leave channels/groups
- Create new channels (public/private)
- Create new groups
- Delete owned channels

**Bulk Operations**
- Join multiple channels at once
- Leave multiple channels
- Export channel list

### 👥 Contact Management

**Contact Export**
- Export all contacts to CSV
- Includes: name, username, phone, user ID
- One-click export
- Compatible with Excel/Google Sheets

**Contact Operations**
- Add new contacts
- Search contacts
- Tag and categorize
- Create contact groups
- Import from external sources
- Two-way Telegram sync

### 🎭 Activity Simulation

**Human-Like Behavior**
- Random online/offline patterns
- Realistic typing indicators
- Natural response delays
- Prevents detection as bot

**Online Maker**
- Keep accounts online automatically
- Configurable intervals
- Per-account control
- Stealth mode available

### ⚡ Automation Engine

**Scheduled Tasks**
- Schedule messages
- Automated actions
- Recurring tasks
- Time-zone aware

**Smart Automation**
- Conditional triggers
- Multi-step workflows
- Error handling
- Activity logging

---

## 📥 Installation

### Requirements

- Python 3.11 or higher
- Telegram API credentials (API_ID, API_HASH)
- Bot token from @BotFather
- MongoDB (auto-configured for cloud platforms)

### Local Setup

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
nano config/.env  # or use any text editor
```

4. **Run Bot**
```bash
python main.py
```

### Cloud Deployment

**Heroku**
```bash
./deploy/heroku.sh
```

**Koyeb**
```bash
./deploy/koyeb.sh
```

**Docker**
```bash
docker-compose up -d
```

---

## 🔧 Configuration

### Required Environment Variables

```bash
# Telegram API (get from https://my.telegram.org)
API_ID=12345678
API_HASH=abcdef1234567890abcdef1234567890

# Bot Token (get from @BotFather)
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz

# Admin Access (your Telegram user ID)
ADMIN_IDS=123456789,987654321
```

### Optional Settings

```bash
# Database
MONGODB_URI=mongodb://localhost:27017/teleguard

# Security
MAX_ACCOUNTS=10
RATE_LIMIT_ENABLED=true

# Features
OTP_DESTROYER_ENABLED=true
AUTO_BACKUP_ENABLED=true

# Logging
LOG_LEVEL=INFO
LOG_FILE=bot.log
```

---

## 📱 Usage Guide

### Getting Started

1. **Start Bot**
   - Send `/start` to your bot
   - You'll see the main menu with buttons

2. **Add Account**
   - Click "📱 Account Settings"
   - Click "➕ Add Account"
   - Enter phone number with country code
   - Enter OTP code received
   - Enter 2FA password if enabled

3. **Enable OTP Protection**
   - Click "🛡️ OTP Manager"
   - Select account
   - Enable "OTP Destroyer"

4. **Setup DM Management**
   - Create a forum group in Telegram
   - Add bot as admin
   - Send `/set_dm_group` to bot
   - Provide group ID

### Main Menu

```
📱 Account Settings    🛡️ OTP Manager
💬 Messaging          📢 Channels
👥 Contacts           ❓ Help
🆘 Support            ⚙️ Developer
```

### Account Settings Menu

- **➕ Add Account** - Add new Telegram account
- **📋 My Accounts** - View and manage accounts
- **👤 Profile Manager** - Update profile information
- **🔐 Session Manager** - View/terminate sessions
- **🔑 2FA Manager** - Manage two-factor authentication
- **🗑️ Remove Account** - Delete account from bot

### OTP Manager Menu

- **🛡️ OTP Destroyer** - Enable/disable destroyer
- **📨 OTP Forward** - Enable/disable forwarding
- **⏰ Temp OTP** - 5-minute temporary access
- **📊 OTP Status** - View protection status
- **🔧 Settings** - Configure OTP behavior

### Messaging Menu

- **✉️ Send Message** - Send message from account
- **🤖 Auto-Reply** - Configure auto-replies
- **📝 Templates** - Manage message templates
- **📊 Statistics** - View messaging stats

### Channel Manager Menu

- **➕ Join Channel** - Join channel/group
- **➖ Leave Channel** - Leave channel/group
- **🆕 Create Channel** - Create new channel
- **🆕 Create Group** - Create new group
- **📋 My Channels** - List joined channels
- **🗑️ Delete Channel** - Delete owned channel

---

## 🎯 Advanced Features

### OTP Protection Deep Dive

**How It Works:**
1. Bot monitors incoming messages from Telegram (777000)
2. Detects login code messages
3. Extracts OTP code
4. Calls `account.invalidateSignInCodes` API
5. Deletes message and notifies you

**Priority System:**
1. Fresh session OTPs (protected)
2. Temp OTP (5-min forwarding)
3. OTP Destroyer (invalidation)
4. OTP Forward (forwarding)

**Protection Features:**
- Wildcard protection for account addition
- Duplicate prevention
- Message deduplication
- Auto-handler refresh

### Topic Management Deep Dive

**Topic Structure:**
- Each topic = One conversation
- Topic title: "Sender → Account"
- System message with mapping info
- Persistent across restarts

**Topic Mapping:**
```
Topic ID → Sender ID + Account ID
Stored in: dm_topics collection
Auto-created on first DM
```

**Advanced Actions:**
- Close topic → Block user (automatic)
- Bulk delete → Clear history (manual command)
- General topic → Broadcast (automatic)

### Session Management

**Session Health Monitoring:**
- Connection status
- Message count tracking
- Join activity monitoring
- Risk level assessment
- Health score (0-100)

**Session Protection:**
- Rate limit tracking
- Activity throttling
- Cooldown management
- Automatic recovery

**Commands:**
- `/session_health` - Check session health
- `/cleanup_accounts` - Remove inactive accounts

### Automation System

**Job Types:**
- Online maker (keep accounts online)
- Scheduled messages
- Auto-reply triggers
- Activity simulation
- Contact sync

**Configuration:**
- Per-account settings
- Time-based triggers
- Conditional execution
- Error handling

---

## 🔒 Security

### Data Encryption

**Session Storage:**
- Fernet encryption for all session strings
- Double encryption for sensitive data
- Encrypted at rest in MongoDB
- Secure key management

**Password Storage:**
- SHA-256 hashing for 2FA passwords
- No plaintext storage
- Secure retrieval system
- Auto-cleanup on account removal

**Database Security:**
- Field-level encryption
- Encrypted backups
- Access control
- Audit logging

### Session Backup

**GitHub Backup:**
- Encrypted session files
- GPG signing for integrity
- Private repository
- Automated rotation
- History compaction

**Telegram Backup:**
- Encrypted user settings
- Session file backups
- ID backups (unencrypted)
- Manual trigger available

**Backup Commands:**
- `/backup_status` - Check backup status
- `/backup_now` - Trigger GitHub backup
- `/backup_settings` - Backup to Telegram
- `/backup_sessions` - Backup session files
- `/backup_all` - All backup types

### Security Best Practices

1. **Keep credentials secure**
   - Never share .env file
   - Use strong bot token
   - Rotate API credentials regularly

2. **Monitor activity**
   - Check audit logs
   - Review session health
   - Monitor OTP notifications

3. **Regular maintenance**
   - Update dependencies
   - Clean up inactive accounts
   - Verify backups

4. **Access control**
   - Limit admin IDs
   - Use 2FA on accounts
   - Enable OTP destroyer

---

## 🆘 Troubleshooting

### OTP Issues

**OTP Destroyer Not Working**
```bash
# Check handler status
/otp_debug

# Re-register handlers
/otp_fix

# Test setup
/test_otp
```

**OTP Forward Not Working**
- Ensure destroyer is disabled
- Check handler registration
- Verify account settings
- Run `/otp_fix`

**Temp OTP Not Working**
- Ensure destroyer is enabled first
- Check expiry time (5 minutes)
- Verify handler status
- Re-enable if expired

### Topic Issues

**Topics Not Created**
```bash
# Check topic status
/debug_topics

# Verify setup
- Bot is admin in group
- Group has topics enabled
- Correct group ID set
```

**Topics Not Working**
- Handlers auto-refresh on account add
- Check `/debug_topics` for status
- Verify bot permissions
- Re-add accounts if needed

### Account Issues

**Session Errors**
- Re-add affected account
- Check for session conflicts
- Verify 2FA password
- Use `/cleanup_accounts`

**Rate Limiting**
- Wait for cooldown period
- Use different phone number
- Check Telegram limits
- Monitor with `/session_health`

**Connection Issues**
- Check internet connection
- Verify API credentials
- Restart bot
- Check MongoDB connection

### Database Issues

**MongoDB Connection Failed**
- Verify MONGODB_URI
- Check MongoDB service status
- Ensure network access
- Check credentials

**Data Not Saving**
- Check database permissions
- Verify encryption keys
- Check disk space
- Review error logs

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `AUTH_KEY_UNREGISTERED` | Session conflict | Re-add account |
| `PHONE_CODE_INVALID` | Wrong OTP | Request new code |
| `SESSION_PASSWORD_NEEDED` | 2FA required | Provide password |
| `FLOOD_WAIT` | Rate limited | Wait specified time |
| `Could not find entity` | Invalid group ID | Check group ID |

### Debug Commands

```bash
# OTP System
/otp_debug          # Handler status
/otp_fix            # Re-register handlers
/test_otp           # Test configuration

# Topics
/debug_topics       # Topic mappings
/dm_status          # DM reply status

# Sessions
/session_health     # Session health check
/cleanup_accounts   # Remove inactive

# System
/backup_status      # Backup system status
```

### Getting Help

1. **Check Logs**
   - Review `bot.log` file
   - Look for error messages
   - Check timestamps

2. **Use Debug Commands**
   - Run relevant debug command
   - Share output with support

3. **Contact Support**
   - Telegram: [@ContactXYZrobot](https://t.me/ContactXYZrobot)
   - GitHub: [Issues](https://github.com/MeherMankar/TeleGuard/issues)
   - Provide: Error message, logs, steps to reproduce

---

## 🛠️ Development

### Project Structure

```
TeleGuard/
├── teleguard/
│   ├── core/
│   │   ├── bot_manager.py       # Main bot manager
│   │   ├── otp_manager.py       # OTP protection
│   │   ├── mongo_database.py    # Database layer
│   │   └── config.py            # Configuration
│   ├── handlers/
│   │   ├── auth_handler.py      # Authentication
│   │   ├── dm_reply_handler.py  # DM management
│   │   ├── topic_actions_handler.py  # Topic actions
│   │   ├── menu_system.py       # Menu interface
│   │   └── command_handlers.py  # Commands
│   ├── utils/
│   │   ├── session_protection.py
│   │   ├── bot_logger.py
│   │   └── error_handler.py
│   └── workers/
│       ├── session_monitor.py
│       └── activity_simulator.py
├── config/
│   ├── .env.example
│   └── config.yaml
├── deploy/
│   ├── heroku.sh
│   ├── koyeb.sh
│   └── docker-compose.yml
├── tests/
├── main.py
└── requirements.txt
```

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/ -v

# Run with debug logging
LOG_LEVEL=DEBUG python main.py

# Format code
black teleguard/
isort teleguard/
```

### Adding Features

1. **Create Handler**
```python
# teleguard/handlers/my_handler.py
class MyHandler:
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
    
    def register_handlers(self):
        @self.bot.on(events.NewMessage(pattern='/mycommand'))
        async def my_command(event):
            await event.reply("Hello!")
```

2. **Register in BotManager**
```python
# teleguard/core/bot_manager.py
from ..handlers.my_handler import MyHandler

async def _initialize_handlers(self):
    self.my_handler = await self.component_manager.initialize_component(
        "my_handler", MyHandler, self
    )
```

### Testing

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_otp_manager.py

# Run with coverage
pytest --cov=teleguard tests/
```

### Deployment

**Heroku:**
```bash
heroku create my-teleguard-bot
heroku config:set API_ID=xxx API_HASH=xxx BOT_TOKEN=xxx
git push heroku main
```

**Docker:**
```bash
docker build -t teleguard .
docker run -d --env-file .env teleguard
```

---

## 📊 Architecture

### System Flow

```
User → Telegram → Bot
         ↓
    Bot Manager
         ↓
    ┌────┴────┐
    ↓         ↓
Handlers   Workers
    ↓         ↓
Database  Clients
```

### Component Interaction

```
Menu System → Command Handlers → Account Manager
                                       ↓
                                  User Clients
                                       ↓
                              ┌────────┴────────┐
                              ↓                 ↓
                         OTP Manager      DM Handler
                              ↓                 ↓
                         Destroyer        Topic Manager
```

### Data Flow

```
User Input → Validation → Processing → Database → Response
                ↓              ↓           ↓
            Security      Encryption   Backup
```

---

## 📄 License

MIT License

Copyright (c) 2024 TeleGuard

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

## 🔗 Links

- **GitHub:** [MeherMankar/TeleGuard](https://github.com/MeherMankar/TeleGuard)
- **Issues:** [Report Bug](https://github.com/MeherMankar/TeleGuard/issues)
- **Support:** [@ContactXYZrobot](https://t.me/ContactXYZrobot)
- **Developers:** [@Meher_Mankar](https://t.me/Meher_Mankar) • [@Gutkesh](https://t.me/Gutkesh)

---

## ⚠️ Disclaimer

This software is provided for educational and legitimate account management purposes only. Users are solely responsible for ensuring compliance with:

- Telegram's Terms of Service
- Local laws and regulations
- Privacy and data protection laws
- Applicable cybersecurity regulations

The developers assume no liability for misuse of this software. Use at your own risk.

---

**Made with ❤️ by the TeleGuard Team**
