"""Set manual account ages"""
import asyncio
from datetime import datetime, timezone
from teleguard.core.mongo_database import mongodb

async def set_ages():
    await mongodb.connect()
    
    # Meher account - created in 2023 (assume January 1, 2023)
    meher_creation = datetime(2023, 1, 1, tzinfo=timezone.utc)
    meher_age = (datetime.now(timezone.utc) - meher_creation).days
    
    # Saja account - created November 2024 (assume November 1, 2024)
    saja_creation = datetime(2024, 11, 1, tzinfo=timezone.utc)
    saja_age = (datetime.now(timezone.utc) - saja_creation).days
    
    # Update Meher
    result1 = await mongodb.db.accounts.update_one(
        {'phone': '+918459770125'},
        {'$set': {
            'creation_date': meher_creation,
            'age_days': meher_age,
            'last_age_update': datetime.now(timezone.utc)
        }}
    )
    print(f"Updated Meher: {meher_age} days ({meher_age//365}y {(meher_age%365)//30}m)")
    
    # Update Saja
    result2 = await mongodb.db.accounts.update_one(
        {'phone': '+998332796916'},
        {'$set': {
            'creation_date': saja_creation,
            'age_days': saja_age,
            'last_age_update': datetime.now(timezone.utc)
        }}
    )
    print(f"Updated Saja: {saja_age} days ({saja_age//365}y {(saja_age%365)//30}m)")
    
    # MongoDB connection will close automatically

if __name__ == "__main__":
    asyncio.run(set_ages())
