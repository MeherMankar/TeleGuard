# 🌐 Proxy Management System

Complete proxy management for TeleGuard with support for Telegram proxy links and per-account proxy assignment.

---

## ✨ Features

### Proxy Support
- ✅ **Telegram Proxy Links** - Direct import from t.me/proxy and tg://proxy links
- ✅ **MTProto Proxies** - Native Telegram proxy protocol
- ✅ **SOCKS5 Proxies** - Standard SOCKS5 with authentication
- ✅ **HTTP Proxies** - HTTP/HTTPS proxy support
- ✅ **Manual Format** - Standard proxy URL format

### Management
- ✅ **Add Proxies** - Import from links or manual entry
- ✅ **Test Proxies** - Connection testing with response time
- ✅ **Assign to Accounts** - Per-account proxy configuration
- ✅ **Remove Proxies** - Clean proxy removal with account updates
- ✅ **Proxy List** - View all proxies with status indicators

### Status Tracking
- ✅ **Working** - Proxy tested and functional
- ✅ **Failed** - Connection failed
- ✅ **Timeout** - Connection timeout
- ✅ **Untested** - Not yet tested

---

## 🚀 Quick Start

### Access Proxy Manager

```
1. Open TeleGuard bot
2. Click "🌐 Proxy Manager" button
3. Or type "Proxy Manager" in chat
```

### Add a Proxy

**From Telegram Channel:**
```
1. Copy proxy link from channel (t.me/proxy?server=...)
2. Click "➕ Add Proxy"
3. Paste the link
4. Bot automatically tests the proxy
```

**Manual Entry:**
```
Format: socks5://user:pass@host:port
Example: socks5://admin:password123@1.2.3.4:1080
```

### Assign to Account

```
1. Click "🔗 Assign to Account"
2. Select account
3. Choose proxy from list
4. Restart account to apply
```

---

## 📋 Supported Formats

### Telegram Proxy Links

**MTProto (t.me/proxy):**
```
t.me/proxy?server=1.2.3.4&port=443&secret=abc123def456
tg://proxy?server=1.2.3.4&port=443&secret=abc123def456
```

**SOCKS5 (t.me/socks):**
```
t.me/socks?server=1.2.3.4&port=1080&user=admin&pass=password
tg://socks?server=1.2.3.4&port=1080&user=admin&pass=password
```

### Manual Formats

**SOCKS5:**
```
socks5://user:pass@1.2.3.4:1080
socks5://1.2.3.4:1080  (no auth)
```

**HTTP:**
```
http://user:pass@1.2.3.4:8080
http://1.2.3.4:8080  (no auth)
```

**MTProto:**
```
mtproto://1.2.3.4:443:secret
```

---

## 🎯 Use Cases

### 1. Multi-Account Safety
```
Problem: Running multiple accounts from same IP = ban risk
Solution: Assign different proxy to each account
Result: Each account appears from different location
```

### 2. Geo-Restricted Content
```
Problem: Content blocked in your country
Solution: Use proxy from allowed country
Result: Access restricted channels/groups
```

### 3. Ban Avoidance
```
Problem: IP banned from Telegram
Solution: Route through clean proxy
Result: Continue using Telegram normally
```

### 4. Privacy Protection
```
Problem: Don't want to expose real IP
Solution: All traffic through proxy
Result: Your real IP stays hidden
```

---

## 📊 Proxy Status Indicators

| Emoji | Status | Meaning |
|-------|--------|---------|
| ✅ | Working | Tested and functional |
| ❌ | Failed | Connection failed |
| ⏱️ | Timeout | Connection timeout |
| ❓ | Untested | Not yet tested |
| 🌐 | Assigned | Currently assigned to account |
| ⚪ | No Proxy | Account has no proxy |

---

## 🔧 Advanced Usage

### Proxy Rotation

```python
# Manually rotate proxies for account
1. Go to "👥 View Accounts"
2. See current proxy assignments
3. Click account to change proxy
4. Select new proxy
5. Restart account
```

### Bulk Assignment

```
Coming soon: Assign proxies to multiple accounts at once
```

### Proxy Health Monitoring

```
- Automatic health checks every 5 minutes
- Failed proxies marked automatically
- Notifications for proxy failures
```

---

## 🛡️ Security Best Practices

### 1. Use Trusted Proxies Only
```
❌ Don't: Use free public proxies
✅ Do: Use paid/private proxies
Why: Public proxies can log your data
```

### 2. Match Proxy Location to Account
```
❌ Don't: US account with Russian proxy
✅ Do: US account with US proxy
Why: Reduces ban risk from location mismatch
```

### 3. Test Before Assigning
```
❌ Don't: Assign untested proxies
✅ Do: Test proxy first
Why: Avoid connection issues
```

### 4. Rotate Regularly
```
❌ Don't: Use same proxy forever
✅ Do: Rotate proxies monthly
Why: Reduces detection patterns
```

---

## 📝 Database Schema

### Proxies Collection

```javascript
{
  _id: ObjectId,
  user_id: Number,
  name: String,
  type: String,  // 'socks5', 'http', 'mtproto'
  server: String,
  port: Number,
  username: String,  // optional
  password: String,  // optional
  secret: String,    // for mtproto
  status: String,    // 'working', 'failed', 'timeout', 'untested'
  last_check: Number,  // timestamp
  response_time: Number,  // seconds
  created_at: Number
}
```

### Account Proxy Assignment

```javascript
{
  _id: ObjectId,
  user_id: Number,
  phone: String,
  proxy_id: String,  // ObjectId reference
  proxy_assigned_at: Number
}
```

---

## 🔍 Troubleshooting

### Proxy Test Fails

**Problem:** Proxy shows as "Failed" or "Timeout"

**Solutions:**
1. Check proxy is actually working (test in browser)
2. Verify credentials are correct
3. Check firewall isn't blocking connection
4. Try different proxy type (SOCKS5 vs HTTP)

### Account Won't Connect

**Problem:** Account disconnects after assigning proxy

**Solutions:**
1. Test proxy first before assigning
2. Check proxy supports Telegram protocol
3. Try removing proxy temporarily
4. Verify proxy location matches account region

### Slow Connection

**Problem:** Messages send slowly with proxy

**Solutions:**
1. Check proxy response time (should be <2s)
2. Try proxy closer to your location
3. Use premium proxy service
4. Test multiple proxies and choose fastest

---

## 🚀 Coming Soon

### Version 2.1
- [ ] Automatic proxy rotation
- [ ] Proxy pool management
- [ ] Geolocation matching
- [ ] Proxy performance analytics

### Version 2.2
- [ ] Bulk proxy import from file
- [ ] Proxy health monitoring dashboard
- [ ] Automatic failover to backup proxy
- [ ] Proxy usage statistics

---

## 💡 Tips & Tricks

### Finding Good Proxies

1. **Paid Services** (Recommended)
   - Bright Data
   - Smartproxy
   - Oxylabs
   - Cost: $50-200/month

2. **Telegram Channels**
   - Search "proxy" in Telegram
   - Join proxy channels
   - Test before using

3. **Self-Hosted**
   - Rent VPS ($5-10/month)
   - Install proxy software
   - Full control

### Optimal Setup

```
For 5 accounts:
- Account 1: US proxy (residential)
- Account 2: UK proxy (datacenter)
- Account 3: DE proxy (residential)
- Account 4: FR proxy (datacenter)
- Account 5: No proxy (your real IP)

Mix residential and datacenter for best results
```

---

## 📞 Support

**Issues:**
- GitHub: [Report Bug](https://github.com/yourusername/teleguard/issues)
- Telegram: @ContactXYZrobot

**Questions:**
- Check FAQ first
- Ask in community group
- Contact support

---

## ⚠️ Disclaimer

**Legal Notice:**

Proxy usage must comply with:
- ✅ Telegram Terms of Service
- ✅ Local laws and regulations
- ✅ Proxy provider terms
- ✅ Ethical usage guidelines

**The developers are not responsible for:**
- ❌ Misuse of proxy features
- ❌ Account bans from improper usage
- ❌ Legal issues from proxy usage
- ❌ Data logged by proxy providers

---

<div align="center">

**Made with ❤️ by the TeleGuard Team**

[⭐ Star on GitHub](https://github.com/yourusername/teleguard) • [📖 Documentation](https://github.com/yourusername/teleguard/wiki)

</div>
