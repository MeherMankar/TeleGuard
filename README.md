# 🛡️ TeleGuard

> Professional Telegram account manager with security automation, OTP protection, and a web dashboard.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Telegram](https://img.shields.io/badge/Support-@MeherPatil-blue.svg)](https://t.me/MeherPatil)

---

## ✨ Features

### 🔐 Security
- **OTP Destroyer** — intercepts and invalidates unauthorized login codes in real time
- **Session Vault** — automatically creates a second independent backup session for every account; if Telegram invalidates the main session the bot silently restores from the vault without losing the account
- **2FA Management** — stores and auto-applies 2FA passwords for all bot-initiated re-auth flows
- **Session Guardian** — monitors IP changes and handles AUTH_KEY_DUPLICATED during rolling deployments silently
- **Proxy Support** — MTProto / SOCKS5 / HTTP proxies per account

### 📱 Account Management
- Multi-account support
- Phone-number login with auto-OTP fetch (reads OTP from connected accounts automatically)
- Session import — Telethon string, .session file, Pyrogram, TData, ZIP bulk import
- Session export — string or .session file with DC information
- Profile manager — name, username, bio, photo
- Backup & restore — current-session export or fresh re-authenticated backup

### 💬 Messaging
- Unified DM inbox via forum topics (all accounts in one group)
- Auto-reply with keyword triggers
- Bulk messaging and message templates
- Scheduled messages
- DM topic management — block, unblock, clear history

### 📢 Channels & Groups
- Join, leave, create, delete channels and groups
- Bulk join/leave across accounts
- Topic and forum management

### 🧹 Cleanup
- Smart chat cleanup — personal, bot, and spam chats
- Mass exit from channels/groups
- Account audit log

### 🎭 Automation
- Activity simulator
- Online maker (keep accounts online)
- Contact export to CSV

---

## 🚀 Quick Start

### Requirements

- Python 3.11+
- MongoDB 4.4+
- Telegram API credentials from [my.telegram.org](https://my.telegram.org)

### Installation

```bash
git clone https://github.com/MeherMankar/TeleGuard.git
cd TeleGuard
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
cp config/.env.example config/.env
```

### Configuration

Edit `config/.env`:

```env
# Required
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
MONGO_URI=mongodb://localhost:27017
JWT_SECRET=at_least_32_random_characters
FERNET_KEY=generate_with_command_below
ALLOWED_ORIGINS=http://localhost:5173

# Optional — admin user IDs (comma-separated Telegram user IDs)
ADMIN_IDS=123456789

# Optional — session backup to a private GitHub repo
SESSION_BACKUP_ENABLED=false
SESSION_BACKUP_GITHUB_REPO=owner/private-repo
SESSION_BACKUP_GITHUB_TOKEN=ghp_...

# Optional — encrypted MongoDB mirror to a public GitHub repo
GITHUB_DATA_MIRROR_ENABLED=false
GITHUB_DATA_REPO=owner/public-repo
GITHUB_DATA_TOKEN=ghp_...
```

Generate the required secrets:

```bash
# JWT_SECRET
python -c "import secrets; print(secrets.token_urlsafe(48))"

# FERNET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Run

```bash
python main.py
```

---

## 📖 Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Open the main menu |
| `/menu` | Re-open the main menu |
| `/add` | Add a Telegram account via phone login |
| `/accs` | List all managed accounts |
| `/cancel` | Cancel any pending operation |
| `/appeal` | Start the automated spam-restriction appeal flow |

---

## 🔑 Adding Your First Account

**Phone login (recommended)**
1. Send `/add` and enter your phone number with country code: `+1234567890`
2. The bot auto-fetches the OTP from your existing connected accounts — no manual entry needed in most cases
3. If 2FA is enabled the bot uses your stored password, or asks you once and stores it for all future operations

**Session import**
1. Open **📱 Account Settings → Session Login**
2. Choose: session string, .session file, Pyrogram string, TData folder, or ZIP bulk import
3. The bot detects the format and converts automatically

---

## 🛡️ OTP Destroyer

Monitors incoming login-code messages on your accounts and invalidates unauthorized codes before an attacker can use them.

- Enable per-account from **📱 Account Settings → OTP Destroyer**
- The destroyer is automatically paused during any bot-internal operation (login, backup, vault creation) so it never blocks legitimate bot flows
- Temp bypass available for 5-minute windows when you need to log in yourself

---

## 💾 Session Vault (Auto-Recovery)

When you add an account the bot creates a second independent session in the background:

- **Primary vault** → MongoDB (always written first)
- **Secondary vault** → GitHub private repo (written after, best-effort)

If Telegram invalidates your main session:
1. Bot detects the invalidation
2. Loads the vault session and promotes it to main
3. Reconnects the account silently
4. Notifies you: *"Account auto-recovered from vault"*
5. Creates a new vault session in the background so the vault is never empty

User-initiated account removal deletes both vaults. Telegram-initiated invalidation never touches the vault.

---

## 🚢 Deployment

### Docker

```bash
docker build -t teleguard .
docker run -d --name teleguard --env-file config/.env teleguard
```

### Koyeb

The `.koyeb/app.yaml` manifest is included. Set all required variables as project-scoped environment variables in the Koyeb dashboard:

`API_ID` · `API_HASH` · `BOT_TOKEN` · `MONGO_URI` · `JWT_SECRET` · `FERNET_KEY` · `ALLOWED_ORIGINS`

The `/health` endpoint returns HTTP 503 until MongoDB is reachable and the bot has finished startup — Koyeb uses this for the health check grace period.

### Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `API_ID` | ✅ | Telegram API ID |
| `API_HASH` | ✅ | Telegram API Hash |
| `BOT_TOKEN` | ✅ | Bot token from @BotFather |
| `MONGO_URI` | ✅ | MongoDB connection string |
| `JWT_SECRET` | ✅ | Random signing key, min 32 chars |
| `FERNET_KEY` | ✅ | Stable Fernet key for encryption |
| `ALLOWED_ORIGINS` | ✅ | Comma-separated frontend origins |
| `ADMIN_IDS` | Optional | Comma-separated Telegram user IDs |
| `SESSION_BACKUP_ENABLED` | Optional | `true` to enable GitHub session backup |
| `SESSION_BACKUP_GITHUB_REPO` | Optional | Private repo for session backup |
| `SESSION_BACKUP_GITHUB_TOKEN` | Optional | Token with Contents read/write |
| `GITHUB_DATA_MIRROR_ENABLED` | Optional | `true` to mirror MongoDB to GitHub |
| `GITHUB_DATA_REPO` | Optional | Public repo for encrypted data mirror |
| `GITHUB_DATA_TOKEN` | Optional | Token with Contents read/write |

Keep `FERNET_KEY` unchanged between deployments — changing it makes existing encrypted backups unreadable.

---

## 🛠️ Development

```bash
pip install -r requirements.txt
pre-commit install

# Format
black teleguard/

# Lint
flake8 teleguard/

# Tests
pytest
```

---

## 🤝 Support

- Telegram: [@MeherPatil](https://t.me/MeherPatil)
- Support bot: [@ContactXYZrobot](https://t.me/ContactXYZrobot)
- Issues: [GitHub Issues](https://github.com/MeherMankar/TeleGuard/issues)

---

## 👨‍💻 Credits

**Developed by:**
- [@MeherPatil](https://t.me/MeherPatil) — Lead Developer
- [@Gutkesh](https://t.me/Gutkesh) — Core Developer

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## ⚠️ Disclaimer

This software is provided for educational and personal use. Users are responsible for complying with [Telegram's Terms of Service](https://telegram.org/tos) and all applicable laws. The developers are not responsible for misuse.
