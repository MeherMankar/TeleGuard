"""Account helper utilities"""

def get_account_name(account):
    """Get account name safely from account dict"""
    if not account:
        return "Unknown"
    
    return (
        account.get('name') or 
        account.get('phone') or 
        account.get('display_name') or 
        'Unknown'
    )

def get_account_display_name(account):
    """Get formatted display name from account"""
    if not account:
        return "Unknown"
    
    # Try display_name first
    if account.get('display_name'):
        return account['display_name']
    
    # Try first/last name combination
    first = account.get('first_name', '')
    last = account.get('last_name', '')
    if first or last:
        return f"{first} {last}".strip()
    
    # Try username
    if account.get('username'):
        return f"@{account['username']}"
    
    # Fall back to phone or name
    return account.get('phone') or account.get('name') or 'Unknown'