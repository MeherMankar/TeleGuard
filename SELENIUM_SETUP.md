# 🔧 Selenium Setup for TeleGuard Captcha Bypass

This guide helps you set up Selenium for automatic captcha bypass in TeleGuard's spam appeal system.

## 🚀 Quick Setup

### Option 1: Automated Setup (Recommended)
```bash
python setup_selenium.py
```

### Option 2: Manual Setup

1. **Install Python packages:**
   ```bash
   pip install selenium>=4.15.0 webdriver-manager>=4.0.0
   ```

2. **Install Chrome browser:**
   - **Windows**: Download from [Chrome website](https://www.google.com/chrome/)
   - **Linux**: `sudo apt-get install google-chrome-stable`
   - **macOS**: Download from Chrome website or `brew install --cask google-chrome`

3. **Test installation:**
   ```python
   from selenium import webdriver
   from webdriver_manager.chrome import ChromeDriverManager
   
   driver = webdriver.Chrome(ChromeDriverManager().install())
   print("Selenium working!")
   driver.quit()
   ```

## 🔍 Troubleshooting

### Common Issues

**"Selenium not available" error:**
```bash
pip install --upgrade selenium webdriver-manager
```

**Chrome driver issues:**
```bash
# Clear webdriver cache
rm -rf ~/.wdm  # Linux/macOS
rmdir /s %USERPROFILE%\.wdm  # Windows
```

**Permission errors:**
- Run terminal as administrator (Windows)
- Use `sudo` for Linux package installation

### Testing Your Setup

Use the bot command to check your setup:
```
/check_selenium
```

Or test manually:
```python
from teleguard.utils.selenium_check import diagnose_selenium_issue
import asyncio

async def test():
    result = await diagnose_selenium_issue()
    print(result)

asyncio.run(test())
```

## 🤖 Using Captcha Bypass

Once Selenium is set up:

1. **Start appeal process:**
   ```
   /appeal
   ```

2. **Check status:**
   ```
   /appeal_status
   ```

3. **If captcha bypass fails:**
   ```
   /continue_appeal
   ```

4. **Get help:**
   ```
   /appeal_help
   ```

## 🔄 How It Works

1. **Automatic Detection**: Bot detects captcha URLs from @spambot
2. **Browser Launch**: Selenium opens headless Chrome browser
3. **Captcha Solving**: Attempts to solve Cloudflare Turnstile captcha
4. **Fallback**: If automatic fails, provides manual instructions
5. **Completion**: Continues appeal process automatically

## 📋 System Requirements

- **Python**: 3.8+
- **Chrome**: Latest version
- **RAM**: 512MB+ available
- **Disk**: 100MB+ for Chrome driver

## 🛡️ Security Notes

- Selenium runs in headless mode (no visible browser)
- No personal data is sent to external services
- Only interacts with official Telegram captcha pages
- Chrome driver is downloaded from official sources

## 🆘 Getting Help

If you're still having issues:

1. **Check logs**: Look for detailed error messages
2. **Update dependencies**: `pip install --upgrade selenium webdriver-manager`
3. **Restart bot**: Sometimes a restart fixes connection issues
4. **Contact support**: Use `/appeal_help` for more guidance

## 🔗 Useful Links

- [Selenium Documentation](https://selenium-python.readthedocs.io/)
- [WebDriver Manager](https://github.com/SergeyPirogov/webdriver_manager)
- [Chrome Downloads](https://www.google.com/chrome/)
- [TeleGuard Wiki](https://github.com/MeherMankar/TeleGuard/wiki)