#!/usr/bin/env python3
"""
Direct Profile Manager - Bypass broken menu system
Use this script to directly manage profiles until the menu system is fixed
"""

import asyncio
import os
import sys
from pathlib import Path

# Add teleguard to path
sys.path.insert(0, str(Path(__file__).parent))

from telethon import TelegramClient

from teleguard.core.client_manager import FullClientManager
from teleguard.core.config import API_HASH, API_ID
from teleguard.core.mongo_database import mongodb


class DirectProfileManager:
    def __init__(self):
        self.user_clients = {}
        self.client_manager = FullClientManager(None, self.user_clients)

    async def connect_account(self, user_id: int, account_name: str):
        """Connect to an account for profile management"""
        try:
            # Get account from MongoDB
            account = await mongodb.db.accounts.find_one(
                {"user_id": user_id, "name": account_name}
            )

            if not account:
                print(f"❌ Account '{account_name}' not found for user {user_id}")
                return False

            # Create client
            session_name = f"profile_manager_{account_name}"
            client = TelegramClient(session_name, API_ID, API_HASH)
            await client.connect()

            if not await client.is_user_authorized():
                print(f"❌ Account '{account_name}' is not authorized")
                return False

            # Store client
            if user_id not in self.user_clients:
                self.user_clients[user_id] = {}
            self.user_clients[user_id][account_name] = client

            print(f"✅ Connected to account: {account_name}")
            return True

        except Exception as e:
            print(f"❌ Failed to connect to account: {e}")
            return False

    async def update_name(
        self, user_id: int, account_id: str, first_name: str, last_name: str = ""
    ):
        """Update profile name"""
        success, message = await self.client_manager.update_profile_name(
            user_id, account_id, first_name, last_name
        )

        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")

        return success

    async def update_username(self, user_id: int, account_id: str, username: str):
        """Update username"""
        success, message = await self.client_manager.update_username(
            user_id, account_id, username
        )

        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")

        return success

    async def update_bio(self, user_id: int, account_id: str, bio: str):
        """Update bio"""
        success, message = await self.client_manager.update_bio(
            user_id, account_id, bio
        )

        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")

        return success

    async def list_accounts(self, user_id: int):
        """List all accounts for a user"""
        try:
            accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(
                length=None
            )

            if not accounts:
                print(f"❌ No accounts found for user {user_id}")
                return []

            print(f"\nAccounts for user {user_id}:")
            for i, account in enumerate(accounts, 1):
                print(f"{i}. {account['name']} (ID: {account['_id']})")

            return accounts

        except Exception as e:
            print(f"❌ Failed to list accounts: {e}")
            return []


async def main():
    """Interactive profile manager"""
    print("TeleGuard Direct Profile Manager")
    print("=" * 50)

    # Initialize MongoDB
    await mongodb.connect()

    manager = DirectProfileManager()

    # Get user ID
    try:
        user_id = int(input("Enter your Telegram User ID: "))
    except ValueError:
        print("❌ Invalid user ID")
        return

    # List accounts
    accounts = await manager.list_accounts(user_id)
    if not accounts:
        return

    # Select account
    try:
        account_num = int(input("\nSelect account number (1, 2, 3, etc.): ")) - 1
        if account_num < 0 or account_num >= len(accounts):
            print("❌ Invalid account number")
            return

        selected_account = accounts[account_num]
        account_id = str(selected_account["_id"])
        account_name = selected_account["name"]

    except ValueError:
        print("❌ Invalid account number")
        return

    # Connect to account
    if not await manager.connect_account(user_id, account_name):
        return

    # Profile management menu
    while True:
        print(f"\nProfile Manager - {account_name}")
        print("1. Update Name")
        print("2. Update Username")
        print("3. Update Bio")
        print("4. Exit")

        choice = input("\nSelect option (1-4): ").strip()

        if choice == "1":
            first_name = input("Enter first name: ").strip()
            last_name = input("Enter last name (optional): ").strip()
            await manager.update_name(user_id, account_id, first_name, last_name)

        elif choice == "2":
            username = input("Enter username (without @): ").strip()
            await manager.update_username(user_id, account_id, username)

        elif choice == "3":
            bio = input("Enter bio: ").strip()
            await manager.update_bio(user_id, account_id, bio)

        elif choice == "4":
            break

        else:
            print("❌ Invalid option")


if __name__ == "__main__":
    asyncio.run(main())
