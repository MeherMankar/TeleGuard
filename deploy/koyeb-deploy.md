# Koyeb Deployment Guide - IP Stability Optimized

## 🎯 Prevent IP Changes on Koyeb

### Method 1: Configuration File (Recommended)
1. Use the included `koyeb.toml` configuration
2. Pins deployment to Frankfurt region (`fra`)
3. Sets minimum instances to 1 (prevents scaling to 0)

### Method 2: Koyeb CLI
```bash
# Deploy with region pinning
koyeb service create teleguard \
  --git github.com/yourusername/TeleGuard \
  --git-branch main \
  --instance-type nano \
  --region fra \
  --min-scale 1 \
  --max-scale 1 \
  --port 8000 \
  --env PORT=8000
```

### Method 3: Web Dashboard
1. Go to Koyeb dashboard
2. Create new service
3. **Important Settings:**
   - **Region**: Select single region (Frankfurt recommended)
   - **Scaling**: Set Min=1, Max=1
   - **Instance Type**: nano or micro
   - **Port**: 8000

## 🔧 Optimization Features

### Automatic Keep-Alive
- Prevents idle shutdown (main cause of IP changes)
- Light CPU activity every 5 minutes
- Memory optimization to prevent OOM restarts

### Region Pinning
- Forces deployment to single region
- Reduces chance of cross-region reassignment
- Frankfurt (`fra`) recommended for stability

### Process Optimization
- Higher process priority
- Optimized garbage collection
- Activity monitoring

## 📊 Monitoring

### Health Endpoints
- `GET /health` - Service health
- `GET /ip` - Current IP and change count

### Environment Variables
```bash
KOYEB_OPTIMIZATION_ENABLED=true
KOYEB_REGION=fra
KOYEB_KEEP_ALIVE=true
KOYEB_PREVENT_IDLE=true
```

## ⚠️ Important Notes

1. **Never scale to 0** - This forces IP reassignment
2. **Use single region** - Multi-region increases IP changes
3. **Keep service active** - Idle services get reassigned
4. **Monitor logs** - Check for restart patterns

## 🚀 Quick Deploy

1. Fork TeleGuard repository
2. Add `koyeb.toml` to root
3. Set environment variables in Koyeb dashboard
4. Deploy with region pinning

This configuration significantly reduces IP changes on Koyeb platform.