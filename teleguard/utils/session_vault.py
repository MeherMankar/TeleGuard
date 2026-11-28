"""
Session Vault — automatic second-session backup and auto-recovery.

Storage hierarchy:
  PRIMARY   → MongoDB  (vault_sessions collection)
  SECONDARY → GitHub   (vault/sessions/{account_id}.enc on SESSION_BACKUP_GITHUB_REPO)

Failover when main session is revoked by Telegram:
  1. Load vault session from MongoDB (primary)
     → promote it to main, delete from MongoDB vault, schedule new vault creation
  2. If MongoDB vault empty, load from GitHub (secondary)
     → promote to main, delete from GitHub, write to MongoDB, schedule new vault
  3. Both empty → fall through to existing invalidation flow (account removed)

User-initiated removal deletes vault from both stores.
Telegram-initiated invalidation must NEVER delete the vault — it is consumed
during failover.
"""

import asyncio
import logging
import time
from typing import Optional

from ..core.config import FERNET, config
from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


class SessionVault:
    """Manages encrypted backup (vault) sessions for auto-recovery."""

    def __init__(self):
        self._fernet = FERNET
        self._github_enabled = (
            bool(config.backup.session_backup_github_repo)
            and bool(config.backup.session_backup_github_token)
            and self._fernet is not None
        )

    @property
    def enabled(self) -> bool:
        return self._fernet is not None

    # ------------------------------------------------------------------ #
    #  MongoDB vault (primary)                                             #
    # ------------------------------------------------------------------ #

    async def store_mongo(
        self, user_id: int, account_id: str, phone: str, name: str, session_string: str
    ) -> bool:
        """Encrypt and store a vault session in MongoDB."""
        try:
            if not self.enabled:
                return False
            encrypted = self._fernet.encrypt(session_string.encode()).decode()
            now = int(time.time())
            await mongodb.db.vault_sessions.update_one(
                {"user_id": user_id, "account_id": account_id},
                {
                    "$set": {
                        "user_id": user_id,
                        "account_id": account_id,
                        "phone": phone,
                        "name": name,
                        "vault_session_enc": encrypted,
                        "updated_at": now,
                    },
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )
            logger.info("Vault session stored in MongoDB for account %s", account_id)
            return True
        except Exception as e:
            logger.warning("MongoDB vault store failed for %s: %s", account_id, e)
            return False

    async def retrieve_mongo(self, user_id: int, account_id: str) -> Optional[str]:
        """Return decrypted vault session from MongoDB, or None."""
        try:
            if not self.enabled:
                return None
            doc = await mongodb.db.vault_sessions.find_one(
                {"user_id": user_id, "account_id": account_id}
            )
            if not doc or not doc.get("vault_session_enc"):
                return None
            return self._fernet.decrypt(doc["vault_session_enc"].encode()).decode()
        except Exception as e:
            logger.warning("MongoDB vault retrieve failed for %s: %s", account_id, e)
            return None

    async def delete_mongo(self, user_id: int, account_id: str) -> bool:
        """Delete vault session from MongoDB."""
        try:
            result = await mongodb.db.vault_sessions.delete_one(
                {"user_id": user_id, "account_id": account_id}
            )
            return result.deleted_count > 0
        except Exception as e:
            logger.warning("MongoDB vault delete failed for %s: %s", account_id, e)
            return False

    async def exists_mongo(self, user_id: int, account_id: str) -> bool:
        try:
            doc = await mongodb.db.vault_sessions.find_one(
                {"user_id": user_id, "account_id": account_id},
                {"_id": 1},
            )
            return doc is not None
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    #  GitHub vault (secondary)                                            #
    # ------------------------------------------------------------------ #

    def _github_path(self, account_id: str) -> str:
        return f"vault/sessions/{account_id}.enc"

    async def store_github(self, account_id: str, session_string: str) -> bool:
        """Encrypt and push vault session to GitHub."""
        if not self._github_enabled or not self.enabled:
            return False
        try:
            from .session_backup import SessionBackupManager

            mgr = SessionBackupManager()
            encrypted = self._fernet.encrypt(session_string.encode())

            def _push():
                mgr._ensure_private_branch()
                mgr._ensure_readme()
                mgr._put_file(
                    self._github_path(account_id),
                    encrypted,
                    compare_plaintext=session_string.encode(),
                )

            await asyncio.to_thread(_push)
            logger.info("Vault session stored on GitHub for account %s", account_id)
            return True
        except Exception as e:
            logger.warning("GitHub vault store failed for %s: %s", account_id, e)
            return False

    async def retrieve_github(self, account_id: str) -> Optional[str]:
        """Return decrypted vault session from GitHub, or None."""
        if not self._github_enabled or not self.enabled:
            return None
        try:
            import base64

            from .session_backup import SessionBackupManager

            mgr = SessionBackupManager()
            path = self._github_path(account_id)

            def _fetch():
                status, remote = mgr._request(
                    "GET",
                    f"contents/{path}",
                    params={"ref": mgr.github_branch},
                    allow_status=(404,),
                )
                if status == 404 or not remote.get("content"):
                    return None
                return base64.b64decode(remote["content"])

            raw = await asyncio.to_thread(_fetch)
            if raw is None:
                return None
            return self._fernet.decrypt(raw).decode()
        except Exception as e:
            logger.warning("GitHub vault retrieve failed for %s: %s", account_id, e)
            return None

    async def delete_github(self, account_id: str) -> bool:
        """Delete vault session from GitHub."""
        if not self._github_enabled:
            return False
        try:
            from .session_backup import SessionBackupManager

            mgr = SessionBackupManager()
            path = self._github_path(account_id)

            def _delete():
                return mgr._delete_file(path)

            deleted = await asyncio.to_thread(_delete)
            if deleted:
                logger.info(
                    "Vault session deleted from GitHub for account %s", account_id
                )
            return deleted
        except Exception as e:
            logger.warning("GitHub vault delete failed for %s: %s", account_id, e)
            return False

    async def exists_github(self, account_id: str) -> bool:
        if not self._github_enabled:
            return False
        try:
            from .session_backup import SessionBackupManager

            mgr = SessionBackupManager()
            path = self._github_path(account_id)

            def _check():
                status, _ = mgr._request(
                    "GET",
                    f"contents/{path}",
                    params={"ref": mgr.github_branch},
                    allow_status=(404,),
                )
                return status == 200

            return await asyncio.to_thread(_check)
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    #  Combined helpers                                                    #
    # ------------------------------------------------------------------ #

    async def store(
        self, user_id: int, account_id: str, phone: str, name: str, session_string: str
    ) -> bool:
        """Write vault session to MongoDB (primary) then GitHub (secondary, best-effort)."""
        mongo_ok = await self.store_mongo(user_id, account_id, phone, name, session_string)
        # GitHub is fire-and-forget — never block or surface failure to caller
        asyncio.create_task(self.store_github(account_id, session_string))
        return mongo_ok

    async def retrieve(self, user_id: int, account_id: str) -> Optional[str]:
        """Return vault session: MongoDB first, then GitHub."""
        session = await self.retrieve_mongo(user_id, account_id)
        if session:
            return session
        # Fallback to GitHub
        session = await self.retrieve_github(account_id)
        if session:
            # Repopulate MongoDB so it's primary again
            doc = await mongodb.db.vault_sessions.find_one(
                {"user_id": user_id, "account_id": account_id}, {"name": 1, "phone": 1}
            )
            phone_fallback = doc.get("phone", "") if doc else ""
            name_fallback = doc.get("name", account_id) if doc else account_id
            await self.store_mongo(
                user_id, account_id, phone_fallback, name_fallback, session
            )
            # Remove from GitHub now that it's in MongoDB
            asyncio.create_task(self.delete_github(account_id))
        return session

    async def delete(self, user_id: int, account_id: str) -> None:
        """Delete from both stores (user-initiated removal only)."""
        await self.delete_mongo(user_id, account_id)
        asyncio.create_task(self.delete_github(account_id))

    async def exists(self, user_id: int, account_id: str) -> bool:
        if await self.exists_mongo(user_id, account_id):
            return True
        return await self.exists_github(account_id)

    # ------------------------------------------------------------------ #
    #  Create a fresh vault session using the session-login machinery     #
    # ------------------------------------------------------------------ #

    async def create_and_store(
        self,
        bot_manager,
        user_id: int,
        account_id: str,
        phone: str,
        name: str,
    ) -> bool:
        """
        Create a brand-new independent session for `phone` via auto-OTP + stored 2FA
        and store it as the vault session.

        Uses OtpBypassContext to disable the OTP destroyer on ALL user accounts
        for the duration, then:
          _request_otp_code → poll 777000 → sign_in → twofa_helper if needed
        """
        if not self.enabled:
            return False

        session_login = getattr(bot_manager, "session_login_handler", None)
        if session_login is None:
            logger.warning("session_login_handler not available for vault creation")
            return False

        client = None

        try:
            from ..core.otp_protection import OtpBypassContext
            import time as _time

            async with OtpBypassContext(
                bot_manager, user_id, phone,
                duration_seconds=300, reason="vault_creation"
            ):
                otp_request_time = _time.time()

                client, phone_code_hash = await session_login._request_otp_code(phone)
                if not client or not phone_code_hash:
                    logger.warning("Could not request OTP for vault creation of %s", phone)
                    return False

                # Poll for OTP — only accept messages newer than the request
                otp_code = None
                for _ in range(15):
                    otp_code = await self._fetch_otp_after(
                        session_login, user_id, phone, otp_request_time
                    )
                    if otp_code:
                        break
                    await asyncio.sleep(2)

                if not otp_code:
                    otp_code = await self._fetch_otp_after(
                        session_login, user_id, phone, otp_request_time, window=300
                    )

                if not otp_code:
                    logger.warning("Could not auto-fetch OTP for vault session of %s", phone)
                    return False

                from telethon.errors import SessionPasswordNeededError
                from telethon.sessions import StringSession

                try:
                    await client.sign_in(phone, otp_code, phone_code_hash=phone_code_hash)
                    vault_session = StringSession.save(client.session)
                except SessionPasswordNeededError:
                    from .twofa_helper import twofa_helper
                    success, vault_session, error = await twofa_helper.try_sign_in_with_2fa(
                        client, user_id, phone
                    )
                    if not success:
                        logger.warning(
                            "2FA failed during vault creation for %s: %s", phone, error
                        )
                        return False

            # OtpBypassContext has exited — destroyer states restored
            await self.store(user_id, account_id, phone, name, vault_session)
            logger.info("Vault session created and stored for %s (%s)", name, phone)
            return True

        except Exception as e:
            logger.warning("Vault session creation failed for %s: %s", phone, e)
            return False
        finally:
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass

    @staticmethod
    async def _fetch_otp_after(
        session_login,
        user_id: int,
        phone: str,
        after_ts: float,
        window: float = 30,
    ) -> Optional[str]:
        """Fetch OTP from 777000 messages that arrived after `after_ts`."""
        import re
        import time as _time

        if user_id not in session_login.user_clients:
            return None

        current_time = _time.time()
        for client in session_login.user_clients[user_id].values():
            if not client or not client.is_connected():
                continue
            try:
                messages = await asyncio.wait_for(
                    client.get_messages(777000, limit=10), timeout=10.0
                )
                for msg in messages:
                    if not msg.message or not hasattr(msg, "date"):
                        continue
                    msg_ts = msg.date.timestamp()
                    if msg_ts < after_ts or (current_time - msg_ts) > window:
                        continue
                    text = msg.message
                    if "login code" not in text.lower() and "код" not in text.lower():
                        continue
                    match = re.search(r"Login code:\s*(\d{4,6})", text)
                    if not match:
                        match = re.search(r"\b(\d{5})\b", text)
                    if match:
                        return match.group(1)
            except Exception:
                continue
        return None


# Module-level singleton
session_vault = SessionVault()
