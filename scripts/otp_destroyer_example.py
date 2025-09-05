"""
Example demonstrating the OTP Destroyer functionality

This script shows how the two-client authentication pattern works:
1. First client requests OTP and disconnects (creates "incomplete login" alert)
2. Second client completes the authentication using the same session
"""

import asyncio
from auth_handler import OTPDestroyer

async def demo_otp_destroyer():
    """Demonstrate OTP destroyer authentication flow"""
    destroyer = OTPDestroyer()
    
    # Replace with your phone number
    phone = input("Enter phone number (with country code, e.g., +1234567890): ")
    
    print("Step 1: Starting phone authentication...")
    try:
        # Step 1: Request OTP (first client)
        auth_data = await destroyer.start_phone_auth(phone)
        print(f"OTP sent to {phone}")
        print("Check your Telegram app - you should see an 'incomplete login' notification")
        
        # Get OTP from user
        code = input("Enter the OTP code you received: ")
        
        print("Step 2: Completing authentication with new client...")
        # Step 2: Complete auth with second client
        try:
            session_string = await destroyer.verify_code(auth_data, code)
            print("Authentication successful!")
            print(f"Session string length: {len(session_string)} characters")
            print("The 'incomplete login' alert was triggered by the OTP destroyer pattern")
        except Exception as e:
            if "Two-factor" in str(e):
                print("2FA detected. Enter your password:")
                password = input("2FA Password: ")
                session_string = await destroyer.verify_code(auth_data, code, password)
                print("Authentication successful with 2FA!")
                print(f"Session string length: {len(session_string)} characters")
                print("The 'incomplete login' alert was triggered by the OTP destroyer pattern")
            else:
                raise e
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("OTP Destroyer Demo")
    print("This will create an 'incomplete login' alert while successfully authenticating")
    print()
    
    asyncio.run(demo_otp_destroyer())