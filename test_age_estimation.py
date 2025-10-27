"""Test age estimation accuracy"""
import asyncio
from teleguard.utils.account_age_estimator import AccountAgeEstimator

async def test():
    # Test with known user IDs
    test_cases = [
        (777000, "Telegram Service (2013)"),  # Official Telegram account
        (1000000000, "~June 2020"),
        (2000000000, "~March 2023"),
        (2700000000, "~November 2024"),
    ]
    
    print("Testing age estimation:\n")
    for user_id, expected in test_cases:
        creation_date, method = await AccountAgeEstimator.estimate_creation_date(user_id)
        if creation_date:
            print(f"ID {user_id:,}")
            print(f"  Expected: {expected}")
            print(f"  Estimated: {creation_date.strftime('%B %Y')}")
            print(f"  Method: {method}\n")

if __name__ == "__main__":
    asyncio.run(test())
