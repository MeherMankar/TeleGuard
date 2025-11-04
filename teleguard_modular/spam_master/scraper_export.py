"""Split from contact_scraper.py - scraper_export"""
                "The automated process took too long.\n\n"
                "**What to do:**\n"
                "• Try /appeal again\n"
                "• Check @spambot manually\n"
                "• Use /appeal_help for guidance"
            )
            self.active_appeals.pop(user_id, None)

    async def _get_account_age_days(self, user_id: int = None, account_name: str = None) -> int:
        """Get specific account creation age in days"""
        try:
            from datetime import datetime, timezone
            
            # Get specific client if provided
            if user_id and account_name:
                client = await self._get_user_client(user_id, account_name)
                if client:
                    try:
                        # Ensure client is connected
                        if not client.is_connected():
                            await client.connect()
                        
                        me = await client.get_me()
                        if me and hasattr(me, 'date') and me.date:
                            # Handle timezone-aware datetime
                            creation_date = me.date
                            if creation_date.tzinfo is None:
                                creation_date = creation_date.replace(tzinfo=timezone.utc)
                            
                            now = datetime.now(timezone.utc)
                            age_days = (now - creation_date).days
                            
                            logger.info(f"✓ Account {account_name} age: {age_days} days ({age_days/365:.1f} years)")
                            return max(0, age_days)  # Ensure non-negative
                    except Exception as e:
                        logger.warning(f"Failed to get age for {account_name}: {e}")
            
            # Fallback: try any available client
            if user_id and user_id in self.bot_manager.user_clients:
                for client_name, client in self.bot_manager.user_clients[user_id].items():
                    try:
                        if client and client.is_connected():
                            me = await client.get_me()
                            if me and hasattr(me, 'date') and me.date:
                                creation_date = me.date
                                if creation_date.tzinfo is None:
                                    creation_date = creation_date.replace(tzinfo=timezone.utc)
                                
                                now = datetime.now(timezone.utc)
                                age_days = (now - creation_date).days
                                logger.info(f"✓ Fallback age from {client_name}: {age_days} days")
                                return max(0, age_days)
                    except Exception as e:
                        logger.debug(f"Fallback client {client_name} failed: {e}")
                        continue
            
            logger.warning(f"Could not determine account age for {account_name}, using default")
            return 365  # Default to 1 year if can't determine
            
        except Exception as e:
            logger.error(f"Error getting account age: {e}")
            return 365  # Default to 1 year

    async def _get_user_client(self, user_id: int, account_name: str = None):
        """Get specific user client by account name or first available"""
        try:
            user_clients = self.bot_manager.user_clients.get(user_id, {})
            # Safe logging - encode Unicode characters for display only
            try:
                safe_account_name = account_name.encode('ascii', errors='replace').decode('ascii') if account_name else None
                safe_keys = [k.encode('ascii', errors='replace').decode('ascii') for k in user_clients.keys()]
                logger.info(f"Looking for client '{safe_account_name}' among {len(user_clients)} clients")
                logger.info(f"Available client keys: {safe_keys}")
            except:
                pass  # Skip logging if encoding fails
            
            # If account name specified, try to find that specific client
            if account_name:
                # Try exact match first (use original Unicode name)
                client = user_clients.get(account_name)
                if client and client.is_connected():
                    return client
                
                # Try to find by checking all stored names for this account
                from ..core.mongo_database import mongodb
                try:
                    # Try multiple query patterns
                    account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
                    if not account:
                        account = await mongodb.db.accounts.find_one({"user_id": user_id, "display_name": account_name})
                    if not account:
                        account = await mongodb.db.accounts.find_one({"user_id": user_id, "phone": account_name})
                    if not account:
                        # Try case-insensitive search
                        account = await mongodb.db.accounts.find_one({
                            "user_id": user_id,
                            "name": {"$regex": f"^{account_name}$", "$options": "i"}
                        })
                    
                    if account:
                        # Try all possible client key variations
                        for key in ['phone', 'name', 'display_name', 'first_name']:
                            if key in account and account[key]:
                                client = user_clients.get(account[key])
                                if client and client.is_connected():
                                    return client
                except Exception as e:
                    logger.error(f"Database lookup error: {e}")
            
            # DON'T fallback if account_name was specified - return None to force error
            if account_name:
                try:
                    safe_account_name = account_name.encode('ascii', errors='replace').decode('ascii')
                    safe_keys = [k.encode('ascii', errors='replace').decode('ascii') for k in user_clients.keys()]
                    logger.error(f"Could not find client for specified account: {safe_account_name}")
                    logger.error(f"Available clients: {safe_keys}")
                except:
                    logger.error(f"Could not find client for account (Unicode name)")
                # Try case-insensitive match with original Unicode names
                for key, client in user_clients.items():
                    if key.lower() == account_name.lower() and client and client.is_connected():
                        return client
                return None
            
            # Only use fallback if no specific account was requested
            for name, client in user_clients.items():
                if client and client.is_connected():
                    logger.warning(f"Using fallback client: {name}")
                    return client
            return None
        except Exception as e:
            logger.error(f"Error getting user client: {e}")
            return None

    async def _notify_user(self, user_id: int, message: str):
        """Send notification to user"""
        try:
            await self.bot.send_message(user_id, message)
        except Exception as e:
            logger.error(f"Failed to notify user {user_id}: {e}")

    async def _start_appeal_for_account(self, user_id: int, account_name: str, context: str, event):
        """Start appeal process for specific account"""
        try:
            # Store account name in active appeals for tracking
            if user_id not in self.active_appeals:
                self.active_appeals[user_id] = {}
            self.active_appeals[user_id]['account_name'] = account_name
            self.active_appeals[user_id]['context'] = context
            self.active_appeals[user_id]['state'] = 'new'
            
            # Load account client if not already loaded
            client = await self._get_user_client(user_id, account_name)
            if not client:
                await event.respond("⏳ Loading account client...")
                # Get account from database
                from ..core.mongo_database import mongodb
                account = await mongodb.db.accounts.find_one({"user_id": user_id, "name": account_name})
                if not account or not account.get('session_string'):
                    await event.respond("❌ Account not found or no session available.")
                    return
                
                # Load the client
                try:
                    await self.bot_manager.start_user_client(user_id, account_name, account['session_string'])
                    await asyncio.sleep(2)
                    await event.respond("✅ Account loaded successfully!")
                    client = await self._get_user_client(user_id, account_name)
                    if not client:
                        await event.respond("❌ Failed to get loaded client.")
                        return
                except Exception as e:
                    error_str = str(e)
                    if 'E11000' in error_str or 'duplicate key' in error_str:
                        logger.info(f"Account {account_name} already loaded, continuing...")
                        client = await self._get_user_client(user_id, account_name)
                        if client:
                            await event.respond("✅ Account already loaded!")
                        else:
                            await event.respond("❌ Account exists but client not found.")
                            return
                    else:
                        logger.error(f"Failed to load account {account_name}: {e}")
                        await event.respond(
                            f"❌ Failed to load account\n\n"
                            f"The account may need re-authentication.\n"
                            f"Please remove and re-add it in Account Settings."
                        )
                        return
            
            # Start the appeal process directly
            await self._start_appeal_process(user_id)
            
        except Exception as e:
            logger.error(f"Start appeal for account error: {e}")
            await event.respond("❌ Error starting appeal process.")
    
    async def _simulate_human_message_composition(self, client, target, message: str):
        """Simulate realistic human message composition with word complexity analysis"""
        try:
            # Show typing indicator
            if len(message) > 20:
                try:
                    from telethon.tl.functions.messages import SetTypingRequest
                    from telethon.tl.types import SendMessageTypingAction
                    await client(SetTypingRequest(peer=target, action=SendMessageTypingAction()))
                except Exception:
                    pass
            
            # Analyze words and calculate realistic typing time
            words = message.split()
            total_typing_time = 0
            
            for word in words:
                # Base time for 37 WPM (1.62 seconds per word)
                base_time = 1.62
                
                # Adjust for word complexity
                word_lower = word.lower().strip('.,!?;:')
                
                # Longer words take more time
                if len(word_lower) > 8:
                    base_time *= 1.4  # 40% slower for long words
                elif len(word_lower) > 5:
                    base_time *= 1.2  # 20% slower for medium words
                
                # Complex/uncommon words take longer
                complex_words = ['restricted', 'legitimate', 'violation', 'communication', 'investigation', 
                               'unauthorized', 'verification', 'circumstances', 'misunderstanding', 'reconsider']
                if word_lower in complex_words:
                    base_time *= 1.3
                
                # Technical terms slower
                if word_lower in ['telegram', 'spambot', 'account', 'restrictions', 'appeal']:
                    base_time *= 1.1
                
                # Common words faster
                common_words = ['the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'man', 'new', 'now', 'old', 'see', 'two', 'way', 'who', 'boy', 'did', 'its', 'let', 'put', 'say', 'she', 'too', 'use']
                if word_lower in common_words:
                    base_time *= 0.8  # 20% faster for common words
                
                total_typing_time += base_time
            
            # Add thinking pauses for appeal composition
            thinking_time = random.uniform(3.0, 6.0)
            total_time = total_typing_time + thinking_time
            
            # Split into realistic segments with natural pauses
            segments = max(2, min(5, len(words) // 12))
            segment_time = total_time / segments
            
            for i in range(segments):
                await asyncio.sleep(segment_time)
                
                # Refresh typing indicator
                if i < segments - 1 and len(message) > 80:
                    try:
