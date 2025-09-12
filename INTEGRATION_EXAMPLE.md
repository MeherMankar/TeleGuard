# GitHub Database Integration Example

This file shows how to integrate the GitHub database into your existing TeleGuard application.

## 1. Update main.py

Add this code to your `main.py` to initialize the database:

```python
# Add these imports at the top
import os
from teleguard.github_db import GitHubJSONDB
from teleguard.local_db import LocalJSONDB

# Add this function to initialize database
def initialize_database():
    """Initialize database backend (GitHub or local)"""
    if os.getenv("USE_GITHUB_DB", "false").lower() == "true":
        print("📡 Initializing GitHub database...")

        # Validate required environment variables
        required_vars = ["DB_GITHUB_OWNER", "DB_GITHUB_REPO", "GITHUB_TOKEN"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]

        if missing_vars:
            print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
            print("💡 Set USE_GITHUB_DB=false to use local database instead")
            sys.exit(1)

        db = GitHubJSONDB(
            owner=os.getenv("DB_GITHUB_OWNER"),
            repo=os.getenv("DB_GITHUB_REPO"),
            token=os.getenv("GITHUB_TOKEN"),
            branch=os.getenv("DB_GITHUB_BRANCH", "db-live"),
            write_allowed=os.getenv("DB_WRITE_ALLOWED", "false").lower() == "true"
        )

        # Test connection
        try:
            rate_limit = db._get_rate_limit()
            print(f"✅ GitHub API connected! Rate limit: {rate_limit.remaining}/{rate_limit.limit}")
        except Exception as e:
            print(f"❌ GitHub API connection failed: {e}")
            sys.exit(1)

        return db
    else:
        print("📁 Using local database...")
        return LocalJSONDB(
            base_path=os.getenv("LOCAL_DB_PATH", "."),
            write_allowed=True
        )

# Add this to your main() function
async def main():
    # ... existing code ...

    # Initialize database
    global db
    db = initialize_database()

    # ... rest of your main function ...
```

## 2. Update User Settings Functions

Replace your existing user settings functions:

```python
# OLD: Direct file operations
def save_user_settings(user_id, settings):
    with open("db/user_settings.json", "w") as f:
        json.dump(settings, f)

def load_user_settings(user_id):
    try:
        with open("db/user_settings.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# NEW: Database abstraction
def save_user_settings(user_id: int, settings: dict):
    """Save user settings to database"""
    def update_settings(current_data):
        users = current_data.setdefault("users", {})
        users[str(user_id)] = {
            **settings,
            "updated_at": int(time.time())
        }
        return current_data

    try:
        db.safe_update_json(
            "db/user_settings.json",
            update_settings,
            f"Update settings for user {user_id}"
        )
        logger.info(f"✅ Saved settings for user {user_id}")
    except Exception as e:
        logger.error(f"❌ Failed to save settings for user {user_id}: {e}")
        raise

def load_user_settings(user_id: int) -> dict:
    """Load user settings from database"""
    try:
        data, _ = db.get_json("db/user_settings.json")
        users = data.get("users", {})
        return users.get(str(user_id), {})
    except Exception as e:
        logger.error(f"❌ Failed to load settings for user {user_id}: {e}")
        return {}
```

## 3. Update Account Management

```python
# NEW: Account management with GitHub database
def add_account(user_id: int, phone: str, session_data: dict):
    """Add account to database"""
    def update_accounts(current_data):
        accounts = current_data.setdefault("accounts", {})
        user_accounts = accounts.setdefault(str(user_id), {})

        user_accounts[phone] = {
            "phone": phone,
            "session_data": session_data,
            "added_at": int(time.time()),
            "status": "active"
        }
        return current_data

    # Use encryption for sensitive session data
    fernet = None
    if os.getenv("FERNET_KEY"):
        from cryptography.fernet import Fernet
        fernet = Fernet(os.getenv("FERNET_KEY").encode())

    try:
        db.safe_update_json(
            "db/accounts.json.enc" if fernet else "db/accounts.json",
            update_accounts,
            f"Add account {phone} for user {user_id}",
            encrypt_with_fernet=fernet
        )
        logger.info(f"✅ Added account {phone} for user {user_id}")
    except Exception as e:
        logger.error(f"❌ Failed to add account {phone}: {e}")
        raise

def get_user_accounts(user_id: int) -> dict:
    """Get all accounts for a user"""
    fernet = None
    if os.getenv("FERNET_KEY"):
        from cryptography.fernet import Fernet
        fernet = Fernet(os.getenv("FERNET_KEY").encode())

    try:
        data, _ = db.get_json(
            "db/accounts.json.enc" if fernet else "db/accounts.json",
            decrypt_with_fernet=fernet
        )
        accounts = data.get("accounts", {})
        return accounts.get(str(user_id), {})
    except Exception as e:
        logger.error(f"❌ Failed to load accounts for user {user_id}: {e}")
        return {}
```

## 4. Add Database Health Check

```python
async def check_database_health():
    """Check database connectivity and health"""
    try:
        if isinstance(db, GitHubJSONDB):
            # Check GitHub API rate limits
            rate_limit = db._get_rate_limit()

            if rate_limit.remaining < 100:
                logger.warning(f"⚠️ Low GitHub API rate limit: {rate_limit.remaining}/{rate_limit.limit}")
                return False

            # Test read operation
            _, _ = db.get_json("db/health_check.json")

            logger.info(f"✅ GitHub database healthy. Rate limit: {rate_limit.remaining}/{rate_limit.limit}")
            return True
        else:
            # Test local database
            test_path = Path(db.base_path) / "db"
            if not test_path.exists():
                test_path.mkdir(parents=True, exist_ok=True)

            logger.info("✅ Local database healthy")
            return True

    except Exception as e:
        logger.error(f"❌ Database health check failed: {e}")
        return False

# Add to your startup sequence
async def startup_checks():
    """Perform startup health checks"""
    logger.info("🔍 Performing startup checks...")

    # Check database health
    if not await check_database_health():
        logger.error("❌ Database health check failed")
        return False

    # ... other checks ...

    logger.info("✅ All startup checks passed")
    return True
```

## 5. Environment Configuration

Update your `.env` file:

```bash
# GitHub Database Configuration
USE_GITHUB_DB=true
DB_GITHUB_OWNER=MeherMankar
DB_GITHUB_REPO=TeleGuard
DB_GITHUB_BRANCH=db-live
GITHUB_TOKEN=ghp_your_token_here
DB_WRITE_ALLOWED=false  # Set to true when ready

# Optional: Encryption for sensitive data
FERNET_KEY=your_base64_fernet_key_here

# Fallback: Local database path
LOCAL_DB_PATH=.
```

## 6. Migration Script Usage

```bash
# 1. Test migration (dry run)
python scripts/migrate_local_db_to_github.py --dry-run

# 2. Run actual migration
export DB_WRITE_ALLOWED=true
python scripts/migrate_local_db_to_github.py

# 3. Verify migration
# Check: https://github.com/MeherMankar/TeleGuard/tree/db-live/db
```

## 7. Error Handling

Add comprehensive error handling:

```python
from teleguard.github_db import GitHubDBError, RateLimitError, ConflictError

async def safe_database_operation(operation_func, *args, **kwargs):
    """Safely execute database operation with error handling"""
    max_retries = 3

    for attempt in range(max_retries):
        try:
            return await operation_func(*args, **kwargs)

        except RateLimitError:
            logger.warning("⚠️ GitHub API rate limit exceeded, waiting...")
            await asyncio.sleep(60)  # Wait 1 minute

        except ConflictError:
            logger.warning("⚠️ Database conflict, retrying...")
            await asyncio.sleep(random.uniform(1, 3))  # Random backoff

        except GitHubDBError as e:
            logger.error(f"❌ Database error: {e}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)  # Exponential backoff

        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            raise

    raise GitHubDBError(f"Operation failed after {max_retries} attempts")
```

## 8. Monitoring and Alerts

```python
async def monitor_github_api():
    """Monitor GitHub API usage and send alerts"""
    if not isinstance(db, GitHubJSONDB):
        return

    try:
        rate_limit = db._get_rate_limit()

        # Alert if rate limit is low
        if rate_limit.remaining < 500:
            logger.warning(f"🚨 GitHub API rate limit low: {rate_limit.remaining}/{rate_limit.limit}")

            # Send alert to admin (implement your notification method)
            await send_admin_alert(
                f"GitHub API rate limit low: {rate_limit.remaining}/{rate_limit.limit}\n"
                f"Reset in: {rate_limit.reset_in_seconds} seconds"
            )

        # Log usage statistics
        usage_percent = ((rate_limit.limit - rate_limit.remaining) / rate_limit.limit) * 100
        logger.info(f"📊 GitHub API usage: {usage_percent:.1f}% ({rate_limit.remaining} remaining)")

    except Exception as e:
        logger.error(f"❌ Failed to monitor GitHub API: {e}")

# Schedule monitoring (add to your scheduler)
scheduler.add_job(
    monitor_github_api,
    'interval',
    minutes=15,  # Check every 15 minutes
    id='github_api_monitor'
)
```

This integration provides a robust, production-ready GitHub database backend for your TeleGuard application with proper error handling, monitoring, and fallback capabilities.
