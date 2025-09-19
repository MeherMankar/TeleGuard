# TeleGuard Public Encrypted Snapshots

This repository contains encrypted snapshots of the TeleGuard database for transparency and verification purposes.

## What are these files?

These are hourly encrypted snapshots of the TeleGuard bot database, allowing users to:
- Verify that backups are being created regularly
- Confirm data integrity and backup frequency
- Audit the backup system operation

## Encryption Details

### Method: AES-GCM (Advanced Encryption Standard - Galois/Counter Mode)
- **Algorithm**: AES-256-GCM
- **Key Size**: 256 bits (32 bytes)
- **Nonce Size**: 96 bits (12 bytes)
- **Authentication**: Built-in authenticated encryption

### File Format
```
[12-byte nonce][encrypted data][authentication tag]
```
All encoded in Base64 for safe text storage.

### Security Properties
- **Confidentiality**: Data is encrypted with AES-256
- **Integrity**: GCM mode provides authentication
- **Uniqueness**: Each encryption uses a random nonce
- **Forward Security**: Each snapshot uses a fresh nonce

## File Naming Convention

```
teleguard_snapshot_YYYYMMDD_HHMMSS.json.enc
```

Example: `teleguard_snapshot_20240101_120000.json.enc`
- Created on January 1, 2024 at 12:00:00 UTC
- Contains encrypted JSON snapshot data

## What's Inside? (When Decrypted)

The decrypted snapshots contain:

```json
{
  "meta": {
    "created_at": "2024-01-01T12:00:00.000000",
    "version": "1.0",
    "collections": ["users", "accounts", "backups_meta"],
    "total_records": 1234
  },
  "data": {
    "users": [...],
    "accounts": [...],
    "backups_meta": [...]
  }
}
```

**Note**: All sensitive data (session strings, passwords, personal info) is already encrypted at the database level before being included in snapshots.

## Decryption (For Authorized Personnel Only)

The encryption key is private and only available to authorized TeleGuard operators.

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import base64

def decrypt_snapshot(encrypted_file_path, key_bytes):
    with open(encrypted_file_path, 'rb') as f:
        encrypted_data = f.read()
    
    # Decode base64
    data = base64.b64decode(encrypted_data)
    
    # Extract nonce and ciphertext
    nonce = data[:12]
    ciphertext = data[12:]
    
    # Decrypt
    aesgcm = AESGCM(key_bytes)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    
    return plaintext.decode('utf-8')
```

## Verification Without Decryption

You can verify snapshots are being created regularly by:

1. **File Timestamps**: Check that new files appear hourly
2. **File Sizes**: Verify files are not empty or suspiciously small
3. **Base64 Validation**: Confirm files contain valid Base64 data
4. **Naming Convention**: Ensure files follow the expected naming pattern

```python
import base64
import os
from datetime import datetime

def verify_snapshot_file(filepath):
    """Verify snapshot file without decrypting"""
    # Check file exists and has content
    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        return False, "File missing or empty"
    
    # Check filename format
    filename = os.path.basename(filepath)
    if not filename.startswith('teleguard_snapshot_') or not filename.endswith('.json.enc'):
        return False, "Invalid filename format"
    
    # Check Base64 validity
    try:
        with open(filepath, 'rb') as f:
            content = f.read()
        base64.b64decode(content)
        return True, "Valid encrypted snapshot"
    except Exception as e:
        return False, f"Invalid Base64 content: {e}"
```

## Backup Schedule

- **Frequency**: Every hour at minute :00
- **Retention**: GitHub history is cleaned every 8 hours (only latest snapshot kept)
- **Location**: This repository's main branch under `/snapshots/` directory

## Security Notice

⚠️ **The encryption key is private and secure**
- Key is stored only in secure environment variables
- Key is never committed to any repository
- Key is not accessible through any public API
- Only authorized TeleGuard operators have access

## Questions?

For questions about the backup system or snapshot verification:
- **Support**: [Contact Support](https://t.me/ContactXYZrobot)
- **Documentation**: [TeleGuard Wiki](https://github.com/MeherMankar/TeleGuard/wiki)
- **Repository**: [GitHub](https://github.com/MeherMankar/TeleGuard)

---

**TeleGuard** - Professional Telegram Account Manager  
Developed by [@Meher_Mankar](https://t.me/Meher_Mankar) & [@Gutkesh](https://t.me/Gutkesh)