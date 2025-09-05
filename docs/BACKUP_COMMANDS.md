# Backup Commands - Execute Before Any Changes

## 1. Create Backup Branch (MANDATORY)
```bash
cd "d:\Vs code\tg bot"
git checkout -b backup/pre-fullclient-20250105
git add .
git commit -m "Pre-fullclient snapshot - Contains working OTP destroyer and session management"
```

## 2. Create Encrypted Archive of Sensitive Files
```bash
# Create archive of sensitive files
tar -czf sensitive_backup_20250105.tar.gz *.session* secret.key bot_data.db .env

# Encrypt the archive (you will be prompted for password)
gpg --symmetric --cipher-algo AES256 sensitive_backup_20250105.tar.gz

# Remove unencrypted archive
rm sensitive_backup_20250105.tar.gz

# The encrypted file will be: sensitive_backup_20250105.tar.gz.gpg
```

## 3. Create Feature Branch
```bash
git checkout -b feature/fullclient-20250105
```

## 4. Verify Backup
```bash
# Verify backup branch exists
git branch --list backup/pre-fullclient-*

# Verify encrypted archive
ls -la *.gpg

# Test decryption (optional)
# gpg --decrypt sensitive_backup_20250105.tar.gz.gpg > test_restore.tar.gz
```

## Recovery Instructions

### To restore from backup branch:
```bash
git checkout backup/pre-fullclient-20250105
git checkout -b recovery/restore-$(date +%Y%m%d)
```

### To restore sensitive files:
```bash
gpg --decrypt sensitive_backup_20250105.tar.gz.gpg > restore.tar.gz
tar -xzf restore.tar.gz
```

## Important Notes

- **NEVER DELETE** the backup branch
- Keep the encrypted archive in a secure location
- The backup contains the working OTP destroyer implementation
- All session files and encryption keys are preserved
- Database with existing accounts and audit logs is backed up