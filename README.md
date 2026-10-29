# 🛡️ TeleGuard

> **Telegram Account Manager with Security and Automation Tools**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-blue.svg)](https://t.me/ContactXYZrobot)

Manage Telegram accounts with security features, automated workflows, and a web dashboard.

---

## ✨ Key Features

### 🔐 Security Suite
- **OTP Protection** - Monitor and handle incoming login-code messages using the configured protection settings
- **2FA Management** - Manage two-factor authentication during account sign-in
- **Session Guardian** - Review and manage Telegram sessions
- **Proxy Support** - MTProto/SOCKS5/HTTP with automatic bridge for Telethon compatibility

### 📱 Account Management
- **Multi-Account Support** - Manage multiple Telegram accounts from one interface
- **Profile Manager** - Update names, usernames, bios, and profile photos
- **Universal Session Import** - Import sessions from Telethon, Pyrogram, and TData formats
- **Session Export** - Export session strings with DC information
- **Bulk Import** - Import session files from ZIP archives

### 💬 Messaging Tools
- **Unified DM Management** - Centralized inbox with forum topics for all accounts
- **Auto-Reply System** - Keyword-based automatic responses
- **Bulk Messaging** - Send a message to multiple targets
- **Message Templates** - Create and reuse message templates

### 📢 Channel Operations
- **Channel Manager** - Join, leave, create, and delete channels
- **Bulk Operations** - Mass join/leave channels across accounts
- **Channel Statistics** - Track engagement and activity metrics

### 🧹 Cleanup Tools
- **Smart Chat Cleanup** - Remove personal, bot, and spam chats
- **Mass Exit** - Leave multiple channels and groups at once
- **Spam Appeal** - Automated spam restriction appeal system

### 🎭 Automation
- **Activity Simulator** - Configure account activity behavior
- **Online Maker** - Keep accounts online automatically
- **Contact Export** - Export contacts to CSV with full details

---

## 🚀 Quick Start

### Prerequisites

```bash
Python 3.11+
MongoDB 4.4+
Telegram API Credentials (api_id, api_hash)
```

### Installation

```bash
# Clone repository
git clone https://github.com/mehermankar/teleguard.git
cd teleguard

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup configuration
cp config/.env.example config/.env
```

### Configuration

Edit `config/.env`:

```env
# Telegram API (get from https://my.telegram.org)
API_ID=12345678
API_HASH=your_api_hash_here
BOT_TOKEN=your_bot_token_here

# Database
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=teleguard

# Security
JWT_SECRET=
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:4173
ADMIN_IDS=123456789,987654321

# Optional
SESSION_BACKUP_ENABLED=false
# To enable GitHub session backups, also set GITHUB_REPO, GITHUB_TOKEN,
# and a stable FERNET_KEY; MongoDB remains the live database.
```

Generate `JWT_SECRET` with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

In production, use a unique secret and set `ALLOWED_ORIGINS` to the exact
origin(s) serving the frontend. The frontend build also needs `VITE_API_URL`
and `VITE_WS_URL` set to the backend's HTTPS and WSS URLs, respectively.

### Run

```bash
# Start bot
python main.py

# Or use start script
python start_bot.py
```

---

## 📖 Usage Guide

### Basic Commands

| Command | Description |
|---------|-------------|
| `/start` | Initialize bot and show main menu |
| `/add` | Add new Telegram account |
| `/accs` | List all managed accounts |
| `/otp` | Toggle OTP Destroyer protection |
| `/help` | Show comprehensive help |

### Menu Navigation

Access features through inline keyboard:

```
📱 Account Settings → Manage accounts, profiles, sessions
🛡️ OTP Manager → Security features and protection
💬 Messaging → DM management, auto-reply, bulk send
📢 Channels → Channel operations and management
👥 Contacts → Contact export and synchronization
🧹 Cleanup → Account cleanup and spam appeals
```

### Adding Your First Account

**Method 1: Phone Login**
1. Click **📱 Account Settings** or use `/add`
2. Send phone number with country code: `+1234567890`
3. Enter OTP code with hyphens: `1-2-3-4-5`
4. If 2FA enabled, enter password
5. Account added successfully! ✅

**Method 2: Session Import**
1. Click **📱 Account Settings** → **Session Login**
2. Choose import method:
   - **📁 Session File** - Upload .session file (Telethon/Pyrogram)
   - **📝 Session String** - Paste session string
   - **📦 Bulk Import** - Upload ZIP with multiple sessions
   - **📂 TData Import** - Upload Telegram Desktop TData folder
3. Upload/paste your session data
4. Automatic format detection and conversion
5. Account imported successfully! ✅

### Enabling OTP Protection

1. Go to **🛡️ OTP Manager**
2. Select **OTP Destroyer**
3. Choose account to protect
4. Click **Enable Destroyer**
5. Your account is now protected from unauthorized logins! 🛡️

---

## 🏗️ Architecture

```
teleguard/
├── backend/       # FastAPI routes, authentication, and WebSocket API
├── config/        # Environment examples and application configuration
├── frontend/      # Vite/React dashboard
├── teleguard/
│   ├── core/      # Bot lifecycle, database, and feature managers
│   ├── handlers/  # Telegram bot and event handlers
├── tests/         # Python tests
├── main.py        # Combined bot and API entry point
├── requirements.txt
└── pyproject.toml
```

---

## 🔒 Security Features

### Encryption
- Session backups use Fernet encryption when configured with a stable `FERNET_KEY`.
- Keep encryption keys out of source control and configure them as deployment secrets.

### WebApp Authentication
- Telegram login data must have a valid signature and an `auth_date` no older than 24 hours.
- Each verified login payload can be used once; replay identifiers are stored in MongoDB and expire automatically.

### OTP Destroyer
- Provides OTP-related monitoring and protection workflows through the bot.
- Review the account and notification settings before enabling protection.

### Session Management
- View session information and use the available session-management controls.

---

## 🚢 Deployment

### Local Development

```bash
python main.py
```

### Production (Koyeb)

```bash
# Deploy using the Koyeb service configuration
koyeb deploy

# Or manual deployment
koyeb app create teleguard \
  --git github.com/MeherMankar/TeleGuard \
  --git-branch test \
  --env API_ID=xxx \
  --env API_HASH=xxx \
  --env BOT_TOKEN=xxx \
  --env MONGO_URI=xxx \
  --env JWT_SECRET=xxx \
  --env ALLOWED_ORIGINS=https://your-frontend-domain
```

Configure all required values as Koyeb **service environment variables**. The
manifest expects project-scoped values for `API_ID`, `API_HASH`, `BOT_TOKEN`,
`MONGO_URI`, `JWT_SECRET`, and `ALLOWED_ORIGINS`. Never use a placeholder
secret in a deployed service.

### Docker

```dockerfile
# Build image
docker build -t teleguard .

# Run container
docker run -d \
  --name teleguard \
  --env-file config/.env \
  -v $(pwd)/sessions:/app/sessions \
  -v $(pwd)/logs:/app/logs \
  teleguard
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `API_ID` | ✅ | Telegram API ID |
| `API_HASH` | ✅ | Telegram API Hash |
| `BOT_TOKEN` | ✅ | Bot token from @BotFather |
| `MONGO_URI` | ✅ | MongoDB connection string |
| `JWT_SECRET` | ✅ | Unique random signing key, at least 32 characters |
| `ALLOWED_ORIGINS` | ✅ in production | Comma-separated frontend origins allowed by backend CORS |
| `ADMIN_IDS` | Optional | Comma-separated admin user IDs |
| `MAX_ACCOUNTS` | Optional | Maximum accounts per user |
| `FERNET_KEY` | ❌ | Stable Fernet key; required for encrypted GitHub session backups |
| `SESSION_BACKUP_ENABLED` | ❌ | Set to `true` to back up account sessions to GitHub |
| `GITHUB_REPO` | ❌ | Private GitHub repository (`owner/repository`) |
| `GITHUB_TOKEN` | ❌ | Token with Contents read/write access to the private backup repository |
| `GITHUB_BACKUP_BRANCH` | ❌ | Backup branch (default: `backups`) |

GitHub is only a session-backup destination; MongoDB remains the live database.
When deploying on Koyeb, set these as **service environment variables**—GitHub
Actions repository secrets are not automatically passed to the running service.
Use a private repository and keep `FERNET_KEY` unchanged between deployments.
The `/health` endpoint is a readiness check: it returns HTTP 503 until MongoDB
is reachable and the bot has completed startup.

For a separately hosted frontend, set `VITE_API_URL` to the backend HTTPS URL
and `VITE_WS_URL` to the backend WSS URL in the frontend host's build
environment. Add the frontend's exact origin to backend `ALLOWED_ORIGINS`.

---

## 🛠️ Development

### Setup Development Environment

```bash
# Clone and setup
git clone https://github.com/mehermankar/teleguard.git
cd teleguard
python -m venv venv
source venv/bin/activate

# Install dev dependencies
pip install -r requirements.txt
pip install black flake8 pytest

# Setup pre-commit hooks
pre-commit install
```

### Code Style

```bash
# Format code
black teleguard/

# Lint code
flake8 teleguard/

# Type checking
mypy teleguard/
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=teleguard

# Run specific test
pytest tests/test_otp_manager.py
```

### Contributing

1. **Fork** the repository
2. **Create** feature branch: `git checkout -b feature/amazing-feature`
3. **Commit** changes: `git commit -m 'Add amazing feature'`
4. **Push** to branch: `git push origin feature/amazing-feature`
5. **Open** Pull Request

---
---

## 🤝 Support & Community

### Get Help

- 📧 **Email Support**: Contact via @ContactXYZrobot
- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/MeherMankar/TeleGuard/issues)
- 📚 **Documentation**: [Wiki](https://github.com/MeherMankar/TeleGuard/wiki)

---

## 👨‍💻 Credits

**Developed by:**
- [@MeherPatil](https://t.me/MeherPatil) - Lead Developer & Architecture
- [@Gutkesh](https://t.me/Gutkesh) - Core Developer & Security

**Special Thanks:**
- Telethon library developers
- MongoDB team
- Python community

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

```
MIT License

Copyright (c) 2024 TeleGuard

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction...
```

---

## ⚠️ Disclaimer

**Important Legal Notice:**

This tool is provided for **educational and research purposes only**. Users are responsible for:

- ✅ Complying with [Telegram's Terms of Service](https://telegram.org/tos)
- ✅ Respecting privacy laws and regulations
- ✅ Using the tool ethically and responsibly
- ✅ Not engaging in spam or abuse

**The developers are not responsible for misuse of this software.**

---

## 🗺️ Roadmap

### Version 2.1 (Q1 2024)
- [ ] Web dashboard interface
- [ ] Advanced analytics and reporting
- [ ] Multi-language support
- [ ] Scheduled messaging

### Version 2.2 (Q2 2024)
- [ ] AI-powered auto-reply
- [ ] Advanced spam detection
- [ ] Group management tools
- [ ] API for third-party integrations

---

## 📈 Changelog

### v2.0.1 (Current)
- 🔄 Universal session import (Telethon, Pyrogram, TData)
- 📦 Bulk session import from ZIP files
- 🐛 Fixed session conflict tracking bug
- ⚡ Performance optimization with account caching (60-80% faster)
- 🪟 Improved Windows console emoji handling
- ⏱️ Optimized timeout values for better reliability
- 🔧 Refactored session utilities (DRY principles)

### v2.0.0
- ✨ Complete codebase refactor (42% reduction)
- 🛡️ Enhanced OTP Destroyer with temp bypass
- 💬 Unified DM management system
- 🧹 Advanced cleanup tools

### v1.5.0
- 🎭 Activity simulator
- 📤 Session export/import
- 👥 Contact management
- 🔐 Enhanced 2FA management

### v1.0.0
- 🚀 Initial release
- 📱 Multi-account support
- 🛡️ Basic OTP protection
- 💬 Simple messaging tools

---

<div align="center">

**Made with ❤️ by the Meher**

[⭐ Star us on GitHub](https://github.com/mehermankar/teleguard) • [🐛 Report Bug](https://github.com/mehermankar/teleguard/issues) • [💡 Request Feature](https://github.com/mehermankar/teleguard/issues)

</div>
