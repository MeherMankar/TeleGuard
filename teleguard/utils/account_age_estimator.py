"""Account age estimation using Telegram ID ranges (AyuGram-based)"""
import datetime
from decimal import Decimal, getcontext, ROUND_HALF_UP
from typing import Optional, Tuple, List, Dict
import logging

getcontext().prec = 34
logger = logging.getLogger(__name__)

class AccountAgeEstimator:
    """Estimates account creation date based on Telegram user ID ranges"""
    
    _anchors_cache: Optional[List[Dict]] = None
    
    # Anchor points: (start_id, end_id, creation_date) - High precision dataset
    ID_RANGES = [
        (1, 10000, datetime.datetime(2013, 8, 14, tzinfo=datetime.timezone.utc)),
        (10001, 25000, datetime.datetime(2013, 8, 25, tzinfo=datetime.timezone.utc)),
        (25001, 50000, datetime.datetime(2013, 9, 5, tzinfo=datetime.timezone.utc)),
        (50001, 75000, datetime.datetime(2013, 9, 15, tzinfo=datetime.timezone.utc)),
        (75001, 100000, datetime.datetime(2013, 9, 25, tzinfo=datetime.timezone.utc)),
        (100001, 150000, datetime.datetime(2013, 10, 10, tzinfo=datetime.timezone.utc)),
        (150001, 200000, datetime.datetime(2013, 10, 25, tzinfo=datetime.timezone.utc)),
        (200001, 300000, datetime.datetime(2013, 11, 10, tzinfo=datetime.timezone.utc)),
        (300001, 400000, datetime.datetime(2013, 11, 25, tzinfo=datetime.timezone.utc)),
        (400001, 550000, datetime.datetime(2013, 12, 10, tzinfo=datetime.timezone.utc)),
        (550001, 700000, datetime.datetime(2013, 12, 25, tzinfo=datetime.timezone.utc)),
        (700001, 850000, datetime.datetime(2014, 1, 10, tzinfo=datetime.timezone.utc)),
        (850001, 1000000, datetime.datetime(2014, 1, 25, tzinfo=datetime.timezone.utc)),
        (1000001, 1250000, datetime.datetime(2014, 2, 15, tzinfo=datetime.timezone.utc)),
        (1250001, 1500000, datetime.datetime(2014, 3, 15, tzinfo=datetime.timezone.utc)),
        (1500001, 1750000, datetime.datetime(2014, 4, 15, tzinfo=datetime.timezone.utc)),
        (1750001, 2000000, datetime.datetime(2014, 5, 15, tzinfo=datetime.timezone.utc)),
        (2000001, 2500000, datetime.datetime(2014, 7, 1, tzinfo=datetime.timezone.utc)),
        (2500001, 3000000, datetime.datetime(2014, 8, 15, tzinfo=datetime.timezone.utc)),
        (3000001, 3500000, datetime.datetime(2014, 10, 1, tzinfo=datetime.timezone.utc)),
        (3500001, 4000000, datetime.datetime(2014, 11, 15, tzinfo=datetime.timezone.utc)),
        (4000001, 4500000, datetime.datetime(2015, 1, 1, tzinfo=datetime.timezone.utc)),
        (4500001, 5000000, datetime.datetime(2015, 2, 15, tzinfo=datetime.timezone.utc)),
        (5000001, 6000000, datetime.datetime(2015, 4, 1, tzinfo=datetime.timezone.utc)),
        (6000001, 7000000, datetime.datetime(2015, 6, 1, tzinfo=datetime.timezone.utc)),
        (7000001, 8500000, datetime.datetime(2015, 8, 1, tzinfo=datetime.timezone.utc)),
        (8500001, 10000000, datetime.datetime(2015, 10, 1, tzinfo=datetime.timezone.utc)),
        (10000001, 12500000, datetime.datetime(2016, 1, 1, tzinfo=datetime.timezone.utc)),
        (12500001, 15000000, datetime.datetime(2016, 3, 1, tzinfo=datetime.timezone.utc)),
        (15000001, 17500000, datetime.datetime(2016, 5, 1, tzinfo=datetime.timezone.utc)),
        (17500001, 20000000, datetime.datetime(2016, 7, 1, tzinfo=datetime.timezone.utc)),
        (20000001, 22500000, datetime.datetime(2016, 9, 1, tzinfo=datetime.timezone.utc)),
        (22500001, 25000000, datetime.datetime(2016, 11, 1, tzinfo=datetime.timezone.utc)),
        (25000001, 27500000, datetime.datetime(2017, 1, 1, tzinfo=datetime.timezone.utc)),
        (27500001, 30000000, datetime.datetime(2017, 3, 1, tzinfo=datetime.timezone.utc)),
        (30000001, 35000000, datetime.datetime(2017, 5, 1, tzinfo=datetime.timezone.utc)),
        (35000001, 40000000, datetime.datetime(2017, 7, 1, tzinfo=datetime.timezone.utc)),
        (40000001, 45000000, datetime.datetime(2017, 9, 1, tzinfo=datetime.timezone.utc)),
        (45000001, 50000000, datetime.datetime(2017, 11, 1, tzinfo=datetime.timezone.utc)),
        (50000001, 55000000, datetime.datetime(2018, 1, 1, tzinfo=datetime.timezone.utc)),
        (55000001, 60000000, datetime.datetime(2018, 3, 1, tzinfo=datetime.timezone.utc)),
        (60000001, 70000000, datetime.datetime(2018, 5, 1, tzinfo=datetime.timezone.utc)),
        (70000001, 80000000, datetime.datetime(2018, 7, 1, tzinfo=datetime.timezone.utc)),
        (80000001, 90000000, datetime.datetime(2018, 9, 1, tzinfo=datetime.timezone.utc)),
        (90000001, 100000000, datetime.datetime(2018, 11, 1, tzinfo=datetime.timezone.utc)),
        (100000001, 110000000, datetime.datetime(2019, 1, 1, tzinfo=datetime.timezone.utc)),
        (110000001, 130000000, datetime.datetime(2019, 3, 1, tzinfo=datetime.timezone.utc)),
        (130000001, 150000000, datetime.datetime(2019, 5, 1, tzinfo=datetime.timezone.utc)),
        (150000001, 170000000, datetime.datetime(2019, 7, 1, tzinfo=datetime.timezone.utc)),
        (170000001, 190000000, datetime.datetime(2019, 9, 1, tzinfo=datetime.timezone.utc)),
        (190000001, 210000000, datetime.datetime(2019, 11, 1, tzinfo=datetime.timezone.utc)),
        (210000001, 240000000, datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)),
        (240000001, 270000000, datetime.datetime(2020, 3, 1, tzinfo=datetime.timezone.utc)),
        (270000001, 300000000, datetime.datetime(2020, 5, 1, tzinfo=datetime.timezone.utc)),
        (300000001, 330000000, datetime.datetime(2020, 7, 1, tzinfo=datetime.timezone.utc)),
        (330000001, 360000000, datetime.datetime(2020, 9, 1, tzinfo=datetime.timezone.utc)),
        (360000001, 390000000, datetime.datetime(2020, 11, 1, tzinfo=datetime.timezone.utc)),
        (390000001, 425000000, datetime.datetime(2021, 1, 1, tzinfo=datetime.timezone.utc)),
        (425000001, 460000000, datetime.datetime(2021, 3, 1, tzinfo=datetime.timezone.utc)),
        (460000001, 500000000, datetime.datetime(2021, 5, 1, tzinfo=datetime.timezone.utc)),
        (500000001, 540000000, datetime.datetime(2021, 7, 1, tzinfo=datetime.timezone.utc)),
        (540000001, 580000000, datetime.datetime(2021, 9, 1, tzinfo=datetime.timezone.utc)),
        (580000001, 620000000, datetime.datetime(2021, 11, 1, tzinfo=datetime.timezone.utc)),
        (620000001, 670000000, datetime.datetime(2022, 1, 1, tzinfo=datetime.timezone.utc)),
        (670000001, 720000000, datetime.datetime(2022, 3, 1, tzinfo=datetime.timezone.utc)),
        (720000001, 780000000, datetime.datetime(2022, 5, 1, tzinfo=datetime.timezone.utc)),
        (780000001, 840000000, datetime.datetime(2022, 7, 1, tzinfo=datetime.timezone.utc)),
        (840000001, 900000000, datetime.datetime(2022, 9, 1, tzinfo=datetime.timezone.utc)),
        (900000001, 970000000, datetime.datetime(2022, 11, 1, tzinfo=datetime.timezone.utc)),
        (970000001, 1040000000, datetime.datetime(2023, 1, 1, tzinfo=datetime.timezone.utc)),
        (1040000001, 1120000000, datetime.datetime(2023, 3, 1, tzinfo=datetime.timezone.utc)),
        (1120000001, 1200000000, datetime.datetime(2023, 5, 1, tzinfo=datetime.timezone.utc)),
        (1200000001, 1280000000, datetime.datetime(2023, 7, 1, tzinfo=datetime.timezone.utc)),
        (1280000001, 1360000000, datetime.datetime(2023, 9, 1, tzinfo=datetime.timezone.utc)),
        (1360000001, 1450000000, datetime.datetime(2023, 11, 1, tzinfo=datetime.timezone.utc)),
        (1450000001, 1540000000, datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)),
        (1540000001, 1640000000, datetime.datetime(2024, 3, 1, tzinfo=datetime.timezone.utc)),
        (1640000001, 1740000000, datetime.datetime(2024, 5, 1, tzinfo=datetime.timezone.utc)),
        (1740000001, 1850000000, datetime.datetime(2024, 7, 1, tzinfo=datetime.timezone.utc)),
        (1850000001, 1960000000, datetime.datetime(2024, 9, 1, tzinfo=datetime.timezone.utc)),
        (1960000001, 2080000000, datetime.datetime(2024, 11, 1, tzinfo=datetime.timezone.utc)),
        (2080000001, 2200000000, datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)),
        (2200000001, 2350000000, datetime.datetime(2025, 3, 1, tzinfo=datetime.timezone.utc)),
        (2350000001, 2500000000, datetime.datetime(2025, 5, 1, tzinfo=datetime.timezone.utc)),
        (2500000001, 2700000000, datetime.datetime(2025, 7, 1, tzinfo=datetime.timezone.utc)),
        (2700000001, 2900000000, datetime.datetime(2025, 9, 1, tzinfo=datetime.timezone.utc)),
        (2900000001, 3100000000, datetime.datetime(2025, 11, 1, tzinfo=datetime.timezone.utc)),
        (3100000001, 3400000000, datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)),
        (3400000001, 3700000000, datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc)),
        (3700000001, 4000000000, datetime.datetime(2026, 5, 1, tzinfo=datetime.timezone.utc)),
        (4000000001, 4500000000, datetime.datetime(2026, 7, 1, tzinfo=datetime.timezone.utc)),
        (4500000001, 5000000000, datetime.datetime(2026, 9, 1, tzinfo=datetime.timezone.utc)),
        (5000000001, 6000000000, datetime.datetime(2026, 11, 1, tzinfo=datetime.timezone.utc)),
        (6000000001, 7000000000, datetime.datetime(2027, 1, 1, tzinfo=datetime.timezone.utc)),
    ]
    
    @classmethod
    async def load_anchors_from_db(cls):
        """Load anchors from MongoDB (cached)"""
        if cls._anchors_cache is not None:
            return cls._anchors_cache
        
        try:
            from ..core.mongo_database import mongodb
            anchors = await mongodb.db.id_anchors.find({}).sort("start_id", 1).to_list(None)
            
            if anchors:
                cls._anchors_cache = [
                    (
                        int(a["start_id"]),
                        int(a["end_id"]),
                        datetime.datetime.fromisoformat(a["date"].replace("Z", "+00:00"))
                    )
                    for a in anchors
                ]
                logger.info(f"Loaded {len(cls._anchors_cache)} anchors from MongoDB")
            else:
                logger.warning("No anchors in MongoDB, using fallback")
                cls._anchors_cache = cls.ID_RANGES
        except Exception as e:
            logger.error(f"Failed to load anchors from MongoDB: {e}")
            cls._anchors_cache = cls.ID_RANGES
        
        return cls._anchors_cache
    
    @classmethod
    async def estimate_creation_date(cls, user_id: int) -> Tuple[Optional[datetime.datetime], str]:
        """
        Estimate account creation date from user ID
        Returns (estimated_datetime, method_description)
        """
        if not user_id or user_id <= 0:
            return None, "invalid-id"
        
        # Load anchors from MongoDB
        anchors = await cls.load_anchors_from_db()
        
        # Check for direct range hit with interpolation within range
        for start_id, end_id, creation_date in anchors:
            if start_id <= user_id <= end_id:
                # Interpolate within the range for better precision
                if start_id == end_id:
                    return creation_date, f"exact-match {start_id}"
                
                # Find next range for end interpolation
                idx = anchors.index((start_id, end_id, creation_date))
                if idx < len(anchors) - 1:
                    next_start, next_end, next_date = anchors[idx + 1]
                    # Interpolate between range start and next range start
                    epoch0 = Decimal(int(creation_date.timestamp()))
                    epoch1 = Decimal(int(next_date.timestamp()))
                    numerator = Decimal(user_id - start_id)
                    denominator = Decimal(next_start - start_id)
                    if denominator > 0:
                        frac = numerator / denominator
                        seconds_span = epoch1 - epoch0
                        add_seconds = (frac * seconds_span).quantize(Decimal("1.0000000000"))
                        est_epoch_dec = (epoch0 + add_seconds).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                        est_epoch = int(est_epoch_dec)
                        estimated_date = datetime.datetime.fromtimestamp(est_epoch, datetime.timezone.utc)
                        return estimated_date, f"intra-range {start_id}-{next_start}"
                
                return creation_date, f"range-hit {start_id}-{end_id}"
        
        # Build anchor points (start points only for better interpolation)
        points = [(s, d) for s, e, d in anchors]
        
        # Find lower and upper anchor points
        lower = None
        upper = None
        for pid, ptime in points:
            if pid <= user_id:
                lower = (pid, ptime)
            elif pid > user_id and upper is None:
                upper = (pid, ptime)
        
        if lower is None:
            return points[0][1], "clamped-earliest"
        if upper is None:
            return points[-1][1], "clamped-latest"
        
        id0, dt0 = lower
        id1, dt1 = upper
        if id1 == id0:
            return dt0, "degenerate-anchor"
        
        # High-precision interpolation using Decimal
        epoch0 = Decimal(int(dt0.timestamp()))
        epoch1 = Decimal(int(dt1.timestamp()))
        numerator = Decimal(user_id - id0)
        denominator = Decimal(id1 - id0)
        frac = numerator / denominator
        seconds_span = epoch1 - epoch0
        add_seconds = (frac * seconds_span).quantize(Decimal("1.0000000000"))
        est_epoch_dec = (epoch0 + add_seconds).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        est_epoch = int(est_epoch_dec)
        estimated_date = datetime.datetime.fromtimestamp(est_epoch, datetime.timezone.utc)
        
        return estimated_date, f"interpolated {id0}->{id1}"
    
    @classmethod
    def calculate_age_days(cls, creation_date: datetime.datetime) -> int:
        """Calculate age in days from creation date"""
        if not creation_date:
            return 0
        
        now = datetime.datetime.now(datetime.timezone.utc)
        if creation_date.tzinfo is None:
            creation_date = creation_date.replace(tzinfo=datetime.timezone.utc)
        
        return max(0, (now - creation_date).days)
    
    @classmethod
    def format_age(cls, creation_date: datetime.datetime) -> str:
        """Format age as 'Xy Ym Zd (N days)' matching AyuGram behavior"""
        if creation_date.tzinfo is None:
            creation_date = creation_date.replace(tzinfo=datetime.timezone.utc)
        now = datetime.datetime.now(datetime.timezone.utc)
        
        years = now.year - creation_date.year
        months = now.month - creation_date.month
        days = now.day - creation_date.day
        
        if days < 0:
            prev_month = (now.replace(day=1) - datetime.timedelta(days=1)).day
            days += prev_month
            months -= 1
        if months < 0:
            months += 12
            years -= 1
        
        total_days = (now - creation_date).days
        return f"{years}y {months}m {days}d ({total_days} days)"