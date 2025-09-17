# 🚀 Koyeb Deployment Guide

Deploy TeleGuard to Koyeb's free tier with automatic scaling and health monitoring.

## 🎯 Quick Deploy

### Prerequisites
- [Koyeb CLI](https://www.koyeb.com/docs/cli) installed
- Git repository with TeleGuard code
- Telegram API credentials

### 1. Install Koyeb CLI
```bash
# macOS/Linux
curl -fsSL https://cli.koyeb.com/install.sh | sh

# Windows (PowerShell)
iwr https://cli.koyeb.com/install.ps1 -useb | iex
```

### 2. Login to Koyeb
```bash
koyeb auth login
```

### 3. Set Environment Variables
```bash
export API_ID="your_api_id"
export API_HASH="your_api_hash"
export BOT_TOKEN="your_bot_token"
export ADMIN_IDS="123456789,987654321"

# Optional
export MONGODB_URI="your_mongodb_connection_string"
export GITHUB_TOKEN="your_github_token"
```

### 4. Deploy
```bash
./deploy/koyeb.sh
```

## 🔧 Manual Configuration

### Create App via CLI
```bash
koyeb app init teleguard --git https://github.com/YourUsername/TeleGuard.git
```

### Configure Secrets
```bash
koyeb secrets create API_ID --value="your_api_id"
koyeb secrets create API_HASH --value="your_api_hash"
koyeb secrets create BOT_TOKEN --value="your_bot_token"
koyeb secrets create ADMIN_IDS --value="123456789,987654321"
```

### Deploy Service
```bash
koyeb service create teleguard-bot \
  --app teleguard \
  --git-repository https://github.com/YourUsername/TeleGuard.git \
  --git-branch main \
  --instance-type nano \
  --port 8080 \
  --env API_ID=@API_ID \
  --env API_HASH=@API_HASH \
  --env BOT_TOKEN=@BOT_TOKEN \
  --env ADMIN_IDS=@ADMIN_IDS \
  --env PORT=8080 \
  --env KOYEB_DEPLOYMENT=true
```

## 📊 Monitoring

### Check Status
```bash
koyeb service list
koyeb service describe teleguard-bot
```

### View Logs
```bash
koyeb logs teleguard-bot --follow
```

### Health Check
Your app will be available at: `https://your-app-name-your-org.koyeb.app/health`

## 🔄 Updates

### Redeploy
```bash
koyeb service redeploy teleguard-bot
```

### Update Environment Variables
```bash
koyeb secrets update API_ID --value="new_value"
koyeb service redeploy teleguard-bot
```

## 💰 Pricing

- **Free Tier**: 512MB RAM, 0.1 vCPU, 2.5GB storage
- **Nano Instance**: Perfect for TeleGuard bot
- **Auto-scaling**: Scales based on demand

## 🛠️ Troubleshooting

### Common Issues

#### 1. Build Failures
```bash
# Check build logs
koyeb logs teleguard-bot --type build

# Common fix: Update requirements.txt
git add config/requirements.txt
git commit -m "Update dependencies"
git push
```

#### 2. Health Check Failures
```bash
# Check if health endpoint responds
curl https://your-app.koyeb.app/health

# Should return: {"status": "healthy", "service": "teleguard"}
```

#### 3. Bot Not Responding
```bash
# Check runtime logs
koyeb logs teleguard-bot --type runtime

# Verify secrets are set
koyeb secrets list
```

#### 4. Database Connection Issues
```bash
# For MongoDB Atlas (recommended)
koyeb secrets create MONGODB_URI --value="mongodb+srv://..."

# For local SQLite (default)
# No additional configuration needed
```

### Debug Commands
```bash
# Service status
koyeb service describe teleguard-bot

# Recent deployments
koyeb deployment list --app teleguard

# Resource usage
koyeb metrics teleguard-bot
```

## 🔒 Security Best Practices

### Environment Variables
- Use Koyeb secrets for sensitive data
- Never commit credentials to Git
- Rotate tokens regularly

### Database Security
- Use MongoDB Atlas with authentication
- Enable IP whitelisting
- Use encrypted connections

### Network Security
- Koyeb provides HTTPS by default
- Health checks are publicly accessible
- Bot API endpoints are internal only

## 📈 Scaling

### Auto-scaling Configuration
```yaml
# .koyeb/app.yaml
services:
  - name: teleguard-bot
    scaling:
      min: 1
      max: 3
      targets:
        - type: cpu
          value: 70
        - type: memory
          value: 80
```

### Manual Scaling
```bash
koyeb service scale teleguard-bot --instances 2
```

## 🔗 Useful Links

- [Koyeb Documentation](https://www.koyeb.com/docs)
- [Koyeb CLI Reference](https://www.koyeb.com/docs/cli)
- [Koyeb Dashboard](https://app.koyeb.com)
- [TeleGuard Support](https://t.me/ContactXYZrobot)

## 📝 Notes

- Free tier includes 100GB bandwidth/month
- Apps sleep after 30 minutes of inactivity
- Health checks prevent sleeping
- Logs retained for 7 days on free tier
- Custom domains available on paid plans

---

**Need help?** Contact support at [t.me/ContactXYZrobot](https://t.me/ContactXYZrobot)