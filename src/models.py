"""
TeleGuard Database Models

Developed by:
- @Meher_Mankar
- @Gutkesh

GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from database import Base
from config import FERNET

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    accounts = relationship("Account", back_populates="owner")
    bots = relationship("Bot", back_populates="owner")
    co_owners = relationship("CoOwner", back_populates="user")
    sudo_users = relationship("SudoUser", back_populates="user")
    is_admin = Column(Boolean, default=False)
    # User settings fields
    otp_forward = Column(Boolean, default=True)
    otp_destroy = Column(Boolean, default=True)
    online_interval = Column(Integer, default=3600)
    # New UI fields
    developer_mode = Column(Boolean, default=False)
    main_menu_message_id = Column(Integer, nullable=True)

class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    session_string = Column(String, nullable=False)  # Encrypted session string
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="accounts")
    co_owners = relationship("CoOwner", back_populates="account")
    is_active = Column(Boolean, default=True)
    # Account-specific settings
    otp_forward = Column(Boolean, default=True)
    otp_destroy = Column(Boolean, default=True)
    online_interval = Column(Integer, default=3600)
    profile_first_name = Column(String, nullable=True)
    profile_last_name = Column(String, nullable=True)
    profile_bio = Column(String, nullable=True)
    # New OTP destroyer fields
    otp_destroyer_enabled = Column(Boolean, default=False)
    otp_destroyed_at = Column(String, nullable=True)  # ISO timestamp
    otp_destroyer_disable_auth = Column(String, nullable=True)  # Hashed password
    otp_audit_log = Column(String, default='[]')  # JSON string
    menu_message_id = Column(Integer, nullable=True)
    twofa_password = Column(String, nullable=True)  # Hashed 2FA password
    
    # Full client management fields
    profile_photo_id = Column(String, nullable=True)
    username = Column(String, nullable=True)
    about = Column(String, nullable=True)
    
    # Automation fields  
    online_maker_enabled = Column(Boolean, default=False)
    online_maker_interval = Column(Integer, default=3600)
    automation_rules = Column(String, default='[]')
    last_online_update = Column(String, nullable=True)
    
    # Session management
    session_health_check = Column(String, nullable=True)
    active_sessions_count = Column(Integer, default=0)
    last_session_check = Column(String, nullable=True)
    
    # Security and API
    login_alerts_enabled = Column(Boolean, default=True)
    webhook_url = Column(String, nullable=True)
    api_access_enabled = Column(Boolean, default=False)
    api_key_hash = Column(String, nullable=True)

    def encrypt_session(self, session: str):
        """Encrypt session string before storing"""
        # TODO: REVIEW - session export / session-file handling
        self.session_string = FERNET.encrypt(session.encode()).decode()

    def decrypt_session(self) -> str:
        """Decrypt stored session string"""
        # TODO: REVIEW - session export / session-file handling
        return FERNET.decrypt(self.session_string.encode()).decode()
    
    def get_audit_log(self) -> list:
        """Get audit log as list"""
        import json
        try:
            return json.loads(self.otp_audit_log or '[]')
        except:
            return []
    
    def add_audit_entry(self, entry: dict):
        """Add entry to audit log"""
        import json
        import time
        entry['timestamp'] = int(time.time())
        log = self.get_audit_log()
        log.append(entry)
        # Keep only last 100 entries
        if len(log) > 100:
            log = log[-100:]
        self.otp_audit_log = json.dumps(log)

class Bot(Base):
    __tablename__ = "bots"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    token = Column(String, nullable=False)  # Encrypted bot token
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="bots")
    is_active = Column(Boolean, default=True)

    def encrypt_token(self, token: str):
        self.token = FERNET.encrypt(token.encode()).decode()

    def decrypt_token(self) -> str:
        return FERNET.decrypt(self.token.encode()).decode()

class CoOwner(Base):
    __tablename__ = "co_owners"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    account_id = Column(Integer, ForeignKey("accounts.id"))
    user = relationship("User", back_populates="co_owners")
    account = relationship("Account", back_populates="co_owners")

class SudoUser(Base):
    __tablename__ = "sudo_users"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    account_id = Column(Integer, ForeignKey("accounts.id"))
    user = relationship("User", back_populates="sudo_users")
    account = relationship("Account")

class AutomationJob(Base):
    __tablename__ = "automation_jobs"
    
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id"))
    job_type = Column(String, nullable=False)
    job_config = Column(String, nullable=False)
    enabled = Column(Boolean, default=True)
    last_run = Column(String, nullable=True)
    next_run = Column(String, nullable=True)
    created_at = Column(String, nullable=True)
    
    account = relationship("Account")

class MessageTemplate(Base):
    __tablename__ = "message_templates"
    
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id"))
    name = Column(String, nullable=False)
    content = Column(String, nullable=False)
    media_path = Column(String, nullable=True)
    created_at = Column(String, nullable=True)
    
    account = relationship("Account")

class AuditEvent(Base):
    __tablename__ = "audit_events"
    
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    event_type = Column(String, nullable=False)
    event_data = Column(String, nullable=False)
    ip_address = Column(String, nullable=True)
    timestamp = Column(String, nullable=True)
    
    account = relationship("Account")
    user = relationship("User")
