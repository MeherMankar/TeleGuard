"""Session Converter - Convert between Telethon, Pyrogram, and TData formats
Integrated from ConSes project
"""

import asyncio
import base64
import logging
import os
import shutil
import struct
import tempfile
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from opentele.td import TDesktop
    from opentele.tl import TelegramClient as OpenTeleClient
    from opentele.api import UseCurrentSession
    OPENTELE_AVAILABLE = True
except ImportError:
    OPENTELE_AVAILABLE = False
    logger.warning("opentele not installed - TData conversion unavailable")


class SessionConverter:
    """Convert sessions between different formats"""
    
    @staticmethod
    async def telethon_to_tdata(session_file: str, output_dir: str, proxy: Optional[dict] = None) -> Tuple[bool, str]:
        """Convert Telethon session to TData format"""
        if not OPENTELE_AVAILABLE:
            return False, "opentele library not installed. Install with: pip install opentele"
        
        try:
            session_name = os.path.splitext(os.path.basename(session_file))[0]
            logger.info(f"Converting {session_file} to TDesktop...")
            
            client = OpenTeleClient(session_file, proxy=proxy)
            tdesk = await client.ToTDesktop(flag=UseCurrentSession)
            
            os.makedirs(f"{output_dir}/{session_name}/tdata", exist_ok=True)
            tdesk.SaveTData(f"{output_dir}/{session_name}/tdata")
            
            logger.info(f"Successfully converted {session_file} to TDesktop")
            return True, f"Converted to {output_dir}/{session_name}/tdata"
        except Exception as e:
            logger.error(f"TData conversion failed: {e}")
            return False, f"Conversion failed: {str(e)}"
    
    @staticmethod
    async def telethon_to_pyrogram(session_file: str, output_dir: str) -> Tuple[bool, str]:
        """Convert Telethon session to Pyrogram format"""
        try:
            logger.info(f"Converting {session_file} to Pyrogram...")
            
            with open(session_file, 'rb') as f:
                data = f.read()
            
            dc_id, auth_key = struct.unpack('<i256s', data[:260])
            session_name = os.path.splitext(os.path.basename(session_file))[0]
            auth_key_b64 = base64.b64encode(auth_key).decode()
            pyrogram_string = f"1:dc{dc_id}:{auth_key_b64}"
            
            os.makedirs(output_dir, exist_ok=True)
            output_file = f"{output_dir}/{session_name}.session"
            with open(output_file, 'w') as f:
                f.write(pyrogram_string)
            
            logger.info(f"Successfully converted {session_file} to Pyrogram")
            return True, f"Converted to {output_file}"
        except Exception as e:
            logger.error(f"Pyrogram conversion failed: {e}")
            return False, f"Conversion failed: {str(e)}"
    
    @staticmethod
    async def tdata_to_telethon(tdata_folder: str, output_dir: str, proxy: Optional[dict] = None) -> Tuple[bool, str]:
        """Convert TData to Telethon session"""
        if not OPENTELE_AVAILABLE:
            return False, "opentele library not installed. Install with: pip install opentele"
        
        temp_tdata = "temp_tdata"
        try:
            logger.info(f"Converting {tdata_folder} to Telethon...")
            
            source_tdata = os.path.join(tdata_folder, 'tdata')
            if not os.path.exists(source_tdata):
                return False, f"tdata folder not found in {tdata_folder}"
            
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
            
            tdesk = TDesktop(temp_tdata)
            session_name = os.path.basename(os.path.dirname(source_tdata))
            
            os.makedirs(output_dir, exist_ok=True)
            output_file = f"{output_dir}/{session_name}.session"
            
            await tdesk.ToTelethon(session=output_file, proxy=proxy)
            
            logger.info(f"Successfully converted {tdata_folder} to Telethon")
            return True, f"Converted to {output_file}"
        except Exception as e:
            logger.error(f"TData to Telethon conversion failed: {e}")
            return False, f"Conversion failed: {str(e)}"
        finally:
            if os.path.exists(temp_tdata):
                shutil.rmtree(temp_tdata, ignore_errors=True)
    
    @staticmethod
    async def convert_batch(
        input_dir: str,
        output_dir: str,
        conversion_type: str,
        proxy: Optional[dict] = None
    ) -> dict:
        """Batch convert sessions
        
        Args:
            input_dir: Directory containing sessions to convert
            output_dir: Output directory
            conversion_type: 'to_tdata', 'to_pyrogram', or 'from_tdata'
            proxy: Optional proxy configuration
        
        Returns:
            dict with 'total', 'successful', 'failed' counts and 'results' list
        """
        stats = {'total': 0, 'successful': 0, 'failed': 0, 'results': []}
        
        try:
            if conversion_type == 'from_tdata':
                folders = [f for f in os.listdir(input_dir) if os.path.isdir(os.path.join(input_dir, f))]
                stats['total'] = len(folders)
                
                for folder in folders:
                    folder_path = os.path.join(input_dir, folder)
                    success, message = await SessionConverter.tdata_to_telethon(folder_path, output_dir, proxy)
                    
                    if success:
                        stats['successful'] += 1
                        stats['results'].append({'name': folder, 'status': 'success', 'message': message})
                    else:
                        stats['failed'] += 1
                        stats['results'].append({'name': folder, 'status': 'failed', 'message': message})
                    
                    await asyncio.sleep(1)
            else:
                session_files = [f for f in os.listdir(input_dir) if f.endswith('.session')]
                stats['total'] = len(session_files)
                
                for session_file in session_files:
                    file_path = os.path.join(input_dir, session_file)
                    
                    if conversion_type == 'to_tdata':
                        success, message = await SessionConverter.telethon_to_tdata(file_path, output_dir, proxy)
                    elif conversion_type == 'to_pyrogram':
                        success, message = await SessionConverter.telethon_to_pyrogram(file_path, output_dir)
                    else:
                        success, message = False, f"Unknown conversion type: {conversion_type}"
                    
                    if success:
                        stats['successful'] += 1
                        stats['results'].append({'name': session_file, 'status': 'success', 'message': message})
                    else:
                        stats['failed'] += 1
                        stats['results'].append({'name': session_file, 'status': 'failed', 'message': message})
                    
                    await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Batch conversion error: {e}")
        
        return stats
