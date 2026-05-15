"""
Bulk Import Handler - Import multiple sessions at once
Supports batch import from files, folders, and session strings
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Dict

from telethon import Button, events

from ..core.mongo_database import mongodb
from ..utils.session_converter import ConversionStats, SessionConverter

logger = logging.getLogger(__name__)


class BulkImportHandler:
    """Handle bulk session imports"""
    
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.bot = bot_manager.bot
        self.active_imports: Dict[int, Dict] = {}
    
    def register_handlers(self):
        """Register bulk import handlers"""
        
        @self.bot.on(events.CallbackQuery(pattern=b"bulk_import:(.+)"))
        async def handle_bulk_import(event):
            user_id = event.sender_id
            action = event.data.decode().split(":")[1]
            
            if action == "menu":
                await self._show_bulk_import_menu(event, user_id)
            elif action == "from_folder":
                await self._start_folder_import(event, user_id)
            elif action == "from_tdata":
                await self._start_tdata_import(event, user_id)
            elif action == "cancel":
                self.active_imports.pop(user_id, None)
                await event.edit("❌ Bulk import cancelled")
    
    async def _show_bulk_import_menu(self, event, user_id: int):
        """Show bulk import options"""
        text = (
            "📦 **Bulk Import Sessions**\n\n"
            "Import multiple Telegram sessions at once:\n\n"
            "**Available Options:**\n"
            "• **From Folder** - Import all .session files from a folder\n"
            "• **From TData** - Import Telegram Desktop sessions\n"
            "• **From List** - Paste multiple session strings\n\n"
            "⚠️ **Note:** Large imports may take several minutes"
        )
        
        buttons = [
            [Button.inline("📁 From Folder", b"bulk_import:from_folder")],
            [Button.inline("🖥 From TData", b"bulk_import:from_tdata")],
            [Button.inline("📝 From List", b"bulk_import:from_list")],
            [Button.inline("❌ Cancel", b"bulk_import:cancel")]
        ]
        
        await event.edit(text, buttons=buttons)
    
    async def _start_folder_import(self, event, user_id: int):
        """Start folder-based import"""
        await event.edit(
            "📁 **Folder Import**\n\n"
            "Please send the path to the folder containing .session files\n\n"
            "Example: `/sessions` or `C:\\Users\\Name\\sessions`\n\n"
            "Or send /cancel to abort"
        )
        
        self.active_imports[user_id] = {
            "type": "folder",
            "state": "waiting_path"
        }
    
    async def _start_tdata_import(self, event, user_id: int):
        """Start TData import"""
        await event.edit(
            "🖥 **TData Import**\n\n"
            "Please send the path to the folder containing TData folders\n\n"
            "Example: `/tdata` or `C:\\Users\\Name\\tdata`\n\n"
            "Each subfolder should contain a `tdata` directory\n\n"
            "Or send /cancel to abort"
        )
        
        self.active_imports[user_id] = {
            "type": "tdata",
            "state": "waiting_path"
        }
    
    async def process_folder_import(
        self,
        user_id: int,
        folder_path: str,
        conversion_type: str = "telethon"
    ) -> Dict:
        """
        Process bulk import from folder
        
        Returns:
            Dict with success count, failed count, and errors
        """
        try:
            # Validate folder
            if not os.path.exists(folder_path):
                return {"success": False, "error": "Folder not found"}
            
            # Find session files
            if conversion_type == "telethon":
                files = list(Path(folder_path).glob("*.session"))
            elif conversion_type == "tdata":
                # Find folders containing tdata subdirectory
                files = [
                    f for f in Path(folder_path).iterdir()
                    if f.is_dir() and (f / "tdata").exists()
                ]
            else:
                return {"success": False, "error": "Unknown conversion type"}
            
            if not files:
                return {"success": False, "error": "No session files found"}
            
            # Send progress message
            progress_msg = await self.bot.send_message(
                user_id,
                f"📦 **Starting bulk import**\n\n"
                f"Found {len(files)} sessions to import\n"
                f"This may take a few minutes...\n\n"
                f"Progress: 0/{len(files)}"
            )
            
            stats = ConversionStats()
            stats.total = len(files)
            
            imported_count = 0
            failed_count = 0
            errors = []
            
            # Process each file
            for i, file_path in enumerate(files):
                try:
                    # Update progress
                    if i % 5 == 0:  # Update every 5 files
                        await progress_msg.edit(
                            f"📦 **Bulk Import Progress**\n\n"
                            f"Processing: {file_path.name}\n"
                            f"Progress: {i + 1}/{len(files)}\n"
                            f"✅ Imported: {imported_count}\n"
                            f"❌ Failed: {failed_count}"
                        )
                    
                    # Convert if needed
                    if conversion_type == "tdata":
                        success, result = await SessionConverter.tdata_to_telethon(
                            str(file_path),
                            None,  # No proxy for now
                            "sessions"
                        )
                        if not success:
                            failed_count += 1
                            errors.append(f"{file_path.name}: {result}")
                            continue
                        session_file = result
                    else:
                        session_file = str(file_path)
                    
                    # Read session string
                    with open(session_file, 'r') as f:
                        session_string = f.read().strip()
                    
                    # Generate account name
                    account_name = file_path.stem
                    
                    # Check if account already exists
                    existing = await mongodb.db.accounts.find_one({
                        "user_id": user_id,
                        "name": account_name
                    })
                    
                    if existing:
                        account_name = f"{account_name}_{i}"
                    
                    # Add account
                    success = await self.bot_manager.add_user_account(
                        user_id,
                        account_name,
                        session_string
                    )
                    
                    if success:
                        imported_count += 1
                    else:
                        failed_count += 1
                        errors.append(f"{file_path.name}: Failed to add account")
                    
                    # Small delay to avoid rate limits
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error importing {file_path}: {e}")
                    failed_count += 1
                    errors.append(f"{file_path.name}: {str(e)}")
            
            # Final summary
            summary_text = (
                f"✅ **Bulk Import Complete**\n\n"
                f"📊 **Summary:**\n"
                f"• Total: {len(files)}\n"
                f"• ✅ Imported: {imported_count}\n"
                f"• ❌ Failed: {failed_count}\n\n"
            )
            
            if errors:
                summary_text += "**Errors (first 5):**\n"
                for error in errors[:5]:
                    summary_text += f"• {error}\n"
            
            await progress_msg.edit(summary_text)
            
            return {
                "success": True,
                "imported": imported_count,
                "failed": failed_count,
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"Bulk import failed: {e}")
            return {"success": False, "error": str(e)}
