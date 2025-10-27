# Silent Telegram ID Collector

## Overview
The ID Collector is a background worker that silently collects Telegram IDs from all dialogs (groups, channels, personal chats) of managed accounts and sends them to admins without notifying users.

## Features
- **Silent Operation**: Runs in background without user notification
- **Comprehensive Collection**: Collects IDs from:
  - Personal chats
  - Groups (including participants)
  - Channels (including subscribers)
  - All managed accounts
- **Automatic Scheduling**: Runs every 6 hours automatically
- **CSV Export**: Saves collected IDs in CSV format
- **Admin Delivery**: Automatically sends to all configured admins

## How It Works

### Automatic Collection
The collector runs automatically every 6 hours:
1. Iterates through all managed user accounts
2. For each account, scans all dialogs
3. Collects entity IDs (users, groups, channels)
4. For groups/channels, also collects participant IDs (up to 1000 per entity)
5. Saves unique IDs to CSV file
6. Sends CSV to all admins
7. Cleans up temporary files

### Manual Collection
Admins can trigger collection manually using:
```
/collect_ids
```

## File Format
Generated CSV files have the format:
```
telegram_ids_YYYYMMDD_HHMMSS.csv
```

CSV structure:
```csv
telegram_id,collected_at
123456789,20250101_120000
987654321,20250101_120000
```

## Configuration
No additional configuration needed. The collector uses:
- Existing managed accounts from the bot
- Admin IDs from `ADMIN_IDS` environment variable

## Security
- **Silent**: Users are never notified about collection
- **Admin-Only**: CSV files only sent to configured admins
- **Temporary Files**: CSV files deleted after sending
- **Unique IDs**: Duplicates automatically removed

## Implementation Details

### Files Created
1. `teleguard/workers/id_collector.py` - Main collector worker
2. `teleguard/utils/anchor.csv` - Telegram ID anchor data for age estimation

### Integration Points
- Initialized in `bot_manager.py` during worker initialization
- Runs alongside other background workers
- Uses existing account manager and client connections

### Performance
- **Collection Interval**: 6 hours
- **Participant Limit**: 1000 per group/channel
- **Timeout Handling**: Graceful error handling for failed collections
- **Resource Usage**: Minimal - only active during collection

## Admin Commands
- `/collect_ids` - Manually trigger ID collection (admin only)

## Logs
Collection activity is logged at DEBUG level:
- Collection start/completion
- Number of IDs collected
- Errors during collection (if any)

## Notes
- Collection happens silently without any user-facing notifications
- Only active accounts are used for collection
- Failed collections for individual accounts don't stop the overall process
- CSV files are automatically cleaned up after sending

## Privacy Considerations
This feature collects Telegram IDs which are public information available to any account that can see the entity. However:
- Use responsibly and in compliance with applicable laws
- Respect Telegram's Terms of Service
- Only use for legitimate purposes
- Ensure proper data handling and storage
