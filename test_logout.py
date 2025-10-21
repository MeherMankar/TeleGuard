#!/usr/bin/env python3
"""
Test script to verify LogOutRequest functionality
"""

def test_logout_import():
    """Test that LogOutRequest can be imported correctly"""
    try:
        from telethon.tl.functions.auth import LogOutRequest
        print("[OK] LogOutRequest imported successfully")
        print(f"LogOutRequest class: {LogOutRequest}")
        return True
    except ImportError as e:
        print(f"[ERROR] Failed to import LogOutRequest: {e}")
        return False

def test_logout_usage():
    """Test LogOutRequest usage pattern"""
    try:
        from telethon.tl.functions.auth import LogOutRequest
        
        # Create a LogOutRequest instance
        logout_request = LogOutRequest()
        print("[OK] LogOutRequest instance created successfully")
        print(f"Request type: {type(logout_request)}")
        
        # Check if it has the expected attributes
        if hasattr(logout_request, 'CONSTRUCTOR_ID'):
            print(f"[OK] Constructor ID: {logout_request.CONSTRUCTOR_ID}")
        
        return True
    except Exception as e:
        print(f"[ERROR] Failed to create LogOutRequest: {e}")
        return False

if __name__ == "__main__":
    print("Testing LogOutRequest functionality...")
    print("=" * 50)
    
    import_success = test_logout_import()
    usage_success = test_logout_usage()
    
    print("=" * 50)
    if import_success and usage_success:
        print("[SUCCESS] All tests passed! LogOutRequest is ready to use.")
    else:
        print("[FAILED] Some tests failed. Check Telethon installation.")