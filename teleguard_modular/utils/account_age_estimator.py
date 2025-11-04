"""Account age estimation using Telegram ID ranges (AyuGram-based)"""
import datetime
from decimal import Decimal, getcontext, ROUND_HALF_UP
from typing import Optional, Tuple, List, Dict
import logging
import csv
import os

getcontext().prec = 34
logger = logging.getLogger(__name__)

class AccountAgeEstimator:
    """Estimates account creation date based on Telegram user ID ranges"""
    
    _anchors_cache: Optional[List[Dict]] = None
    
    # Anchor points from creationDate project - accurate community-verified data
    ID_RANGES = [
        (1, 5000, datetime.datetime.fromisoformat('2013-08-01T00:00:00Z')),
        (5001, 55000, datetime.datetime.fromisoformat('2013-08-15T00:00:00Z')),
        (55001, 550000, datetime.datetime.fromisoformat('2013-09-01T00:00:00Z')),
        (550001, 5500000, datetime.datetime.fromisoformat('2013-10-15T00:00:00Z')),
        (5500001, 55000000, datetime.datetime.fromisoformat('2014-02-01T00:00:00Z')),
        (55000001, 150000000, datetime.datetime.fromisoformat('2015-03-01T00:00:00Z')),
        (150000001, 250000000, datetime.datetime.fromisoformat('2016-01-01T00:00:00Z')),
        (250000001, 350000000, datetime.datetime.fromisoformat('2016-09-01T00:00:00Z')),
        (350000001, 450000000, datetime.datetime.fromisoformat('2017-04-01T00:00:00Z')),
        (450000001, 550000000, datetime.datetime.fromisoformat('2018-01-01T00:00:00Z')),
        (550000001, 650000000, datetime.datetime.fromisoformat('2018-08-01T00:00:00Z')),
        (650000001, 750000000, datetime.datetime.fromisoformat('2019-02-01T00:00:00Z')),
        (750000001, 850000000, datetime.datetime.fromisoformat('2019-08-01T00:00:00Z')),
        (850000001, 950000000, datetime.datetime.fromisoformat('2020-01-01T00:00:00Z')),
        (950000001, 1050000000, datetime.datetime.fromisoformat('2020-06-01T00:00:00Z')),
        (1050000001, 1150000000, datetime.datetime.fromisoformat('2020-10-01T00:00:00Z')),
        (1150000001, 1250000000, datetime.datetime.fromisoformat('2021-02-01T00:00:00Z')),
        (1250000001, 1350000000, datetime.datetime.fromisoformat('2021-06-01T00:00:00Z')),
        (1350000001, 1450000000, datetime.datetime.fromisoformat('2021-09-01T00:00:00Z')),
        (1450000001, 1550000000, datetime.datetime.fromisoformat('2021-12-01T00:00:00Z')),
        (1550000001, 1650000000, datetime.datetime.fromisoformat('2022-03-01T00:00:00Z')),
        (1650000001, 1750000000, datetime.datetime.fromisoformat('2022-06-01T00:00:00Z')),
        (1750000001, 1850000000, datetime.datetime.fromisoformat('2022-09-01T00:00:00Z')),
        (1850000001, 1950000000, datetime.datetime.fromisoformat('2022-12-01T00:00:00Z')),
        (1950000001, 2050000000, datetime.datetime.fromisoformat('2023-03-01T00:00:00Z')),
        (2050000001, 2150000000, datetime.datetime.fromisoformat('2023-06-01T00:00:00Z')),
        (2150000001, 2250000000, datetime.datetime.fromisoformat('2023-09-01T00:00:00Z')),
        (2250000001, 2350000000, datetime.datetime.fromisoformat('2023-12-01T00:00:00Z')),
        (2350000001, 2450000000, datetime.datetime.fromisoformat('2024-03-01T00:00:00Z')),
        (2450000001, 2550000000, datetime.datetime.fromisoformat('2024-06-01T00:00:00Z')),
        (2550000001, 2650000000, datetime.datetime.fromisoformat('2024-09-01T00:00:00Z')),
        (2650000001, 2750000000, datetime.datetime.fromisoformat('2024-11-01T00:00:00Z')),
        (2750000001, 3000000000, datetime.datetime.fromisoformat('2024-12-15T00:00:00Z')),
    ]
    
    @classmethod
    def load_anchors_from_csv(cls):
        """Load anchors from CSV file"""
        csv_path = os.path.join(os.path.dirname(__file__), 'anchor.csv')
        try:
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                return [
                    (
                        int(row['start_id']),
                        int(row['end_id']),
                        datetime.datetime.fromisoformat(row['date'].replace('Z', '+00:00'))
                    )
                    for row in reader
                ]
        except Exception as e:
            logger.error(f"Failed to load anchor.csv: {e}")
            return cls.ID_RANGES
    
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
                logger.info("No anchors in MongoDB, loading from CSV")
                cls._anchors_cache = cls.load_anchors_from_csv()
        except Exception as e:
            logger.error(f"Failed to load anchors from MongoDB: {e}, using CSV")
            cls._anchors_cache = cls.load_anchors_from_csv()
        
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