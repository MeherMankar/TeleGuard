"""Account age estimation using Telegram ID ranges"""
import datetime
from typing import Optional, Tuple

class AccountAgeEstimator:
    """Estimates account creation date based on Telegram user ID ranges"""
    
    # Basic ID ranges dataset (start_id, end_id, creation_date)
    ID_RANGES = [
        (1, 1000000, datetime.datetime(2013, 8, 1, tzinfo=datetime.timezone.utc)),
        (1000001, 5000000, datetime.datetime(2014, 2, 1, tzinfo=datetime.timezone.utc)),
        (5000001, 20000000, datetime.datetime(2015, 7, 1, tzinfo=datetime.timezone.utc)),
        (20000001, 50000000, datetime.datetime(2016, 6, 1, tzinfo=datetime.timezone.utc)),
        (50000001, 100000000, datetime.datetime(2017, 8, 1, tzinfo=datetime.timezone.utc)),
        (100000001, 200000000, datetime.datetime(2018, 10, 1, tzinfo=datetime.timezone.utc)),
        (200000001, 400000000, datetime.datetime(2019, 12, 1, tzinfo=datetime.timezone.utc)),
        (400000001, 700000000, datetime.datetime(2021, 3, 1, tzinfo=datetime.timezone.utc)),
        (700000001, 1000000000, datetime.datetime(2022, 6, 1, tzinfo=datetime.timezone.utc)),
        (1000000001, 1500000000, datetime.datetime(2023, 9, 1, tzinfo=datetime.timezone.utc)),
        (1500000001, 2000000000, datetime.datetime(2024, 6, 1, tzinfo=datetime.timezone.utc)),
    ]
    
    @classmethod
    def estimate_creation_date(cls, user_id: int) -> Tuple[Optional[datetime.datetime], str]:
        """
        Estimate account creation date from user ID
        Returns (estimated_datetime, method_description)
        """
        if not user_id or user_id <= 0:
            return None, "invalid-id"
        
        # Check for direct range hit
        for start_id, end_id, creation_date in cls.ID_RANGES:
            if start_id <= user_id <= end_id:
                return creation_date, "range-match"
        
        # Find surrounding ranges for interpolation
        lower_range = None
        upper_range = None
        
        for i, (start_id, end_id, creation_date) in enumerate(cls.ID_RANGES):
            if user_id < start_id:
                upper_range = (start_id, creation_date)
                if i > 0:
                    prev_start, prev_end, prev_date = cls.ID_RANGES[i-1]
                    lower_range = (prev_end, prev_date)
                break
            elif user_id > end_id:
                lower_range = (end_id, creation_date)
        
        # Handle edge cases
        if not lower_range and not upper_range:
            return cls.ID_RANGES[-1][2], "above-max"
        elif not lower_range:
            return upper_range[1], "below-min"
        elif not upper_range:
            return lower_range[1], "above-max"
        
        # Linear interpolation
        id1, date1 = lower_range
        id2, date2 = upper_range
        
        if id2 == id1:
            return date1, "degenerate"
        
        # Calculate interpolated date
        ratio = (user_id - id1) / (id2 - id1)
        time_diff = (date2 - date1).total_seconds()
        estimated_timestamp = date1.timestamp() + (ratio * time_diff)
        estimated_date = datetime.datetime.fromtimestamp(estimated_timestamp, datetime.timezone.utc)
        
        return estimated_date, f"interpolated"
    
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
    def format_age(cls, age_days: int) -> str:
        """Format age display string"""
        if age_days >= 365:
            years = age_days // 365
            months = (age_days % 365) // 30
            if months > 0:
                return f"{years}y {months}m ({age_days} days)"
            else:
                return f"{years} year{'s' if years != 1 else ''} ({age_days} days)"
        elif age_days >= 30:
            months = age_days // 30
            days = age_days % 30
            if days > 0:
                return f"{months}m {days}d ({age_days} days)"
            else:
                return f"{months} month{'s' if months != 1 else ''} ({age_days} days)"
        else:
            return f"{age_days} day{'s' if age_days != 1 else ''}"