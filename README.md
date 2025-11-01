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

## 🎯 Feature Comparison

| Feature | Free Version | Premium Features |
|---------|-------------|------------------|
| **Accounts** | Up to 10 | Unlimited |
| **OTP Protection** | ✅ Full | ✅ Full |
| **DM Management** | ✅ Full | ✅ Full |
| **Topic System** | ✅ Full | ✅ Full |
| **SpamMaster** | ✅ Full | ✅ Enhanced |
| **Bulk Sender** | ✅ Full | ✅ Priority |
| **Spam Appeal** | ✅ Basic | ✅ AI-Powered |
| **Device Snooper** | ✅ Full | ✅ Full |
| **Contact Sharing** | ✅ Full | ✅ Full |
| **Chat Import** | ✅ Full | ✅ Full |
| **ID Collector** | ✅ Full | ✅ Full |
| **Audit System** | ✅ 30 days | ✅ Unlimited |
| **Session Protection** | ✅ Full | ✅ Enhanced |
| **Backup System** | ✅ Basic | ✅ Advanced |
| **Support** | Community | Priority |

**Note:** All features are currently available in the free version. Premium features are planned for future releases.

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

### 📊 SpamMaster - Professional Bulk Messaging

**User Gathering**
- Auto-gather from all groups/channels
- Manual gathering from specific groups
- Smart deduplication
- Blacklist management

**Bulk Sending**
- Single account mode
- Multi-account rotation (prevents limits)
- Media support (photos, videos, documents)
- Real-time progress tracking
- Smart delays (40-60s between messages)

**Campaign Management**
- Live campaign monitoring
- Stop/resume campaigns
- Reply tracking and statistics
- Campaign history and analytics

**Group Spam**
- Send to all joined groups
- Automatic group detection
- Rate limiting protection

**Smart Filters**
- Blacklist users by ID
- Smart delay configuration
- Duplicate prevention
- Auto-skip blocked users

**Commands:**
- Access via main menu → "🎯 SpamMaster"
- Warning acceptance required (ToS compliance)
- Full campaign control interface

### 🛡️ Spam Appeal System

**Automated Appeal Process**
- AI-powered appeal message generation
- Smart spam type detection (spamblock, two-way, new account)
- Multi-strategy optimization
- Manual captcha verification support

**Appeal Features**
- Automatic spambot interaction
- Human-like message composition
- Account age-aware messaging
- Success rate optimization

**Spam Type Detection**
- Spamblock restrictions
- Two-way restrictions
- New account limitations
- Time-based restrictions
- Illegal content flags

**Commands:**
- `/appeal` - Start automated appeal
- `/appeal_help` - Get appeal guidance
- `/spam_stats` - View spam detector statistics
- `/test_appeal_messages` - Test appeal system

### 📱 Device Snooper

**Android Device Monitoring**
- Scan active Android devices
- View device history
- Detect suspicious devices
- Monitor device changes

**Device Information**
- Device model and type
- OS name and version
- App name and version
- IP address and country
- Last active timestamp

**Security Features**
- Suspicious device detection
- Session termination
- Device change alerts
- Access pattern analysis

**Commands:**
- Access via main menu → "🕵️ Device Snooper"
- Per-account device scanning
- Real-time device monitoring

### 📤 Bulk Message Sender

**Advanced Bulk Sending**
- Send to username/ID lists
- Send to all contacts
- Multi-account broadcasting
- Button support (URL & callback)

**Message Features**
- Text messages
- Media attachments
- Inline buttons
- Custom formatting

**Smart Routing**
- Access hash resolution
- Cross-account contact sharing
- Automatic entity resolution
- Flood wait handling

**Progress Tracking**
- Real-time progress bars
- Success/failure counts
- Campaign statistics
- Stop/resume controls

**Commands:**
- `/bulk_send` - View bulk sender help
- `/bulk_send_list` - Send to specific users
- `/bulk_send_contacts` - Send to all contacts
- `/bulk_send_all` - Broadcast from all accounts
- `/bulk_jobs` - View active jobs
- `/bulk_stop` - Stop a campaign

### 📇 Contact Sharing

**Cross-Account Contact Sync**
- Share contacts between accounts
- Batch import (100 contacts per batch)
- Phone number preservation
- Name synchronization

**Features**
- Source account selection
- Target account selection
- Progress tracking
- Automatic batching

**Commands:**
- `/share_contacts` - View help
- `/share_contacts source target` - Share contacts

### 💬 Chat Import System

**Retroactive Topic Creation**
- Import existing private chats
- Auto-create topics for conversations
- Import message history (last 5 messages)
- Preserve conversation context

**Import Features**
- Multi-account scanning
- Private chat detection
- Bot/deleted account filtering
- Progress tracking

**Topic Management**
- Automatic topic naming
- Message history import
- Chronological ordering
- Context preservation

**Commands:**
- `/import_chats` - Import all existing chats
- `/check_admin_group` - Verify group setup
- `/import_help` - Get import guidance

### 📊 Comprehensive Audit System

**Activity Tracking**
- All bot actions logged
- Active sim activities
- Account management events
- Security events

**Audit Events**
- Reactions posted
- Channels joined/left
- Messages sent
- Comments posted
- Poll votes
- Profile views
- Entity views
- Session activities

**Audit Features**
- 30-day retention
- Per-account logs
- Activity summaries
- Real-time tracking
- Quick access logs

**Data Tracked**
- Event type and timestamp
- Action details
- IP addresses
- User context
- Account information

### 🔍 ID Collector

**Silent ID Collection**
- Automatic collection every 6 hours
- Scans all managed accounts
- Collects from dialogs and groups
- Exports to CSV

**Collection Features**
- User IDs from direct chats
- Participant IDs from groups
- Channel member IDs
- Smart deduplication

**Export & Delivery**
- CSV file generation
- Automatic admin delivery
- Logs bot integration
- Timestamp tracking

**Data Format**
- User ID
- Collection timestamp
- Sorted output
- UTF-8 encoding

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
👥 Contacts           🎯 SpamMaster    ❓ Help
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

### SpamMaster Issues

**Gathering Not Working**
```bash
# Check account connection
- Verify account is active
- Check group permissions
- Try manual gathering first
```

**Campaign Stuck**
```bash
# Stop and restart
/bulk_stop <job_id>
# Check for flood wait
# Reduce sending speed
```

**No Users Gathered**
- Ensure you're in groups/channels
- Check account has access
- Try auto-gather mode
- Verify account permissions

### Bulk Sender Issues

**Access Hash Errors**
- Use `/share_contacts` to sync contacts
- Ensure target users are in contacts
- Try different source account

**Flood Wait Errors**
- Automatic handling built-in
- Wait for specified time
- Use multi-account rotation

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `AUTH_KEY_UNREGISTERED` | Session conflict | Re-add account |
| `PHONE_CODE_INVALID` | Wrong OTP | Request new code |
| `SESSION_PASSWORD_NEEDED` | 2FA required | Provide password |
| `FLOOD_WAIT` | Rate limited | Wait specified time |
| `Could not find entity` | Invalid group ID | Check group ID |
| `No access_hash` | User not in contacts | Use contact sharing |
| `Captcha required` | Manual verification | Complete captcha manually |

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

## 🔧 Additional Features

### Account Age Estimation

**Smart Age Detection**
- Estimates account creation date
- Uses anchor data and ID ranges
- Caches results for performance
- Manual age override support

**Commands:**
- `/account_age` - Check account age
- `/set_manual_age` - Override estimated age
- `/clear_age_cache` - Clear cached ages

### Session Guardian

**Advanced Session Protection**
- Real-time session monitoring
- Automatic threat detection
- Session health scoring
- Risk level assessment

**Protection Features**
- Rate limit tracking
- Activity throttling
- Cooldown management
- Automatic recovery

### Network Optimization

**Connection Management**
- Smart connection pooling
- Automatic reconnection
- Network error handling
- Bandwidth optimization

### Redis Caching

**Performance Enhancement**
- Fast data access
- Session caching
- Query optimization
- Distributed caching support

### Task Queue System

**Background Processing**
- Asynchronous task execution
- Priority queue management
- Job scheduling
- Error recovery

### API Security

**Enhanced Security**
- Rate limiting
- Request validation
- Token management
- Access control

### Comprehensive Logging

**Advanced Logging**
- Structured logging
- Log rotation
- Error tracking
- Performance monitoring
- Audit trails

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

## 📝 Complete Command Reference

### Core Commands

**Basic**
- `/start` - Start the bot and show main menu
- `/help` - Show help information
- `/support` - Contact support

**Account Management**
- `/add_account` - Add new Telegram account
- `/remove_account` - Remove account from bot
- `/my_accounts` - List all your accounts
- `/cleanup_accounts` - Remove inactive accounts

**OTP Protection**
- `/otp_debug` - Check OTP handler status
- `/otp_fix` - Force re-register OTP handlers
- `/test_otp` - Test OTP configuration

**DM Management**
- `/set_dm_group` - Configure admin group for DMs
- `/debug_topics` - Show topic mappings
- `/dm_status` - Check DM reply status
- `/block` - Block user in current topic
- `/clear_history` - Clear chat history in topic

**Session Management**
- `/session_health` - Check session health
- `/export_session` - Export session string
- `/import_session` - Import session string

### Advanced Commands

**Spam Appeal**
- `/appeal` - Start automated spam appeal
- `/appeal_help` - Get appeal guidance
- `/spam_stats` - View spam statistics
- `/test_appeal_messages` - Test appeal system

**Bulk Messaging**
- `/bulk_send` - Bulk sender help
- `/bulk_send_list` - Send to user list
- `/bulk_send_contacts` - Send to all contacts
- `/bulk_send_all` - Broadcast from all accounts
- `/bulk_jobs` - View active campaigns
- `/bulk_stop <job_id>` - Stop campaign

**Contact Management**
- `/share_contacts` - Share contacts between accounts
- `/export_contacts` - Export contacts to CSV

**Chat Import**
- `/import_chats` - Import existing chats to topics
- `/check_admin_group` - Verify group configuration
- `/import_help` - Get import guidance

**Backup & Recovery**
- `/backup_status` - Check backup status
- `/backup_now` - Trigger GitHub backup
- `/backup_settings` - Backup to Telegram
- `/backup_sessions` - Backup session files
- `/backup_all` - All backup types

**Developer Commands**
- `/dev_stats` - System statistics
- `/dev_logs` - View recent logs
- `/dev_cleanup` - Clean up database
- `/dev_test` - Run system tests

### Activity Simulation Commands

**Online Maker**
- `/online_start` - Start online maker
- `/online_stop` - Stop online maker
- `/online_status` - Check online status

**Simulation**
- `/sim_start` - Start activity simulation
- `/sim_stop` - Stop simulation
- `/sim_config` - Configure simulation

### Monitoring Commands

**Account Age**
- `/account_age` - Check account age
- `/set_manual_age` - Override estimated age
- `/clear_age_cache` - Clear age cache

**Device Monitoring**
- Access via menu → Device Snooper
- Scan devices per account
- View device history
- Detect suspicious devices

**Audit Logs**
- `/audit_log` - View audit logs
- `/activity_summary` - Get activity summary

---

## 🔗 Links

- **GitHub:** [MeherMankar/TeleGuard](https://github.com/MeherMankar/TeleGuard)
- **Issues:** [Report Bug](https://github.com/MeherMankar/TeleGuard/issues)
- **Support:** [@ContactXYZrobot](https://t.me/ContactXYZrobot)
- **Developers:** [@Meher_Mankar](https://t.me/Meher_Mankar) • [@Gutkesh](https://t.me/Gutkesh)

---

## ❓ Frequently Asked Questions

### General Questions

**Q: Is TeleGuard safe to use?**
A: Yes, TeleGuard uses official Telegram APIs and implements security best practices. However, bulk messaging features may violate Telegram's ToS.

**Q: How many accounts can I manage?**
A: Up to 10 accounts per user by default. This can be configured in settings.

**Q: Does TeleGuard store my passwords?**
A: 2FA passwords are hashed with SHA-256. Session strings are encrypted with Fernet. No plaintext storage.

**Q: Can I use TeleGuard on multiple devices?**
A: Yes, but only one instance should run at a time per account to avoid conflicts.

### Feature Questions

**Q: How does OTP Destroyer work?**
A: It monitors incoming messages from Telegram (777000), detects login codes, and calls the official `invalidateSignInCodes` API to block unauthorized logins.

**Q: What's the difference between OTP Destroyer and OTP Forward?**
A: Destroyer invalidates codes (blocks logins), Forward sends codes to you (allows logins). Use Destroyer for security, Forward for convenience.

**Q: How do I set up DM management?**
A: Create a forum group, add bot as admin, send `/set_dm_group`, provide group ID. All DMs will auto-create topics.

**Q: Can I import existing conversations?**
A: Yes! Use `/import_chats` to retroactively create topics for all existing private chats.

**Q: Is SpamMaster legal?**
A: Bulk messaging violates Telegram's ToS and may result in account bans. Use at your own risk with test accounts.

**Q: How does the spam appeal system work?**
A: It uses AI to generate optimized appeal messages, automatically interacts with @spambot, and handles captcha verification.

**Q: What is Device Snooper?**
A: It monitors active Android devices on your accounts, detects suspicious logins, and allows session termination.

**Q: How does ID Collector work?**
A: It silently scans all your accounts every 6 hours, collects user IDs from dialogs and groups, and exports to CSV.

### Technical Questions

**Q: What database does TeleGuard use?**
A: MongoDB for data storage, with optional Redis for caching.

**Q: Can I run TeleGuard on Heroku?**
A: Yes, one-click deployment is available. See deployment section.

**Q: How do I backup my data?**
A: Use `/backup_all` for complete backup, or individual backup commands for specific data.

**Q: What happens if my session expires?**
A: You'll need to re-add the account. Enable OTP Destroyer to prevent unauthorized session creation.

**Q: Can I use TeleGuard with Telegram Premium?**
A: Yes, all features work with both free and premium Telegram accounts.

### Troubleshooting Questions

**Q: Why aren't topics being created?**
A: Ensure your admin group is a forum group, bot is admin, and has "Manage Topics" permission. Use `/check_admin_group` to verify.

**Q: Why is OTP Destroyer not working?**
A: Run `/otp_debug` to check status, `/otp_fix` to re-register handlers, and `/test_otp` to test configuration.

**Q: How do I fix "Could not find entity" errors?**
A: Use `/share_contacts` to sync contacts between accounts, or ensure the user is in your contacts.

**Q: What should I do if I get flood wait errors?**
A: Wait for the specified time. Use multi-account rotation in SpamMaster to avoid rate limits.

**Q: Why can't I send messages to some users?**
A: You need their access_hash. Use `/share_contacts` to import contacts from another account that has them.

### Security Questions

**Q: How secure is my data?**
A: Sessions are encrypted with Fernet, passwords are hashed with SHA-256, and all data is stored securely in MongoDB.

**Q: Can someone hack my account through TeleGuard?**
A: No, TeleGuard uses official APIs and doesn't expose your credentials. Enable OTP Destroyer for additional protection.

**Q: What data does TeleGuard collect?**
A: Only data necessary for functionality (sessions, settings, audit logs). No data is shared with third parties.

**Q: How do I delete my data?**
A: Remove all accounts from the bot, then contact support for complete data deletion.

---

## ⚠️ Disclaimer

This software is provided for educational and legitimate account management purposes only. Users are solely responsible for ensuring compliance with:

- Telegram's Terms of Service
- Local laws and regulations
- Privacy and data protection laws
- Applicable cybersecurity regulations

The developers assume no liability for misuse of this software. Use at your own risk.

**Important Warnings:**
- SpamMaster bulk messaging violates Telegram ToS and may result in account bans
- Use test accounts for bulk messaging, not your main account
- Spam appeal success is not guaranteed
- ID collection should comply with privacy laws
- Device snooping is for security purposes only

---

**Made with ❤️ by the TeleGuard Team**
