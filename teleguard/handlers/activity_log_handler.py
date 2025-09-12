"""Activity Log Handler for displaying simulator audit logs"""

import logging

from telethon import Button

from ..core.mongo_database import mongodb

logger = logging.getLogger(__name__)


async def show_activity_log(bot, user_id: int, account_id: str, message_id: int):
    """Show activity log for account"""
    try:
        from bson import ObjectId
        
        account = await mongodb.db.accounts.find_one({
            "_id": ObjectId(account_id),
            "user_id": user_id
        })

            if not account:
                await bot.send_message(user_id, "❌ Account not found")
                return

            # Get activity audit from MongoDB
            activities = account.get("activity_log", [])[-50:] if account else []

            if not activities:
                text = (
                    f"📋 **Activity Log: {account['name']}**\n\n"
                    f"No activities recorded in the last 4 hours.\n\n"
                    f"Activities are logged when simulation is enabled and running."
                )
            else:
                text = f"📋 **Activity Log: {account['name']}** (Last 4 hours)\n\n"

                # Show last 15 activities
                for activity in activities[-15:]:
                    time_str = activity.get("time_str", "??:??:??")
                    activity_type = activity.get("activity", "unknown")
                    details = activity.get("details", "No details")

                    # Format activity type for display
                    if activity_type == "view_random_entity":
                        icon = "👀"
                        action = "Viewed"
                    elif activity_type == "react_to_random_post":
                        icon = "👍"
                        action = "Reacted"
                    elif activity_type == "browse_profiles":
                        icon = "👤"
                        action = "Browsed"
                    elif activity_type == "vote_in_random_poll":
                        icon = "🗳️"
                        action = "Voted"
                    elif activity_type == "join_or_leave_public_channel":
                        icon = "🔄"
                        action = "Join/Leave"
                    elif activity_type == "session_start":
                        icon = "🎬"
                        action = "Session"
                    elif activity_type == "session_end":
                        icon = "🎬"
                        action = "Session"
                    elif activity_type == "simulation_enabled":
                        icon = "🟢"
                        action = "Enabled"
                    elif activity_type == "simulation_disabled":
                        icon = "🔴"
                        action = "Disabled"
                    else:
                        icon = "ℹ️"
                        action = activity_type.replace("_", " ").title()

                    # Truncate long details
                    if len(details) > 40:
                        details = details[:37] + "..."

                    text += f"{icon} {time_str}: {action} - {details}\n"

                if len(activities) > 15:
                    text += f"\n... and {len(activities) - 15} more activities"

            buttons = [
                [Button.inline("🔄 Refresh", f"simulate:log:{account_id}")],
                [Button.inline("🔙 Back", f"simulate:status:{account_id}")],
            ]

            await bot.edit_message(user_id, message_id, text, buttons=buttons)

    except Exception as e:
        logger.error(f"Show activity log error: {e}")
        text = "❌ Error loading activity log"
        buttons = [[Button.inline("🔙 Back", f"account:manage:{account_id}")]]
        await bot.edit_message(user_id, message_id, text, buttons=buttons)
