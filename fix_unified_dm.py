"""Fix for Unified DM Manager - Replace methods in unified_messaging.py"""

# Replace _verify_forum_enabled method (around line 620)
verify_forum_fixed = '''
    async def _verify_forum_enabled(self, admin_group_id: int) -> bool:
        """Verify forum is enabled for group"""
        try:
            chat_info = await self.bot.get_entity(admin_group_id)
            is_forum = getattr(chat_info, "forum", False)
            if not is_forum:
                logger.error(f"Group {admin_group_id} does not have Topics/Forum enabled")
            return is_forum
        except Exception as e:
            logger.error(f"Failed to verify forum for {admin_group_id}: {e}")
            return False
'''

# Replace _create_new_topic method (around line 635)
create_topic_fixed = '''
    async def _create_new_topic(self, admin_group_id: int, topic_title: str, sender_id: int, account_id: int, user_id: int) -> Optional[int]:
        """Create new forum topic"""
        try:
            result = await self.bot(functions.channels.CreateForumTopicRequest(
                channel=admin_group_id,
                title=topic_title,
                random_id=hash(f"{sender_id}_{account_id}_{user_id}"),
            ))
            if hasattr(result, "updates") and result.updates:
                for update in result.updates:
                    if hasattr(update, "message") and update.message:
                        logger.info(f"Created topic '{topic_title}' with ID {update.message.id}")
                        return update.message.id
                    elif hasattr(update, "id"):
                        logger.info(f"Created topic '{topic_title}' with ID {update.id}")
                        return update.id
            logger.error(f"Failed to extract topic ID from result: {result}")
            return None
        except Exception as e:
            logger.error(f"Failed to create topic '{topic_title}' in {admin_group_id}: {e}")
            return None
'''

print("INSTRUCTIONS:")
print("1. Open teleguard/handlers/unified_messaging.py")
print("2. Find _verify_forum_enabled method (around line 620)")
print("3. Replace it with the verify_forum_fixed code above")
print("4. Find _create_new_topic method (around line 635)")
print("5. Replace it with the create_topic_fixed code above")
print("\nOR run: python main.py and check logs/teleguard.log for errors")
