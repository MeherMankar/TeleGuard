"""
Session Converter - Multi-format session conversion utility
Supports: Telethon ↔ Pyrogram ↔ TData (Telegram Desktop)
Adapted from ConSes with TeleGuard integration
"""

import asyncio
import base64
import logging
import os
import shutil
import struct
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ConversionStats:
    """Track conversion statistics"""
    
    def __init__(self):
        self.total = 0
        self.successful = 0
        self.failed = 0
        self.start_time = datetime.now()
        self.errors: List[str] = []
    
    def add_success(self):
        self.successful += 1
    
    def add_failure(self, error: str):
        self.failed += 1
        self.errors.append(error)
    
    def get_summary(self) -> Dict:
        duration = (datetime.now() - self.start_time).total_seconds()
        return {
            "total": self.total,
            "successful": self.successful,
            "failed": self.failed,
            "duration_seconds": duration,
            "errors": self.errors[:10]  # Limit to 10 errors
        }


class SessionConverter:
    """Multi-format session converter"""
    
    @staticmethod
    async def telethon_to_pyrogram(session_file: str, output_dir: str = "pyrogram_sessions") -> Tuple[bool, str]:
        """Convert Telethon session to Pyrogram format"""
        try:
            with open(session_file, 'rb') as f:
                data = f.read()
            
            dc_id, auth_key = struct.unpack('<i256s', data[:260])
            session_name = Path(session_file).stem
            auth_key_b64 = base64.b64encode(auth_key).decode()
            pyrogram_string = f"1:dc{dc_id}:{auth_key_b64}"
            
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{session_name}.session")
            
            with open(output_file, 'w') as f:
                f.write(pyrogram_string)
            
            logger.info(f"Converted {session_name} to Pyrogram")
            return True, output_file
            
        except Exception as e:
            logger.error(f"Telethon to Pyrogram conversion failed: {e}")
            return False, str(e)
    
    @staticmethod
    async def telethon_to_tdata(session_file: str, proxy: Optional[Dict], output_dir: str = "tdata") -> Tuple[bool, str]:
        """Convert Telethon session to TData format"""
        try:
            # Requires opentele library
            try:
                from opentele.tl import TelegramClient
                from opentele.api import UseCurrentSession
            except ImportError:
                return False, "opentele library not installed (pip install opentele)"
            
            session_name = Path(session_file).stem
            
            client = TelegramClient(session_file, proxy=proxy)
            tdesk = await client.ToTDesktop(flag=UseCurrentSession)
            
            output_path = os.path.join(output_dir, session_name, "tdata")
            os.makedirs(output_path, exist_ok=True)
            tdesk.SaveTData(output_path)
            
            logger.info(f"Converted {session_name} to TData")
            return True, output_path
            
        except Exception as e:
            logger.error(f"Telethon to TData conversion failed: {e}")
            return False, str(e)
    
    @staticmethod
    async def tdata_to_telethon(tdata_folder: str, proxy: Optional[Dict], output_dir: str = "sessions") -> Tuple[bool, str]:
        """Convert TData to Telethon session"""
        temp_tdata = "temp_tdata_conversion"
        
        try:
            # Requires opentele library
            try:
                from opentele.td import TDesktop
            except ImportError:
                return False, "opentele library not installed (pip install opentele)"
            
            source_tdata = os.path.join(tdata_folder, 'tdata')
            if not os.path.exists(source_tdata):
                return False, f"tdata folder not found in {tdata_folder}"
            
            # Copy to temp directory
            if os.path.exists(temp_tdata):
                shutil.rmtree(temp_tdata)
            os.makedirs(temp_tdata, exist_ok=True)
            
            for item in os.listdir(source_tdata):
                source = os.path.join(source_tdata, item)
                dest = os.path.join(temp_tdata, item)
                if os.path.isfile(source):
                    shutil.copy2(source, dest)
                else:
                    shutil.copytree(source, dest, dirs_exist_ok=True)
            
            # Convert
            tdesk = TDesktop(temp_tdata)
            session_name = os.path.basename(os.path.dirname(source_tdata))
            
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{session_name}.session")
            
            await tdesk.ToTelethon(session=output_file, proxy=proxy)
            
            logger.info(f"Converted {session_name} from TData to Telethon")
            return True, output_file
            
        except Exception as e:
            error_msg = str(e)
            if "TDesktopUnauthorized" in error_msg:
                return False, "Session not authorized"
            logger.error(f"TData to Telethon conversion failed: {e}")
            return False, str(e)
            
        finally:
            if os.path.exists(temp_tdata):
                shutil.rmtree(temp_tdata, ignore_errors=True)
    
    @staticmethod
    async def batch_convert(
        input_files: List[str],
        conversion_type: str,
        proxies: Optional[List[Dict]] = None,
        progress_callback=None
    ) -> ConversionStats:
        """
        Batch convert multiple sessions
        
        Args:
            input_files: List of input file paths
            conversion_type: 'telethon_to_pyrogram', 'telethon_to_tdata', 'tdata_to_telethon'
            proxies: Optional list of proxy configs
            progress_callback: Optional callback(current, total, status)
        """
        stats = ConversionStats()
        stats.total = len(input_files)
        
        proxy_index = 0
        
        for i, input_file in enumerate(input_files):
            try:
                # Get proxy if available
                proxy = None
                if proxies and len(proxies) > 0:
                    proxy = proxies[proxy_index % len(proxies)]
                    proxy_index += 1
                
                # Progress callback
                if progress_callback:
                    await progress_callback(i + 1, stats.total, f"Converting {Path(input_file).name}")
                
                # Convert based on type
                if conversion_type == 'telethon_to_pyrogram':
                    success, result = await SessionConverter.telethon_to_pyrogram(input_file)
                elif conversion_type == 'telethon_to_tdata':
                    success, result = await SessionConverter.telethon_to_tdata(input_file, proxy)
                elif conversion_type == 'tdata_to_telethon':
                    success, result = await SessionConverter.tdata_to_telethon(input_file, proxy)
                else:
                    success, result = False, f"Unknown conversion type: {conversion_type}"
                
                if success:
                    stats.add_success()
                else:
                    stats.add_failure(f"{Path(input_file).name}: {result}")
                
                # Small delay between conversions
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Batch conversion error for {input_file}: {e}")
                stats.add_failure(f"{Path(input_file).name}: {str(e)}")
        
        return stats
