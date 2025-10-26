"""Load anchor data into MongoDB for production use"""
import asyncio
from teleguard.core.mongo_database import mongodb, init_db

async def load_anchors():
    """Load ID range anchors into MongoDB"""
    await init_db()
    
    # Clear existing anchors
    await mongodb.db.id_anchors.delete_many({})
    
    # Anchor data from AccountAgeEstimator
    anchors = [
        {"start_id": 1, "end_id": 10000, "date": "2013-08-14T00:00:00Z"},
        {"start_id": 10001, "end_id": 25000, "date": "2013-08-25T00:00:00Z"},
        {"start_id": 25001, "end_id": 50000, "date": "2013-09-05T00:00:00Z"},
        {"start_id": 50001, "end_id": 75000, "date": "2013-09-15T00:00:00Z"},
        {"start_id": 75001, "end_id": 100000, "date": "2013-09-25T00:00:00Z"},
        {"start_id": 100001, "end_id": 150000, "date": "2013-10-10T00:00:00Z"},
        {"start_id": 150001, "end_id": 200000, "date": "2013-10-25T00:00:00Z"},
        {"start_id": 200001, "end_id": 300000, "date": "2013-11-10T00:00:00Z"},
        {"start_id": 300001, "end_id": 400000, "date": "2013-11-25T00:00:00Z"},
        {"start_id": 400001, "end_id": 550000, "date": "2013-12-10T00:00:00Z"},
        {"start_id": 550001, "end_id": 700000, "date": "2013-12-25T00:00:00Z"},
        {"start_id": 700001, "end_id": 850000, "date": "2014-01-10T00:00:00Z"},
        {"start_id": 850001, "end_id": 1000000, "date": "2014-01-25T00:00:00Z"},
        {"start_id": 1000001, "end_id": 1250000, "date": "2014-02-15T00:00:00Z"},
        {"start_id": 1250001, "end_id": 1500000, "date": "2014-03-15T00:00:00Z"},
        {"start_id": 1500001, "end_id": 1750000, "date": "2014-04-15T00:00:00Z"},
        {"start_id": 1750001, "end_id": 2000000, "date": "2014-05-15T00:00:00Z"},
        {"start_id": 2000001, "end_id": 2500000, "date": "2014-07-01T00:00:00Z"},
        {"start_id": 2500001, "end_id": 3000000, "date": "2014-08-15T00:00:00Z"},
        {"start_id": 3000001, "end_id": 3500000, "date": "2014-10-01T00:00:00Z"},
        {"start_id": 3500001, "end_id": 4000000, "date": "2014-11-15T00:00:00Z"},
        {"start_id": 4000001, "end_id": 4500000, "date": "2015-01-01T00:00:00Z"},
        {"start_id": 4500001, "end_id": 5000000, "date": "2015-02-15T00:00:00Z"},
        {"start_id": 5000001, "end_id": 6000000, "date": "2015-04-01T00:00:00Z"},
        {"start_id": 6000001, "end_id": 7000000, "date": "2015-06-01T00:00:00Z"},
        {"start_id": 7000001, "end_id": 8500000, "date": "2015-08-01T00:00:00Z"},
        {"start_id": 8500001, "end_id": 10000000, "date": "2015-10-01T00:00:00Z"},
        {"start_id": 10000001, "end_id": 12500000, "date": "2016-01-01T00:00:00Z"},
        {"start_id": 12500001, "end_id": 15000000, "date": "2016-03-01T00:00:00Z"},
        {"start_id": 15000001, "end_id": 17500000, "date": "2016-05-01T00:00:00Z"},
        {"start_id": 17500001, "end_id": 20000000, "date": "2016-07-01T00:00:00Z"},
        {"start_id": 20000001, "end_id": 22500000, "date": "2016-09-01T00:00:00Z"},
        {"start_id": 22500001, "end_id": 25000000, "date": "2016-11-01T00:00:00Z"},
        {"start_id": 25000001, "end_id": 27500000, "date": "2017-01-01T00:00:00Z"},
        {"start_id": 27500001, "end_id": 30000000, "date": "2017-03-01T00:00:00Z"},
        {"start_id": 30000001, "end_id": 35000000, "date": "2017-05-01T00:00:00Z"},
        {"start_id": 35000001, "end_id": 40000000, "date": "2017-07-01T00:00:00Z"},
        {"start_id": 40000001, "end_id": 45000000, "date": "2017-09-01T00:00:00Z"},
        {"start_id": 45000001, "end_id": 50000000, "date": "2017-11-01T00:00:00Z"},
        {"start_id": 50000001, "end_id": 55000000, "date": "2018-01-01T00:00:00Z"},
        {"start_id": 55000001, "end_id": 60000000, "date": "2018-03-01T00:00:00Z"},
        {"start_id": 60000001, "end_id": 70000000, "date": "2018-05-01T00:00:00Z"},
        {"start_id": 70000001, "end_id": 80000000, "date": "2018-07-01T00:00:00Z"},
        {"start_id": 80000001, "end_id": 90000000, "date": "2018-09-01T00:00:00Z"},
        {"start_id": 90000001, "end_id": 100000000, "date": "2018-11-01T00:00:00Z"},
        {"start_id": 100000001, "end_id": 110000000, "date": "2019-01-01T00:00:00Z"},
        {"start_id": 110000001, "end_id": 130000000, "date": "2019-03-01T00:00:00Z"},
        {"start_id": 130000001, "end_id": 150000000, "date": "2019-05-01T00:00:00Z"},
        {"start_id": 150000001, "end_id": 170000000, "date": "2019-07-01T00:00:00Z"},
        {"start_id": 170000001, "end_id": 190000000, "date": "2019-09-01T00:00:00Z"},
        {"start_id": 190000001, "end_id": 210000000, "date": "2019-11-01T00:00:00Z"},
        {"start_id": 210000001, "end_id": 240000000, "date": "2020-01-01T00:00:00Z"},
        {"start_id": 240000001, "end_id": 270000000, "date": "2020-03-01T00:00:00Z"},
        {"start_id": 270000001, "end_id": 300000000, "date": "2020-05-01T00:00:00Z"},
        {"start_id": 300000001, "end_id": 330000000, "date": "2020-07-01T00:00:00Z"},
        {"start_id": 330000001, "end_id": 360000000, "date": "2020-09-01T00:00:00Z"},
        {"start_id": 360000001, "end_id": 390000000, "date": "2020-11-01T00:00:00Z"},
        {"start_id": 390000001, "end_id": 425000000, "date": "2021-01-01T00:00:00Z"},
        {"start_id": 425000001, "end_id": 460000000, "date": "2021-03-01T00:00:00Z"},
        {"start_id": 460000001, "end_id": 500000000, "date": "2021-05-01T00:00:00Z"},
        {"start_id": 500000001, "end_id": 540000000, "date": "2021-07-01T00:00:00Z"},
        {"start_id": 540000001, "end_id": 580000000, "date": "2021-09-01T00:00:00Z"},
        {"start_id": 580000001, "end_id": 620000000, "date": "2021-11-01T00:00:00Z"},
        {"start_id": 620000001, "end_id": 670000000, "date": "2022-01-01T00:00:00Z"},
        {"start_id": 670000001, "end_id": 720000000, "date": "2022-03-01T00:00:00Z"},
        {"start_id": 720000001, "end_id": 780000000, "date": "2022-05-01T00:00:00Z"},
        {"start_id": 780000001, "end_id": 840000000, "date": "2022-07-01T00:00:00Z"},
        {"start_id": 840000001, "end_id": 900000000, "date": "2022-09-01T00:00:00Z"},
        {"start_id": 900000001, "end_id": 970000000, "date": "2022-11-01T00:00:00Z"},
        {"start_id": 970000001, "end_id": 1040000000, "date": "2023-01-01T00:00:00Z"},
        {"start_id": 1040000001, "end_id": 1120000000, "date": "2023-03-01T00:00:00Z"},
        {"start_id": 1120000001, "end_id": 1200000000, "date": "2023-05-01T00:00:00Z"},
        {"start_id": 1200000001, "end_id": 1280000000, "date": "2023-07-01T00:00:00Z"},
        {"start_id": 1280000001, "end_id": 1360000000, "date": "2023-09-01T00:00:00Z"},
        {"start_id": 1360000001, "end_id": 1450000000, "date": "2023-11-01T00:00:00Z"},
        {"start_id": 1450000001, "end_id": 1540000000, "date": "2024-01-01T00:00:00Z"},
        {"start_id": 1540000001, "end_id": 1640000000, "date": "2024-03-01T00:00:00Z"},
        {"start_id": 1640000001, "end_id": 1740000000, "date": "2024-05-01T00:00:00Z"},
        {"start_id": 1740000001, "end_id": 1850000000, "date": "2024-07-01T00:00:00Z"},
        {"start_id": 1850000001, "end_id": 1960000000, "date": "2024-09-01T00:00:00Z"},
        {"start_id": 1960000001, "end_id": 2080000000, "date": "2024-11-01T00:00:00Z"},
        {"start_id": 2080000001, "end_id": 2200000000, "date": "2025-01-01T00:00:00Z"},
        {"start_id": 2200000001, "end_id": 2350000000, "date": "2025-03-01T00:00:00Z"},
        {"start_id": 2350000001, "end_id": 2500000000, "date": "2025-05-01T00:00:00Z"},
        {"start_id": 2500000001, "end_id": 2700000000, "date": "2025-07-01T00:00:00Z"},
        {"start_id": 2700000001, "end_id": 2900000000, "date": "2025-09-01T00:00:00Z"},
        {"start_id": 2900000001, "end_id": 3100000000, "date": "2025-11-01T00:00:00Z"},
        {"start_id": 3100000001, "end_id": 3400000000, "date": "2026-01-01T00:00:00Z"},
        {"start_id": 3400000001, "end_id": 3700000000, "date": "2026-03-01T00:00:00Z"},
        {"start_id": 3700000001, "end_id": 4000000000, "date": "2026-05-01T00:00:00Z"},
        {"start_id": 4000000001, "end_id": 4500000000, "date": "2026-07-01T00:00:00Z"},
        {"start_id": 4500000001, "end_id": 5000000000, "date": "2026-09-01T00:00:00Z"},
        {"start_id": 5000000001, "end_id": 6000000000, "date": "2026-11-01T00:00:00Z"},
        {"start_id": 6000000001, "end_id": 7000000000, "date": "2027-01-01T00:00:00Z"},
    ]
    
    # Insert anchors
    await mongodb.db.id_anchors.insert_many(anchors)
    
    # Create index for fast lookups
    await mongodb.db.id_anchors.create_index([("start_id", 1), ("end_id", 1)])
    
    print(f"✅ Loaded {len(anchors)} anchor points into MongoDB")
    print("Collection: id_anchors")
    print("Indexes created for fast lookups")

if __name__ == "__main__":
    asyncio.run(load_anchors())
