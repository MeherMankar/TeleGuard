"""Migration script for session backup system"""

import asyncio
import logging

from database import get_session
from models import Account
from mongo_store import init_mongo_indexes
from session_backup import SessionBackupManager
from sqlalchemy import select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_existing_sessions():
    """Migrate existing sessions from SQLite to MongoDB backup system"""

    try:
        # Initialize MongoDB indexes
        logger.info("Initializing MongoDB indexes...")
        init_mongo_indexes()

        # Initialize session backup manager
        backup_manager = SessionBackupManager()

        # Get all existing accounts
        async with get_session() as session:
            result = await session.execute(
                select(Account).where(Account.is_active == True)
            )
            accounts = result.scalars().all()

            if not accounts:
                logger.info("No accounts found to migrate")
                return

            logger.info(f"Found {len(accounts)} accounts to migrate")

            migrated_count = 0
            for account in accounts:
                try:
                    # Decrypt existing session
                    session_string = account.decrypt_session()

                    # Store in MongoDB backup system
                    backup_manager.store_session(account.phone, session_string)

                    logger.info(
                        f"Migrated session for account {account.name} ({account.phone})"
                    )
                    migrated_count += 1

                except Exception as e:
                    logger.error(f"Failed to migrate account {account.name}: {e}")

            logger.info(
                f"Migration completed: {migrated_count}/{len(accounts)} accounts migrated"
            )

            if migrated_count > 0:
                logger.info(
                    "Sessions are now stored in MongoDB and will be backed up to GitHub on next scheduled run"
                )
                logger.info("Use /backup_now command to trigger immediate backup")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


async def verify_migration():
    """Verify migration was successful"""

    try:
        from mongo_store import sessions_temp

        # Count sessions in MongoDB
        mongo_count = sessions_temp.count_documents({})

        # Count active accounts in SQLite
        async with get_session() as session:
            result = await session.execute(
                select(Account).where(Account.is_active == True)
            )
            accounts = result.scalars().all()
            sqlite_count = len(accounts)

        logger.info(
            f"Verification: {sqlite_count} accounts in SQLite, {mongo_count} sessions in MongoDB"
        )

        if mongo_count >= sqlite_count:
            logger.info("✅ Migration verification successful")
            return True
        else:
            logger.warning("⚠️ Migration may be incomplete")
            return False

    except Exception as e:
        logger.error(f"Verification failed: {e}")
        return False


async def main():
    """Main migration function"""

    print("🔄 Session Backup Migration Tool")
    print("=" * 40)

    # Check environment
    import os

    required_vars = ["MONGO_URI", "GITHUB_REPO"]
    missing_vars = [var for var in required_vars if not os.environ.get(var)]

    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("Please configure these variables before running migration")
        return

    print("✅ Environment variables configured")

    # Run migration
    print("\n🔄 Starting migration...")
    await migrate_existing_sessions()

    # Verify migration
    print("\n🔍 Verifying migration...")
    success = await verify_migration()

    if success:
        print("\n✅ Migration completed successfully!")
        print("\nNext steps:")
        print("1. Set SESSION_BACKUP_ENABLED=true in your environment")
        print("2. Restart the bot to enable scheduled backups")
        print("3. Use /backup_now to trigger immediate backup")
        print("4. Use /verify_session <account_id> to verify backups")
    else:
        print("\n⚠️ Migration completed with warnings")
        print("Please check the logs and verify your configuration")


if __name__ == "__main__":
    asyncio.run(main())
