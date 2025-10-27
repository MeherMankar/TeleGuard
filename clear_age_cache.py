"""Clear invalid age cache from database"""
import asyncio
from teleguard.core.mongo_database import mongodb

async def clear_cache():
    await mongodb.connect()
    result = await mongodb.db.accounts.update_many(
        {},
        {'$unset': {'age_days': '', 'creation_date': ''}}
    )
    print(f"Cleared age cache for {result.modified_count} accounts")

if __name__ == "__main__":
    asyncio.run(clear_cache())
