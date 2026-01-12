# TeleGuard - Project Structure

## Directory Organization

```
teleguard/
├── teleguard/              # Core application package
│   ├── core/              # Business logic and core services
│   ├── handlers/          # Event handlers and command processors
│   ├── services/          # Service layer components
│   ├── sync/              # Synchronization utilities
│   ├── utils/             # Utility functions and helpers
│   └── workers/           # Background workers and automation
│
├── config/                # Configuration files
├── sessions/              # Telegram session storage
├── logs/                  # Application logs
├── tests/                 # Test suite
└── main.py               # Application entry point
```

## Core Components (`teleguard/core/`)

### Account & Client Management
- **bot_manager.py**: Main bot orchestration and account management logic
- **client_manager.py**: Telethon client lifecycle management and connection pooling
- **account_cleaner.py**: Account cleanup operations (chats, channels, groups)

### Security & Protection
- **otp_manager.py**: OTP Destroyer orchestration and management
- **otp_destroyer.py**: Real-time login code invalidation engine
- **session_guardian.py**: Session monitoring and IP tracking
- **session_health.py**: Session health checks and validation
- **device_snooper.py**: Device and session information extraction

### Data Management
- **mongo_database.py**: MongoDB operations and schema management
- **database_manager.py**: Unified database interface (MongoDB + Redis)
- **redis_cache.py**: Redis caching layer for performance
- **contact_db.py**: Contact database operations
- **contact_models.py**: Contact data models and schemas
- **contact_sync.py**: Contact synchronization across accounts

### Infrastructure
- **config.py**: Configuration loading and validation
- **constants.py**: Application-wide constants and enums
- **models.py**: Core data models and schemas
- **exceptions.py**: Custom exception classes
- **task_queue.py**: Background task queue with retry mechanisms
- **rate_limiter.py**: Rate limiting for API calls
- **proxy_manager.py**: Proxy configuration and management
- **mtproto_bridge.py**: MTProto proxy bridge for Telethon
- **automation.py**: Automation utilities and helpers
- **messaging.py**: Messaging operations and utilities

## Handlers (`teleguard/handlers/`)

### Command Handlers
- **command_handlers.py**: Main command dispatcher and routing
- **start_handler.py**: /start command and bot initialization
- **help_handler.py**: /help command and documentation
- **otp_commands.py**: OTP-related commands
- **twofa_commands.py**: 2FA management commands
- **simulation_commands.py**: Activity simulation commands
- **rate_limit_commands.py**: Rate limiting commands
- **developer_commands.py**: Developer/admin commands

### Menu System
- **menu_system.py**: Inline keyboard menu orchestration and navigation
- **menu_callbacks/**: Callback query handlers for menu interactions
- **menu_modules/**: Modular menu components

### Feature Handlers
- **auth_handler.py**: Account authentication and login
- **session_login_handler.py**: Session-based login
- **session_export_handler.py**: Session export functionality
- **session_import_handler.py**: Session import functionality
- **session_operations_handler.py**: Session operations (list, terminate)
- **sessions_handler.py**: Session management interface

### Messaging Handlers
- **unified_messaging.py**: Unified DM management system
- **dm_reply_handler.py**: Direct message reply handling
- **dm_reply_commands.py**: DM reply commands
- **topic_dm_handler.py**: Forum topic-based DM organization
- **topic_actions_handler.py**: Topic actions (create, delete, manage)
- **bulk_sender.py**: Bulk message sending
- **auto_reply_handler.py**: Auto-reply system
- **template_handler.py**: Message template management
- **scheduled_messaging.py**: Scheduled message sending

### Channel & Group Management
- **channel_manager.py**: Channel operations (join, leave, create)
- **group_manager.py**: Group management operations
- **chat_import_handler.py**: Chat import functionality

### Contact Management
- **contact_handler.py**: Contact operations
- **contact_export_handler.py**: Contact export to CSV
- **contact_share_handler.py**: Contact sharing between accounts

### Security & Admin
- **secure_2fa_handlers.py**: Secure 2FA password management
- **otp_password_handler.py**: OTP password handling
- **security_dashboard.py**: Security monitoring dashboard
- **device_handler.py**: Device management interface
- **proxy_handler.py**: Proxy configuration interface

### Cleanup & Maintenance
- **spam_appeal_handler.py**: Spam restriction appeals
- **spam_filters_handler.py**: Spam detection and filtering
- **advanced_spam_handler.py**: Advanced spam management

### Analytics & Monitoring
- **analytics_dashboard.py**: Analytics and metrics dashboard
- **backup_restore.py**: Backup and restore functionality
- **account_sync.py**: Account synchronization
- **transfer_ownership_handler.py**: Account ownership transfer

### Automation
- **online_maker.py**: Keep accounts online
- **simulation_handlers.py**: Activity simulation handlers

## Services (`teleguard/services/`)
- **channel_search.py**: Channel search functionality
- **messaging_stats.py**: Messaging statistics and analytics
- **otp_metrics.py**: OTP protection metrics

## Synchronization (`teleguard/sync/`)
- **crypto.py**: Cryptographic operations for sync
- **db.py**: Database operations for sync
- **scheduler.py**: Scheduled synchronization tasks

## Utilities (`teleguard/utils/`)

### Security & Encryption
- **crypto_utils.py**: Cryptographic utilities (Fernet encryption)
- **data_encryption.py**: Data encryption/decryption helpers
- **secure_password.py**: Secure password handling
- **security.py**: General security utilities
- **security_monitor.py**: Security monitoring and alerts
- **api_security.py**: API security and validation
- **session_protection.py**: Session protection mechanisms

### Session Management
- **session_manager.py**: Session lifecycle management
- **session_backup.py**: Session backup and restore
- **session_utils.py**: Session utility functions
- **session_scheduler.py**: Session scheduling operations

### Authentication & Authorization
- **auth_helpers.py**: Authentication helper functions
- **authorization.py**: Authorization and permission checks

### Error Handling & Logging
- **logger.py**: Structured logging with rotation
- **error_handler.py**: Global error handling
- **error_messages.py**: Error message templates

### Helpers & Utilities
- **account_helpers.py**: Account operation helpers
- **account_invalidation.py**: Account invalidation logic
- **activity_logger.py**: Activity logging
- **network_helpers.py**: Network utility functions
- **protected_client.py**: Protected Telethon client wrapper
- **validators.py**: Input validation functions
- **response_formatter.py**: Response formatting utilities
- **twofa_helper.py**: 2FA helper functions
- **spam_detector.py**: Spam detection algorithms
- **backups.py**: Backup utilities
- **cache_decorators.py**: Caching decorators
- **command_registry.py**: Command registration system
- **i18n.py**: Internationalization support

### Platform-Specific
- **health_server.py**: Health check web server
- **koyeb_optimizer.py**: Koyeb platform optimizations
- **startup_optimizer.py**: Startup optimization utilities
- **guardian_config.py**: Session guardian configuration

### Rate Limiting
- **rate_limiter.py**: Rate limiting implementation

## Workers (`teleguard/workers/`)
- **activity_simulator.py**: Human-like activity simulation
- **automation_worker.py**: Background automation tasks
- **online_maker_worker.py**: Keep accounts online worker
- **session_monitor.py**: Session monitoring worker

## Configuration (`config/`)
- **.env**: Environment variables (not in version control)
- **.env.example**: Example environment configuration
- **.env.production**: Production environment template
- **secret.key**: Encryption key storage

## Tests (`tests/`)
- **test_otp_manager.py**: OTP manager tests
- **test_encryption.py**: Encryption tests
- **test_session_manager.py**: Session manager tests
- **test_analytics_dashboard.py**: Analytics tests
- **test_backup_restore.py**: Backup/restore tests
- **test_group_manager.py**: Group manager tests
- **test_i18n.py**: Internationalization tests
- **test_scheduled_messaging.py**: Scheduled messaging tests
- **test_zip_import.py**: ZIP import tests

## Architectural Patterns

### Layered Architecture
1. **Entry Point** (main.py): Application initialization and orchestration
2. **Core Layer** (core/): Business logic and domain models
3. **Handler Layer** (handlers/): User interaction and command processing
4. **Service Layer** (services/): Reusable business services
5. **Utility Layer** (utils/): Cross-cutting concerns and helpers
6. **Worker Layer** (workers/): Background processing and automation

### Key Design Patterns
- **Manager Pattern**: ClientManager, BotManager for resource lifecycle
- **Factory Pattern**: Client creation and configuration
- **Observer Pattern**: Event handlers and callbacks
- **Strategy Pattern**: Different authentication strategies
- **Singleton Pattern**: Global task queue, database connections
- **Decorator Pattern**: Cache decorators, rate limiting
- **Repository Pattern**: Database operations abstraction

### Data Flow
1. User sends command via Telegram
2. Command handler receives and validates input
3. Handler delegates to core business logic
4. Core interacts with database/cache/external APIs
5. Response formatted and sent back to user
6. Background workers handle async tasks

### Session Management
- Sessions stored in `sessions/` directory as SQLite files
- Session strings encrypted with Fernet (double encryption)
- Session health monitored by session_guardian
- Automatic reconnection on connection loss
- IP change detection and monitoring

### Database Architecture
- **MongoDB**: Primary data store for accounts, settings, messages
- **Redis**: Caching layer for performance optimization
- **SQLite**: Telegram session storage (Telethon requirement)

### Security Layers
1. **Transport Security**: Proxy support (MTProto/SOCKS5/HTTP)
2. **Data Security**: Fernet encryption for sensitive data
3. **Session Security**: Double-encrypted session strings
4. **Access Security**: OTP Destroyer, Session Guardian
5. **Application Security**: Rate limiting, input validation
