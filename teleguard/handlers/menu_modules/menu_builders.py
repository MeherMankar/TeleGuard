"""Menu button builders"""

from telethon import Button


class MenuBuilders:
    def __init__(self, menu_system):
        self.menu = menu_system

    def get_main_menu_keyboard(self, user_id):
        from ...core.config import ADMIN_IDS

        keyboard = [
            [Button.text("📱 Account Settings"), Button.text("🛡️ OTP Manager")],
            [Button.text("💬 Messaging"), Button.text("📢 Channels")],
            [Button.text("👥 Contacts"), Button.text("🎯 SpamMaster")],
            [Button.text("🧹 Cleanup"), Button.text("❓ Help")],
            [Button.text("🆘 Support")],
        ]
        if user_id in ADMIN_IDS:
            keyboard.append([Button.text("⚙️ Developer Panel")])
        return keyboard

    def get_account_menu_buttons(self, account_id, account=None):
        if account:
            online_status = account.get("online_maker_enabled", False)
            online_text = (
                "🔴 Stop Online Maker" if online_status else "✅ Start Online Maker"
            )
            sim_status = account.get("simulation_enabled", False)
            sim_text = "🔴 Stop Activity Sim" if sim_status else "✅ Start Activity Sim"
            has_2fa = account.get("twofa_password") is not None
            twofa_text = "🛡️ 2FA Settings" if has_2fa else "❌ 2FA Settings"
        else:
            online_text = "✅ Online Maker"
            sim_text = "❌ Activity Sim"
            twofa_text = "❌ 2FA Settings"
        return [
            [
                Button.inline("👤 Profile Settings", f"profile:manage:{account_id}"),
                Button.inline(twofa_text, f"2fa:status:{account_id}"),
            ],
            [
                Button.inline("🔐 Active Sessions", f"sessions:list:{account_id}"),
                Button.inline(online_text, f"online:toggle:{account_id}"),
            ],
            [
                Button.inline(sim_text, f"simulate:status:{account_id}"),
                Button.inline("📊 Sim Stats", f"simulate:stats:{account_id}"),
            ],
            [Button.inline("🔙 Back to Accounts", "menu:accounts")],
        ]

    def get_otp_account_buttons(self, account_id, account):
        destroyer_enabled = (
            account.get("otp_destroyer_enabled", False)
            if isinstance(account, dict)
            else getattr(account, "otp_destroyer_enabled", False)
        )
        forward_enabled = (
            account.get("otp_forward_enabled", False)
            if isinstance(account, dict)
            else getattr(account, "otp_forward_enabled", False)
        )
        has_password = (
            account.get("otp_destroyer_disable_auth")
            if isinstance(account, dict)
            else getattr(account, "otp_destroyer_disable_auth", None)
        )
        destroyer_text = (
            "❌ Disable Destroyer" if destroyer_enabled else "✅ Enable Destroyer"
        )
        destroyer_action = (
            f"otp:disable:{account_id}"
            if destroyer_enabled
            else f"otp:enable:{account_id}"
        )
        forward_text = "❌ Disable Forward" if forward_enabled else "✅ Enable Forward"
        forward_action = (
            f"otp:forward_disable:{account_id}"
            if forward_enabled
            else f"otp:forward_enable:{account_id}"
        )
        import time

        temp_active = False
        if account.get("otp_temp_passthrough", False):
            expiry = account.get("temp_passthrough_expiry", 0)
            if time.time() < expiry:
                temp_active = True
        temp_text = "❌ Stop Temp OTP" if temp_active else "⏰ Temp OTP (5min)"
        buttons = [
            [Button.inline(destroyer_text, destroyer_action)],
            [Button.inline(forward_text, forward_action)],
            [Button.inline(temp_text, f"otp:temp:{account_id}")],
        ]
        if has_password:
            buttons.append(
                [
                    Button.inline("🛡️ Change Password", f"otp_pwd:change:{account_id}"),
                    Button.inline("❌ Remove Password", f"otp_pwd:remove:{account_id}"),
                ]
            )
        else:
            buttons.append(
                [Button.inline("🛡️ Set Password", f"otp_pwd:set:{account_id}")]
            )
        buttons.extend(
            [
                [Button.inline("📊 Password Status", f"otp_pwd:status:{account_id}")],
                [Button.inline("🔙 Back to OTP Manager", "menu:otp")],
            ]
        )
        return buttons
