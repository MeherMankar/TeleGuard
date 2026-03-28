# TeleGuard - ConSes Integration Summary

## Features Integrated from ConSes

### 1. Session Converter Utility (`teleguard/utils/session_converter.py`)
**New utility module for session format conversion**

#### Features:
- **Telethon to TData**: Convert Telethon sessions to Telegram Desktop format
- **Telethon to Pyrogram**: Convert Telethon sessions to Pyrogram format  
- **TData to Telethon**: Convert Telegram Desktop sessions to Telethon format
- **Batch Conversion**: Process multiple sessions at once with progress tracking

#### Key Methods:
- `telethon_to_tdata()` - Convert single Telethon session to TData
- `telethon_to_pyrogram()` - Convert single Telethon session to Pyrogram
- `tdata_to_telethon()` - Convert TData folder to Telethon session
- `convert_batch()` - Batch process multiple sessions

### 2. TData Import Feature (Updated `session_login_handler.py`)

#### New Functionality:
- **TData ZIP Import**: Upload tdata folders as ZIP files
- **Automatic Conversion**: TData automatically converted to Telethon format
- **Multi-Account Support**: Import multiple TData sessions from single ZIP
- **Progress Tracking**: Real-time progress updates during import

#### User Interface Updates:
- Added "📦 Import TData (ZIP)" button to session import menu
- New TData import flow with instructions
- Availability check for opentele library
- Detailed error messages and troubleshooting

#### New Methods:
- `_start_tdata_import()` - Initialize TData import process
- `process_tdata_zip()` - Process uploaded TData ZIP file
- Integrated with existing session import workflow

### 3. Dependencies Added

#### New Requirements:
```
opentele>=1.15.1  # TData conversion library
tgcrypto>=1.2.5   # Cryptography for Pyrogram
```

## Usage

### For Users:

#### Import TData Sessions:
1. Go to **📱 Account Settings** → **🔐 Session Import**
2. Click **📦 Import TData (ZIP)**
3. Prepare your tdata folder:
   - Locate Telegram Desktop tdata folder
   - Compress entire tdata folder to ZIP
   - Send ZIP file to bot
4. Bot automatically:
   - Extracts ZIP
   - Converts TData to Telethon
   - Imports accounts
   - Cleans up temporary files

#### Session Conversion (Developer):
```python
from teleguard.utils.session_converter import SessionConverter

# Convert Telethon to TData
success, message = await SessionConverter.telethon_to_tdata(
    "session.session",
    "output_dir",
    proxy={"proxy_type": "socks5", "addr": "127.0.0.1", "port": 1080}
)

# Convert TData to Telethon
success, message = await SessionConverter.tdata_to_telethon(
    "tdata_folder",
    "output_dir",
    proxy=None
)

# Batch convert
stats = await SessionConverter.convert_batch(
    "input_dir",
    "output_dir",
    "to_tdata",  # or "to_pyrogram", "from_tdata"
    proxy=None
)
```

## Installation

### Install Optional Dependencies:
```bash
pip install opentele tgcrypto
```

### Without TData Support:
TeleGuard works without opentele. TData import will show:
```
❌ TData Import Unavailable
The opentele library is not installed.
```

## Technical Details

### Session Conversion Flow:
1. **TData → Telethon**:
   - Extract tdata folder from ZIP
   - Use opentele to load TDesktop session
   - Convert to Telethon format
   - Save as .session file
   - Import into TeleGuard

2. **Telethon → TData**:
   - Load Telethon session
   - Use opentele to convert
   - Generate TData directory structure
   - Package as archive

### Error Handling:
- Invalid ZIP format detection
- Missing tdata folder detection
- Unauthorized session handling
- Automatic cleanup on failure
- Detailed error messages

### Security:
- Temporary files deleted after processing
- Session data encrypted before storage
- Proxy support for conversions
- No session data logged

## Compatibility

### Supported Formats:
- ✅ Telethon sessions (.session files)
- ✅ Pyrogram sessions (.session files)
- ✅ TData (Telegram Desktop)
- ✅ Session strings (Telethon/Pyrogram)

### Platform Support:
- ✅ Windows
- ✅ Linux
- ✅ macOS
- ✅ Docker

## Benefits

### For Users:
- Import Telegram Desktop sessions easily
- No need to re-authenticate accounts
- Bulk import multiple accounts
- Preserve existing sessions

### For Developers:
- Reusable session converter utility
- Support for multiple session formats
- Clean API for conversions
- Batch processing capabilities

## Future Enhancements

### Planned Features:
- TData export (Telethon → TData)
- Direct Pyrogram session import
- Session format auto-detection
- Session validation before import
- Session backup/restore with format conversion

## Notes

- opentele library is optional but recommended for TData support
- TData conversion requires valid, authorized sessions
- Proxy support available for all conversions
- Batch operations include progress tracking and error reporting
