#!/usr/bin/env python3
"""Fix all account['name'] references to use safe access"""

import os
import re
from pathlib import Path

def get_account_name_safe(account_var="account"):
    """Generate safe account name access code"""
    return f"{account_var}.get('name') or {account_var}.get('phone') or {account_var}.get('display_name', 'Unknown')"

def fix_file(file_path):
    """Fix account['name'] references in a file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Pattern to match account["name"] or account['name']
        patterns = [
            (r'account\[\"name\"\]', get_account_name_safe()),
            (r"account\['name'\]", get_account_name_safe()),
            # Handle other variable names like acc["name"]
            (r'(\w+)\[\"name\"\]', lambda m: get_account_name_safe(m.group(1))),
            (r"(\w+)\['name'\]", lambda m: get_account_name_safe(m.group(1))),
        ]
        
        for pattern, replacement in patterns:
            if callable(replacement):
                content = re.sub(pattern, replacement, content)
            else:
                content = re.sub(pattern, replacement, content)
        
        # Write back if changed
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Fixed: {file_path}")
            return True
        else:
            print(f"⚪ No changes: {file_path}")
            return False
            
    except Exception as e:
        print(f"❌ Error fixing {file_path}: {e}")
        return False

def main():
    """Main function to fix all files"""
    teleguard_dir = Path("teleguard")
    
    if not teleguard_dir.exists():
        print("❌ teleguard directory not found")
        return
    
    # Find all Python files
    py_files = list(teleguard_dir.rglob("*.py"))
    
    fixed_count = 0
    total_count = len(py_files)
    
    print(f"Found {total_count} Python files to check")
    
    for py_file in py_files:
        if fix_file(py_file):
            fixed_count += 1
    
    print(f"\nSummary:")
    print(f"  Total files: {total_count}")
    print(f"  Files fixed: {fixed_count}")
    print(f"  Files unchanged: {total_count - fixed_count}")

if __name__ == "__main__":
    main()