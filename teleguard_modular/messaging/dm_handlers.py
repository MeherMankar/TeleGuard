"""Split from unified_dm.py - dm_handlers"""
                        me = await client.get_me()
                        if me.id == account_id:
                            return client
                    except Exception as e:
                        continue
        return None

    async def _get_or_create_topic(self, group_id: int, topic_title: str, sender_id: int, account_id: int):
        """Get existing topic or create new one"""
        try:
            topic_key = f"{sender_id}_{account_id}"
            
            existing_topic = await mongodb.db.dm_topics.find_one({
                "group_id": group_id,
                "topic_key": topic_key
            })
            
            if existing_topic:
                # Update topic title if names changed
                if existing_topic.get('topic_title') != topic_title:
                    try:
                        from telethon.tl.functions.channels import EditForumTopicRequest
                        await self.bot(EditForumTopicRequest(
                            channel=group_id,
                            topic_id=existing_topic['topic_id'],
                            title=topic_title
                        ))
                        await mongodb.db.dm_topics.update_one(
                            {"_id": existing_topic["_id"]},
                            {"$set": {"topic_title": topic_title}}
                        )
                    except Exception:
                        pass
                return existing_topic["topic_id"]
            
            logger.info(f"Creating new topic: '{topic_title}' in group {group_id}")
            
            from telethon.tl.functions.channels import CreateForumTopicRequest
            result = await self.bot(CreateForumTopicRequest(
                channel=group_id,
                title=topic_title,
                icon_color=0x6FB9F0,
                random_id=hash(topic_key) % (2**63)
            ))
            
            logger.debug(f"Topic creation result: {result}")
            
            topic_id = None
            if hasattr(result, 'updates') and result.updates:
                for update in result.updates:
                    if hasattr(update, 'message'):
                        if hasattr(update.message, 'id'):
                            topic_id = update.message.id
                            logger.info(f"Extracted topic_id from message.id: {topic_id}")
                            break
                        elif hasattr(update.message, 'reply_to') and hasattr(update.message.reply_to, 'reply_to_top_id'):
                            topic_id = update.message.reply_to.reply_to_top_id
                            logger.info(f"Extracted topic_id from reply_to_top_id: {topic_id}")
                            break
            
            if not topic_id and hasattr(result, 'updates'):
                for update in result.updates:
                    if hasattr(update, 'id'):
                        topic_id = update.id
                        logger.info(f"Extracted topic_id from update.id: {topic_id}")
                        break
            
            if not topic_id:
                logger.error(f"Failed to extract topic_id from result: {result}")
                return None
            
            # Save to database
            await mongodb.db.dm_topics.insert_one({
                "group_id": group_id,
                "topic_key": topic_key,
                "topic_id": topic_id,
                "topic_title": topic_title,
                "sender_id": sender_id,
                "account_id": account_id,
                "created_at": datetime.utcnow()
            })
            
            logger.info(f"✅ Created and saved topic: {topic_id} - '{topic_title}'")
            return topic_id
            
        except Exception as e:
            logger.error(f"Failed to create/get topic: {e}", exc_info=True)
            try:
                await BotLogger.log_error("Topic Creation Error", str(e)[:500], context=f"Group: {group_id}, Title: {topic_title}")
            except:
                pass
        return None
    
    async def setup_ai_automation_job(self, user_id: int, account_id: str, config: dict):
        """Setup AI automation job for account"""
        try:
            job_data = {
                "user_id": user_id,
                "account_id": account_id,
                "job_type": "ai_smart_reply",
                "job_config": json.dumps(config),
                "enabled": True,
                "created_at": datetime.utcnow(),
                "next_run": datetime.utcnow()
            }
            
            await mongodb.db.automation_jobs.insert_one(job_data)
            logger.info(f"AI automation job created for account {account_id}")
            
        except Exception as e:
            logger.error(f"Failed to create AI automation job: {e}")

    async def setup_new_client_handler(self, user_id: int, account_name: str, client):
        """Set up DM handler for a newly added client"""
        if client and client.is_connected():
            await self._setup_client_dm_handler(user_id, account_name, client)
            logger.info(f"✅ DM handler registered for new account: {account_name}")
    
    async def refresh_all_handlers(self):
        """Refresh all DM handlers - automatically called on startup and when adding accounts"""
        try:
            self.handled_clients.clear()
            await self.setup_dm_handlers()
            handler_count = len(self.handled_clients)
            logger.info(f"✅ Refreshed DM handlers: {handler_count} accounts registered")
        except Exception as e:
            logger.error(f"Failed to refresh DM handlers: {e}")
    
    async def _handle_ai_auto_reply(self, event, me, user_id: int):
        """Handle AI-powered auto-reply to DMs"""
        try:
            # Check if auto-reply is enabled for this user
            if not await self._is_auto_reply_enabled(user_id):
                return
            
            if not self.ai_model or not event.text:
                return
            
            # Generate AI response
            response = await self._ai_generate_dm_reply(event, me)
            if response:
                # Extremely realistic auto-reply behavior
                await self._simulate_human_auto_reply_behavior(event.client, event.chat_id, response)
                await event.reply(response)
                
                # Log auto-reply
                logger.info(f"AI auto-reply sent for account {me.id}")
                
        except Exception as e:
            logger.error(f"AI auto-reply error: {e}")
    
    async def _ai_analyze_message(self, message_text: str) -> dict:
        """AI analyzes incoming message for priority and context"""
        if not self.ai_model or not message_text:
            return {'priority': 'normal', 'summary': ''}
        
        try:
            prompt = f"""Analyze this Telegram DM for priority and context:

Message: "{message_text}"

Provide analysis in this format:
Priority: [urgent/high/normal/low]
Summary: [brief 1-line summary]
Category: [question/complaint/spam/business/personal/other]

Analysis:"""
            
            response = await asyncio.to_thread(self.ai_model.generate_content, prompt)
            analysis_text = response.text.strip()
            
            # Parse response
            analysis = {'priority': 'normal', 'summary': '', 'category': 'other'}
            for line in analysis_text.split('\n'):
                if line.startswith('Priority:'):
                    analysis['priority'] = line.split(':', 1)[1].strip().lower()
                elif line.startswith('Summary:'):
                    analysis['summary'] = f"📋 {line.split(':', 1)[1].strip()}\n"
                elif line.startswith('Category:'):
                    analysis['category'] = line.split(':', 1)[1].strip().lower()
            
            return analysis
            
        except Exception as e:
            logger.error(f"Message analysis error: {e}")
            return {'priority': 'normal', 'summary': ''}
    
    def _get_priority_indicator(self, analysis: dict) -> str:
        """Get priority indicator emoji based on analysis"""
        priority = analysis.get('priority', 'normal')
        if priority == 'urgent':
            return '🚨'
        elif priority == 'high':
            return '⚡'
        elif priority == 'low':
            return '📝'
        else:
            return '📨'
    
    async def _ai_generate_dm_reply(self, event, me) -> str:
        """Generate AI-powered DM reply"""
        if not self.ai_model:
            return None
        
        try:
            sender = await event.get_sender()
            sender_name = sender.first_name or 'User'
            
            prompt = f"""Generate a natural, helpful auto-reply to this DM:

From: {sender_name}
To: {me.first_name or 'User'}
Message: "{event.text}"

Guidelines:
1. Be friendly and professional
2. Acknowledge their message
3. Keep it concise (1-2 sentences)
4. Sound natural, not robotic
5. Offer help if appropriate

Auto-reply:"""
            
            response = await asyncio.to_thread(self.ai_model.generate_content, prompt)
            reply_text = response.text.strip()
            
            # Validate response
            if len(reply_text) > 300 or any(word in reply_text.lower() for word in ['ai', 'artificial', 'bot']):
                return None
            
            return reply_text
            
        except Exception as e:
            logger.error(f"AI DM reply generation error: {e}")
            return None
    
    async def _ai_enhance_reply(self, reply_text: str, sender_id: int, client) -> str:
        """AI-enhance manual reply for better communication"""
        if not self.ai_model:
            return None
        
        try:
            # Get conversation context
            messages = await client.get_messages(sender_id, limit=5)
            context = "\n".join([f"{msg.sender_id}: {msg.text or '[media]'}" for msg in messages if msg.text])
            
            prompt = f"""Enhance this reply to be more natural and effective:

Original reply: "{reply_text}"
Conversation context: {context[-200:]}

Guidelines:
1. Keep the core message intact
2. Make it sound more natural
3. Add appropriate tone
4. Maintain professionalism
5. Don't change the meaning

Enhanced reply:"""
            
            response = await asyncio.to_thread(self.ai_model.generate_content, prompt)
            enhanced = response.text.strip()
            
            # Validate enhancement
            if len(enhanced) > len(reply_text) * 2:
                return None
            
            return enhanced
            
        except Exception as e:
            logger.error(f"Reply enhancement error: {e}")
            return None
    
    async def _is_auto_reply_enabled(self, user_id: int) -> bool:
        """Check if auto-reply is enabled for user"""
        try:
            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            return user and user.get("ai_auto_reply_enabled", False)
        except Exception as e:
            logger.error(f"Auto-reply check error: {e}")
            return False
    
    async def _is_ai_enhancement_enabled(self, user_id: int) -> bool:
        """Check if AI enhancement is enabled for user"""
        try:
            user = await mongodb.db.users.find_one({"telegram_id": user_id})
            return user and user.get("ai_enhancement_enabled", False)
        except Exception as e:
            logger.error(f"AI enhancement check error: {e}")
            return False
    
    async def _simulate_human_reply_behavior(self, client, target, message: str):
        """Simulate extremely realistic human reply behavior"""
        try:
            # Brief thinking time
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Start typing
            async with client.action(target, 'typing'):
                typing_time = len(message) * random.uniform(0.05, 0.1)
                typing_time = max(1.0, min(typing_time, 5.0))
                await asyncio.sleep(typing_time)
            
            # Brief pause before sending
            await asyncio.sleep(random.uniform(0.3, 0.8))
        except Exception as e:
            logger.debug(f"Typing simulation error: {e}")
            await asyncio.sleep(random.uniform(0.5, 1.5))
    
    async def _simulate_human_auto_reply_behavior(self, client, chat_id, message: str):
        """Simulate realistic auto-reply behavior (more immediate but still human)"""
        try:
            # Brief moment to "see" the message
            await asyncio.sleep(random.uniform(0.3, 1.5))
            
