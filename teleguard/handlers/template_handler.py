"""Advanced message template handler

Developed by:
- @Meher_Mankar
- @Gutkesh

GitHub: https://github.com/mehermankar/teleguard
Support: https://t.me/ContactXYZrobot
"""

import json
import logging
from telethon import events
from telethon.tl.custom import Button

logger = logging.getLogger(__name__)


class TemplateHandler:
    """Handles message template UI and operations"""
    
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.messaging_manager = bot_manager.messaging_manager
        self.pending_actions = {}
        
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup template-related handlers"""
        
        @self.bot.on(events.NewMessage(pattern=r"/templates"))
        async def templates_command(event):
            await self.show_main_menu(event)
        
        @self.bot.on(events.CallbackQuery(pattern=r"^template:"))
        async def handle_template_callback(event):
            user_id = event.sender_id
            data = event.data.decode("utf-8")
            
            try:
                if data == "template:main":
                    await self.show_main_menu(event)
                
                elif data == "template:create":
                    await self.show_create_menu(event)
                
                elif data == "template:create_text":
                    await self.start_text_template_creation(event)
                
                elif data == "template:create_media":
                    await self.start_media_template_creation(event)
                
                elif data == "template:view":
                    await self.show_view_menu(event)
                
                elif data == "template:categories":
                    await self.show_categories_menu(event)
                
                elif data.startswith("template:view_category:"):
                    category = data.replace("template:view_category:", "")
                    await self.show_templates_by_category(event, category)
                
                elif data.startswith("template:edit:"):
                    template_id = data.replace("template:edit:", "")
                    await self.show_template_details(event, template_id)
                
                elif data.startswith("template:delete:"):
                    template_id = data.replace("template:delete:", "")
                    await self.delete_template(event, template_id)
                
                elif data.startswith("template:use:"):
                    template_id = data.replace("template:use:", "")
                    await self.start_template_usage(event, template_id)
                
                elif data.startswith("template:select_account:"):
                    account_name = data.replace("template:select_account:", "")
                    await self.select_account_for_template(event, account_name)
                
            except Exception as e:
                logger.error(f"Template callback error: {e}")
                await event.answer("❌ Error processing request")
        
        @self.bot.on(events.NewMessage(pattern=r"^(?!/)"))
        async def handle_text_input(event):
            user_id = event.sender_id
            if user_id not in self.pending_actions:
                return
            
            action = self.pending_actions[user_id]
            if not action.get("type", "").startswith("template_"):
                return
            
            text = event.message.text
            
            if text.lower() in ["cancel", "/cancel"]:
                del self.pending_actions[user_id]
                await event.reply("❌ Operation cancelled", buttons=[[Button.inline("🔙 Back", "template:main")]])
                return
            
            await self.process_text_input(event, action, text)
    
    async def show_main_menu(self, event):
        """Show the main templates menu"""
        text = "📝 **Message Templates**\n\nManage your message templates with variables, media, and buttons."
        
        buttons = [
            [Button.inline("➕ Create Template", "template:create")],
            [Button.inline("📋 View Templates", "template:view")],
            [Button.inline("📁 Manage Categories", "template:categories")],
            [Button.inline("🔙 Back", "messaging:main")]
        ]
        
        if hasattr(event, 'edit'):
            await event.edit(text, buttons=buttons)
        else:
            await event.reply(text, buttons=buttons)
    
    async def show_create_menu(self, event):
        """Show template creation options"""
        text = "➕ **Create New Template**\n\nChoose template type:"
        
        buttons = [
            [Button.inline("📝 Text Template", "template:create_text")],
            [Button.inline("🖼️ Media Template", "template:create_media")],
            [Button.inline("🔙 Back", "template:main")]
        ]
        
        await event.edit(text, buttons=buttons)
    
    async def start_text_template_creation(self, event):
        """Start text template creation process"""
        user_id = event.sender_id
        
        self.pending_actions[user_id] = {
            "type": "template_create_text",
            "step": "name"
        }
        
        text = "📝 **Create Text Template**\n\nStep 1/4: Enter template name:"
        buttons = [[Button.inline("❌ Cancel", "template:main")]]
        
        await event.edit(text, buttons=buttons)
    
    async def start_media_template_creation(self, event):
        """Start media template creation process"""
        user_id = event.sender_id
        
        self.pending_actions[user_id] = {
            "type": "template_create_media",
            "step": "name"
        }
        
        text = "🖼️ **Create Media Template**\n\nStep 1/5: Enter template name:"
        buttons = [[Button.inline("❌ Cancel", "template:main")]]
        
        await event.edit(text, buttons=buttons)
    
    async def show_view_menu(self, event):
        """Show template viewing options"""
        user_id = event.sender_id
        
        categories = await self.messaging_manager.get_template_categories(user_id)
        templates = await self.messaging_manager.get_user_templates(user_id)
        
        text = f"📋 **View Templates** ({len(templates)} total)\n\nSelect category:"
        
        buttons = []
        for category in categories:
            category_templates = await self.messaging_manager.get_templates_by_category(user_id, category)
            buttons.append([Button.inline(f"📁 {category} ({len(category_templates)})", f"template:view_category:{category}")])
        
        buttons.append([Button.inline("🔙 Back", "template:main")])
        
        await event.edit(text, buttons=buttons)
    
    async def show_templates_by_category(self, event, category):
        """Show templates in a specific category"""
        user_id = event.sender_id
        
        templates = await self.messaging_manager.get_templates_by_category(user_id, category)
        
        text = f"📁 **{category} Templates** ({len(templates)} templates)\n\n"
        
        buttons = []
        for template in templates[:10]:  # Limit to 10 for UI
            preview = template["content"][:30] + "..." if len(template["content"]) > 30 else template["content"]
            buttons.append([Button.inline(f"📝 {template['name']}", f"template:edit:{template['_id']}")])
        
        if not templates:
            text += "No templates in this category."
        
        buttons.append([Button.inline("🔙 Back", "template:view")])
        
        await event.edit(text, buttons=buttons)
    
    async def show_template_details(self, event, template_id):
        """Show template details and options"""
        template = await self.messaging_manager.get_template(template_id)
        if not template:
            await event.answer("❌ Template not found")
            return
        
        text = f"📝 **{template['name']}**\n\n"
        text += f"**Category:** {template.get('category', 'General')}\n"
        text += f"**Content:** {template['content'][:100]}{'...' if len(template['content']) > 100 else ''}\n"
        
        if template.get('media_url'):
            text += f"**Media:** Yes\n"
        
        if template.get('buttons'):
            text += f"**Buttons:** {len(template['buttons'])} buttons\n"
        
        text += f"\n**Variables:** {{name}}, {{username}}, {{time}}, {{date}}"
        
        buttons = [
            [Button.inline("🚀 Use Template", f"template:use:{template_id}")],
            [Button.inline("🗑️ Delete", f"template:delete:{template_id}")],
            [Button.inline("🔙 Back", "template:view")]
        ]
        
        await event.edit(text, buttons=buttons)
    
    async def delete_template(self, event, template_id):
        """Delete a template"""
        success = await self.messaging_manager.delete_template(template_id)
        
        if success:
            await event.edit("✅ Template deleted successfully!", buttons=[[Button.inline("🔙 Back", "template:view")]])
        else:
            await event.edit("❌ Failed to delete template", buttons=[[Button.inline("🔙 Back", "template:view")]])
    
    async def start_template_usage(self, event, template_id):
        """Start template usage process"""
        user_id = event.sender_id
        
        # Get user accounts
        from ..core.mongo_database import mongodb
        from ..utils.data_encryption import DataEncryption
        
        encrypted_accounts = await mongodb.db.accounts.find({"user_id": user_id}).to_list(length=None)
        accounts = [DataEncryption.decrypt_account_data(acc) for acc in encrypted_accounts]
        
        if not accounts:
            await event.edit("❌ No accounts found", buttons=[[Button.inline("🔙 Back", "template:main")]])
            return
        
        self.pending_actions[user_id] = {
            "type": "template_use",
            "template_id": template_id,
            "step": "account"
        }
        
        text = "🚀 **Use Template**\n\nSelect account to send from:"
        
        buttons = []
        for account in accounts:
            buttons.append([Button.inline(f"📱 {account['name']}", f"template:select_account:{account['name']}")])
        
        buttons.append([Button.inline("🔙 Back", f"template:edit:{template_id}")])
        
        await event.edit(text, buttons=buttons)
    
    async def show_categories_menu(self, event):
        """Show categories management menu"""
        user_id = event.sender_id
        
        categories = await self.messaging_manager.get_template_categories(user_id)
        
        text = f"📁 **Template Categories** ({len(categories)} categories)\n\n"
        
        buttons = []
        for category in categories:
            templates = await self.messaging_manager.get_templates_by_category(user_id, category)
            buttons.append([Button.inline(f"📁 {category} ({len(templates)})", f"template:view_category:{category}")])
        
        buttons.append([Button.inline("🔙 Back", "template:main")])
        
        await event.edit(text, buttons=buttons)
    
    async def process_text_input(self, event, action, text):
        """Process text input for template creation"""
        user_id = event.sender_id
        
        if action["type"] == "template_create_text":
            await self.process_text_template_input(event, action, text)
        elif action["type"] == "template_create_media":
            await self.process_media_template_input(event, action, text)
        elif action["type"] == "template_use":
            await self.process_template_use_input(event, action, text)
    
    async def process_text_template_input(self, event, action, text):
        """Process text template creation input"""
        user_id = event.sender_id
        
        if action["step"] == "name":
            action["name"] = text
            action["step"] = "category"
            await event.reply("Step 2/4: Enter category (or 'General'):")
        
        elif action["step"] == "category":
            action["category"] = text if text else "General"
            action["step"] = "content"
            await event.reply("Step 3/4: Enter template content:\n\nAvailable variables: {name}, {username}, {time}, {date}")
        
        elif action["step"] == "content":
            action["content"] = text
            action["step"] = "buttons"
            await event.reply("Step 4/4: Enter buttons (JSON format) or 'skip':\n\nExample: [{\"text\": \"Visit\", \"url\": \"https://example.com\"}]")
        
        elif action["step"] == "buttons":
            buttons = []
            if text.lower() != "skip":
                try:
                    buttons = json.loads(text)
                except:
                    await event.reply("❌ Invalid JSON format. Try again or type 'skip':")
                    return
            
            # Create template
            try:
                template_id = await self.messaging_manager.create_template(
                    user_id=user_id,
                    name=action["name"],
                    content=action["content"],
                    category=action["category"],
                    buttons=buttons
                )
                
                del self.pending_actions[user_id]
                await event.reply(f"✅ Text template '{action['name']}' created successfully!", 
                                buttons=[[Button.inline("🔙 Back", "template:main")]])
                
            except Exception as e:
                await event.reply(f"❌ Failed to create template: {e}")
    
    async def process_media_template_input(self, event, action, text):
        """Process media template creation input"""
        user_id = event.sender_id
        
        if action["step"] == "name":
            action["name"] = text
            action["step"] = "category"
            await event.reply("Step 2/5: Enter category (or 'General'):")
        
        elif action["step"] == "category":
            action["category"] = text if text else "General"
            action["step"] = "media_url"
            await event.reply("Step 3/5: Enter media URL (image/video):")
        
        elif action["step"] == "media_url":
            action["media_url"] = text
            action["step"] = "content"
            await event.reply("Step 4/5: Enter caption/content:\n\nAvailable variables: {name}, {username}, {time}, {date}")
        
        elif action["step"] == "content":
            action["content"] = text
            action["step"] = "buttons"
            await event.reply("Step 5/5: Enter buttons (JSON format) or 'skip':\n\nExample: [{\"text\": \"Visit\", \"url\": \"https://example.com\"}]")
        
        elif action["step"] == "buttons":
            buttons = []
            if text.lower() != "skip":
                try:
                    buttons = json.loads(text)
                except:
                    await event.reply("❌ Invalid JSON format. Try again or type 'skip':")
                    return
            
            # Create template
            try:
                template_id = await self.messaging_manager.create_template(
                    user_id=user_id,
                    name=action["name"],
                    content=action["content"],
                    category=action["category"],
                    media_url=action["media_url"],
                    buttons=buttons
                )
                
                del self.pending_actions[user_id]
                await event.reply(f"✅ Media template '{action['name']}' created successfully!", 
                                buttons=[[Button.inline("🔙 Back", "template:main")]])
                
            except Exception as e:
                await event.reply(f"❌ Failed to create template: {e}")
    
    async def process_template_use_input(self, event, action, text):
        """Process template usage input"""
        user_id = event.sender_id
        
        if action["step"] == "target":
            # Send template
            success = await self.messaging_manager.send_template(
                user_id=user_id,
                account_name=action["account_name"],
                target=text,
                template_id=action["template_id"]
            )
            
            del self.pending_actions[user_id]
            
            if success:
                await event.reply("✅ Template sent successfully!", 
                                buttons=[[Button.inline("🔙 Back", "template:main")]])
            else:
                await event.reply("❌ Failed to send template", 
                                buttons=[[Button.inline("🔙 Back", "template:main")]])
    
    async def select_account_for_template(self, event, account_name):
        """Handle account selection for template usage"""
        user_id = event.sender_id
        
        if user_id not in self.pending_actions:
            await event.answer("❌ Session expired")
            return
        
        action = self.pending_actions[user_id]
        action["account_name"] = account_name
        action["step"] = "target"
        
        text = f"🚀 **Use Template**\n\nAccount: {account_name}\n\nEnter target (username, phone, or user ID):"
        buttons = [[Button.inline("❌ Cancel", "template:main")]]
        
        await event.edit(text, buttons=buttons)
    
    async def get_template_selection_menu(self, user_id: int) -> tuple[str, list]:
        """Get template selection menu for messaging integration"""
        templates = await self.messaging_manager.get_user_templates(user_id)
        
        if not templates:
            return "No templates available", [[Button.inline("➕ Create Template", "template:create")]]
        
        text = f"📝 **Select Template** ({len(templates)} available)\n\n"
        buttons = []
        
        for template in templates[:10]:  # Limit to 10
            preview = template["content"][:30] + "..." if len(template["content"]) > 30 else template["content"]
            buttons.append([Button.inline(f"📝 {template['name']}", f"template:use:{template['_id']}")])
        
        buttons.append([Button.inline("🔙 Back", "messaging:main")])
        
        return text, buttons