"""Selenium installation and setup checker"""

import logging
import sys
from typing import Dict, Any

logger = logging.getLogger(__name__)

def check_selenium_setup() -> Dict[str, Any]:
    """
    Check if Selenium and required dependencies are properly installed
    
    Returns:
        Dict with setup status and recommendations
    """
    result = {
        'selenium_available': False,
        'webdriver_manager_available': False,
        'chrome_available': False,
        'recommendations': [],
        'status': 'failed'
    }
    
    # Check Selenium
    try:
        import selenium
        result['selenium_available'] = True
        result['selenium_version'] = selenium.__version__
    except ImportError:
        result['recommendations'].append("Install Selenium: pip install selenium>=4.15.0")
    
    # Check WebDriver Manager
    try:
        import webdriver_manager
        result['webdriver_manager_available'] = True
    except ImportError:
        result['recommendations'].append("Install WebDriver Manager: pip install webdriver-manager>=4.0.0")
    
    # Check Chrome WebDriver
    if result['selenium_available']:
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service
            
            # Test Chrome driver installation
            options = Options()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            driver.quit()
            
            result['chrome_available'] = True
            
        except Exception as e:
            result['chrome_error'] = str(e)
            result['recommendations'].append("Install Chrome browser or check Chrome driver setup")
    
    # Determine overall status
    if result['selenium_available'] and result['webdriver_manager_available'] and result['chrome_available']:
        result['status'] = 'ready'
    elif result['selenium_available'] and result['webdriver_manager_available']:
        result['status'] = 'partial'
    else:
        result['status'] = 'failed'
    
    return result

def get_setup_instructions() -> str:
    """Get detailed setup instructions for Selenium"""
    return """
🔧 **Selenium Setup Instructions**

**1. Install Python Dependencies:**
```bash
pip install selenium>=4.15.0 webdriver-manager>=4.0.0
```

**2. Install Chrome Browser:**
- Windows: Download from https://www.google.com/chrome/
- Linux: `sudo apt-get install google-chrome-stable`
- macOS: Download from Chrome website

**3. Verify Installation:**
Run the following Python code to test:
```python
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

options = webdriver.ChromeOptions()
options.add_argument("--headless")
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)
print("Selenium setup successful!")
driver.quit()
```

**4. Common Issues:**
- **Permission errors**: Run as administrator/sudo
- **Chrome not found**: Ensure Chrome is in PATH
- **Driver issues**: Clear webdriver cache: `rm -rf ~/.wdm`

**5. Alternative Browsers:**
If Chrome doesn't work, try Firefox:
```bash
pip install selenium webdriver-manager
# Use Firefox instead of Chrome in the code
```
"""

async def diagnose_selenium_issue() -> str:
    """Diagnose common Selenium issues and provide solutions"""
    check_result = check_selenium_setup()
    
    if check_result['status'] == 'ready':
        return "✅ Selenium is properly configured and ready to use!"
    
    diagnosis = "🔍 **Selenium Diagnosis Results**\n\n"
    
    if not check_result['selenium_available']:
        diagnosis += "❌ Selenium not installed\n"
    else:
        diagnosis += f"✅ Selenium {check_result.get('selenium_version', 'unknown')} installed\n"
    
    if not check_result['webdriver_manager_available']:
        diagnosis += "❌ WebDriver Manager not installed\n"
    else:
        diagnosis += "✅ WebDriver Manager installed\n"
    
    if not check_result['chrome_available']:
        diagnosis += "❌ Chrome WebDriver not working\n"
        if 'chrome_error' in check_result:
            diagnosis += f"   Error: {check_result['chrome_error']}\n"
    else:
        diagnosis += "✅ Chrome WebDriver working\n"
    
    if check_result['recommendations']:
        diagnosis += "\n🛠️ **Recommended Actions:**\n"
        for i, rec in enumerate(check_result['recommendations'], 1):
            diagnosis += f"{i}. {rec}\n"
    
    diagnosis += f"\n📋 **Setup Instructions:**\n{get_setup_instructions()}"
    
    return diagnosis