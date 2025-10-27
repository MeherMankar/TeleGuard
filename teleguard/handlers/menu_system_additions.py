# Add these methods to the MenuSystem class in menu_system.py

async def _show_messaging_statistics(self, user_id: int, message_id: int):
    """Show messaging statistics"""
    try:
        if hasattr(self.account_manager, 'unified_messaging'):
            stats = await self.account_manager.unified_messaging.get_messaging_statistics(user_id)
            
            text = (
                "📊 **Messaging Analytics**\n\n"
                f"📤 **Total Messages:** {stats.get('total_messages_sent', 0)}\n"
                f"🤖 **Auto-Replies:** {stats.get('auto_replies_sent', 0)}\n"
                f"📱 **Active Accounts:** {stats.get('active_accounts', 0)}\n"
                f"📨 **DM Topics:** {stats.get('dm_topics_created', 0)}\n\n"
                "💡 **Tip:** Enable auto-reply for better engagement"
            )
        else:
            text = "📊 **Messaging Analytics**\n\n❌ Analytics is unavailable for messages"
        
        buttons = [[Button.inline("🔙 Back to Messaging", "menu:messaging")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    except Exception as e:
        logger.error(f"Error showing messaging statistics: {e}")
        text = "❌ Analytics is unavailable for messages"
        buttons = [[Button.inline("🔙 Back to Messaging", "menu:messaging")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

async def _show_message_history(self, user_id: int, message_id: int):
    """Show message history"""
    try:
        from ..services.messaging_stats import MessagingStats
        stats_service = MessagingStats()
        
        recent_messages = await stats_service.get_recent_messages(user_id, limit=10)
        
        if not recent_messages:
            text = "📋 **Message History**\n\n💭 No recent messages found."
        else:
            text = "📋 **Message History** (Last 10)\n\n"
            for msg in recent_messages:
                import time
                timestamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(msg.get('timestamp', 0)))
                target = msg.get('target', 'Unknown')
                msg_type = msg.get('type', 'message')
                emoji = "🤖" if msg_type == "auto_reply" else "📤"
                text += f"{emoji} {timestamp} → {target}\n"
        
        buttons = [[Button.inline("🔙 Back to Messaging", "menu:messaging")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    except Exception as e:
        logger.error(f"Error showing message history: {e}")
        text = "❌ Message history is unavailable"
        buttons = [[Button.inline("🔙 Back to Messaging", "menu:messaging")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)

async def _show_messaging_settings(self, user_id: int, message_id: int):
    """Show messaging system settings"""
    try:
        settings = await mongodb.db.auto_reply_settings.find_one({"user_id": user_id}) or {}
        
        keyword_enabled = settings.get('keyword_replies_enabled', False)
        time_based_enabled = settings.get('time_based_replies_enabled', False)
        
        text = (
            "⚙️ **Messaging System Settings**\n\n"
            f"🔑 **Keyword Replies:** {'✅ Enabled' if keyword_enabled else '❌ Disabled'}\n"
            f"⏰ **Time-Based Replies:** {'✅ Enabled' if time_based_enabled else '❌ Disabled'}\n\n"
            "**Configure:**\n"
            "• Auto-reply rules\n"
            "• Message templates\n"
            "• DM forwarding\n"
            "• Notification preferences\n\n"
            "Use the buttons below to manage settings."
        )
        
        buttons = [
            [Button.inline("🤖 Auto-Reply Settings", "auto_reply:main")],
            [Button.inline("📝 Template Settings", "template:main")],
            [Button.inline("📨 DM Reply Settings", "dm_reply:main")],
            [Button.inline("🔙 Back to Messaging", "menu:messaging")]
        ]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
    except Exception as e:
        logger.error(f"Error showing messaging settings: {e}")
        text = "❌ System settings is unavailable"
        buttons = [[Button.inline("🔙 Back to Messaging", "menu:messaging")]]
        await self.bot.edit_message(user_id, message_id, text, buttons=buttons)
