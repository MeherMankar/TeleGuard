# TeleGuard - Technology Stack

## Programming Language
- **Python 3.9+** (Target: Python 3.11)
- **Async/Await**: Extensive use of asyncio for concurrent operations
- **Type Hints**: Partial type annotations (mypy configuration present)

## Core Dependencies

### Telegram Libraries
- **telethon >= 1.41.2**: Primary Telegram client library for user accounts
- **pyrogram >= 2.0.106**: Alternative Telegram client (MTProto API)

### Database & Caching
- **pymongo >= 4.10.1**: MongoDB driver for data persistence
- **motor >= 3.6.0**: Async MongoDB driver
- **redis >= 5.2.0**: Redis client for caching and rate limiting

### Security & Encryption
- **cryptography >= 43.0.3**: Fernet encryption, AES-256 for sensitive data
- **python-dotenv == 1.0.1**: Environment variable management

### Web & Networking
- **aiohttp >= 3.11.10**: Async HTTP client/server for health checks
- **requests >= 2.32.3**: Synchronous HTTP client
- **aiohttp-socks >= 0.8.4**: SOCKS proxy support for aiohttp
- **pysocks >= 1.7.1**: SOCKS proxy support
- **aiodns >= 3.1.1**: Async DNS resolution

### Task Scheduling & Background Jobs
- **APScheduler == 3.11.0**: Advanced Python Scheduler for cron-like tasks

### System & Performance
- **psutil >= 6.1.0**: System and process monitoring
- **aiofiles >= 23.2.0**: Async file operations
- **uvloop >= 0.19.0**: Fast event loop (Unix/Linux/macOS only)
- **setproctitle >= 1.3.3**: Process title customization

## Development Tools

### Code Quality
- **black**: Code formatter (line-length: 88, target: py311)
- **flake8**: Linting (.flake8 configuration present)
- **mypy**: Static type checking (pyproject.toml configuration)
- **isort**: Import sorting (profile: black)

### Testing
- **pytest**: Test framework (pytest.ini configuration present)
- Test files in `tests/` directory

### Version Control
- **Git**: Version control with .gitignore
- **pre-commit**: Pre-commit hooks (.pre-commit-config.yaml)

## Build & Deployment

### Package Management
- **pip**: Python package installer
- **requirements.txt**: Dependency specification
- **pyproject.toml**: Modern Python project configuration

### Containerization
- **Docker**: Containerization support
  - `Dockerfile`: Container image definition
  - `docker-compose.yml`: Multi-container orchestration
  - `.dockerignore`: Docker build exclusions

### Cloud Platforms
- **Koyeb**: Primary cloud deployment platform
  - `koyeb.toml`: Koyeb configuration
  - `.koyeb/app.yaml`: App configuration
  - `app.json`: App metadata
  - `Procfile`: Process definition
  - `runtime.txt`: Python runtime specification

### CI/CD
- **GitHub Actions**: Automated workflows
  - `.github/workflows/quality.yml`: Code quality checks

## Configuration Management

### Environment Variables
- `.env`: Local development configuration (not in version control)
- `.env.example`: Example configuration template
- `.env.production`: Production configuration template
- `config/secret.key`: Encryption key storage

### Required Environment Variables
```
API_ID=<telegram_api_id>
API_HASH=<telegram_api_hash>
BOT_TOKEN=<bot_token>
MONGO_URI=<mongodb_connection_string>
DB_NAME=<database_name>
ENCRYPTION_KEY=<32_byte_encryption_key>
ADMIN_IDS=<comma_separated_admin_ids>
```

### Optional Environment Variables
```
MAX_ACCOUNTS=10
SESSION_BACKUP_ENABLED=true
PORT=8000
KOYEB_OPTIMIZATION_ENABLED=true
```

## Logging & Monitoring

### Logging Configuration
- **Structured Logging**: Custom logger with JSON-like format
- **Log Rotation**: RotatingFileHandler (10MB max, 5 backups)
- **Log Levels**: INFO for application, ERROR for external libraries
- **Log Files**: `logs/teleguard.log`, `logs/session_guardian.log`
- **Console Output**: Safe console handler with emoji replacement for Windows

### Health Monitoring
- **Health Check Server**: aiohttp web server on port 8000
- **Endpoints**:
  - `/health`: General health status
  - `/ip`: IP monitoring status
  - `/`: Root endpoint (health check)

### Metrics
- OTP protection metrics
- Messaging statistics
- Session health monitoring
- IP change tracking

## Database Schema

### MongoDB Collections
- **accounts**: User account information
- **sessions**: Session metadata
- **settings**: User preferences and configuration
- **messages**: Message history and templates
- **contacts**: Contact information
- **otp_logs**: OTP protection logs
- **analytics**: Usage analytics

### Redis Keys
- Session cache
- Rate limiting counters
- Temporary data storage

## Development Commands

### Setup
```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Unix/Linux/macOS)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Running
```bash
# Start bot
python main.py

# Run with specific Python version
python3.11 main.py
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

### Code Quality
```bash
# Format code
black teleguard/

# Lint code
flake8 teleguard/

# Type checking
mypy teleguard/

# Sort imports
isort teleguard/
```

### Docker
```bash
# Build image
docker build -t teleguard .

# Run container
docker run -d --name teleguard --env-file config/.env teleguard

# Docker Compose
docker-compose up -d
```

### Deployment
```bash
# Koyeb deployment
koyeb deploy

# Manual Koyeb
koyeb app create teleguard \
  --git github.com/yourusername/teleguard \
  --git-branch main \
  --env API_ID=xxx \
  --env API_HASH=xxx \
  --env BOT_TOKEN=xxx
```

## Platform Compatibility

### Operating Systems
- **Windows**: Full support with safe console handler
- **Linux**: Full support with uvloop optimization
- **macOS**: Full support with uvloop optimization

### Python Versions
- **Minimum**: Python 3.9
- **Recommended**: Python 3.11
- **Target**: Python 3.11 (pyproject.toml)

### Cloud Platforms
- **Koyeb**: Optimized with koyeb_optimizer
- **Docker**: Full containerization support
- **Heroku**: Compatible (Procfile present)
- **Local**: Direct execution support

## Performance Optimizations

### Async Operations
- Extensive use of asyncio for I/O-bound operations
- Concurrent client management
- Background task queue with retry mechanisms

### Caching
- Redis caching layer for frequently accessed data
- Cache decorators for function memoization
- Session caching for quick access

### Connection Pooling
- Client manager with connection pooling
- Reusable Telethon clients
- Automatic reconnection on failure

### Platform-Specific
- **Koyeb Optimizer**: Startup optimization for Koyeb platform
- **uvloop**: Fast event loop for Unix-like systems
- **Health Server**: Multiple port fallback for reliability

## Security Features

### Encryption
- **Fernet**: Symmetric encryption for sensitive data
- **Double Encryption**: Session strings encrypted twice
- **AES-256**: Two-factor authentication password storage

### Session Protection
- **OTP Destroyer**: Real-time login code invalidation
- **Session Guardian**: Active session monitoring
- **IP Tracking**: IP change detection and alerts

### Input Validation
- Validators for user input
- Rate limiting for API calls
- Authorization checks for admin commands

## External APIs

### Telegram API
- **API ID & Hash**: Required from https://my.telegram.org
- **Bot Token**: Required from @BotFather
- **MTProto Protocol**: Direct Telegram API access

### Database Services
- **MongoDB**: Document database (local or cloud)
- **Redis**: In-memory cache (local or cloud)

## File Storage

### Session Files
- Location: `sessions/` directory
- Format: SQLite database files (`.session`)
- Naming: `teleguard_bot_<user_id>.session`

### Log Files
- Location: `logs/` directory
- Format: Plain text with structured format
- Rotation: 10MB max, 5 backup files

### Configuration Files
- Location: `config/` directory
- Format: `.env` files (key=value pairs)
- Security: Not committed to version control
