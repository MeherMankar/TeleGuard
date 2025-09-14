"""Advanced captcha bypass utilities"""

import asyncio
import logging
import random
import time
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class CaptchaBypass:
    """Advanced captcha bypass with multiple strategies"""
    
    def __init__(self):
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
    
    async def bypass_captcha(self, url: str, strategy: str = "auto") -> Dict[str, Any]:
        """
        Attempt to bypass captcha using various strategies
        
        Args:
            url: Captcha URL to bypass
            strategy: Bypass strategy ('selenium', 'requests', 'auto')
            
        Returns:
            Dict with success status and details
        """
        strategies = {
            'selenium': self._selenium_bypass,
            'requests': self._requests_bypass,
            'auto': self._auto_bypass
        }
        
        if strategy not in strategies:
            strategy = 'auto'
            
        try:
            return await strategies[strategy](url)
        except Exception as e:
            logger.error(f"Captcha bypass failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'method': strategy
            }
    
    async def _auto_bypass(self, url: str) -> Dict[str, Any]:
        """Try selenium bypass only for Telegram captcha"""
        try:
            result = await self._selenium_bypass(url)
            return result
        except Exception as e:
            logger.warning(f"Selenium bypass failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'method': 'auto'
            }
    
    async def _requests_bypass(self, url: str) -> Dict[str, Any]:
        """Bypass using HTTP requests - disabled for Telegram captcha"""
        return {
            'success': False,
            'error': 'Telegram captcha requires browser interaction',
            'method': 'requests'
        }
    
    async def _selenium_bypass(self, url: str) -> Dict[str, Any]:
        """Bypass using Selenium WebDriver with Telegram captcha handling"""
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.action_chains import ActionChains
            
        except ImportError:
            return {
                'success': False,
                'error': 'Selenium not available',
                'method': 'selenium'
            }
        
        driver = None
        try:
            chrome_options = Options()
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--allow-running-insecure-content")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument(f"--user-agent={random.choice(self.user_agents)}")
            chrome_options.add_argument("--window-size=1920,1080")
            
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                from selenium.webdriver.chrome.service import Service
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=chrome_options)
            except:
                driver = webdriver.Chrome(options=chrome_options)
            
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            driver.get(url)
            
            await asyncio.sleep(3)
            
            wait = WebDriverWait(driver, 15)
            
            # Cloudflare Turnstile handling
            try:
                from .turnstile_bypass import TurnstileBypass
                turnstile = TurnstileBypass()
                
                success = await turnstile.bypass_turnstile(driver)
                if success:
                    return {
                        'success': True,
                        'method': 'selenium',
                        'final_url': driver.current_url
                    }
                # Wait for Cloudflare challenge to load
                await asyncio.sleep(5)
                
                # Look for Cloudflare checkbox
                cf_selectors = [
                    "input[type='checkbox']",
                    ".cf-turnstile",
                    "[data-sitekey]",
                    ".challenge-form input[type='checkbox']",
                    "#challenge-form input[type='checkbox']"
                ]
                
                checkbox_clicked = False
                for selector in cf_selectors:
                    try:
                        checkbox = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                        # Human-like click
                        actions = ActionChains(driver)
                        actions.move_to_element(checkbox).pause(1).click().perform()
                        checkbox_clicked = True
                        await asyncio.sleep(3)
                        break
                    except:
                        continue
                
                # If checkbox not found, try JavaScript
                if not checkbox_clicked:
                    driver.execute_script("""
                        const checkbox = document.querySelector('input[type="checkbox"]');
                        if (checkbox) {
                            checkbox.click();
                        }
                    """)
                    await asyncio.sleep(3)
                
                # Wait for verification to complete
                await asyncio.sleep(5)
                
                # Look for "Go back to bot" or continue button
                button_selectors = [
                    "//button[contains(text(), 'Go back to bot')]",
                    "//button[contains(text(), 'Continue')]",
                    "//a[contains(text(), 'Go back to bot')]",
                    "//a[contains(@href, 't.me')]",
                    "button[type='submit']",
                    ".btn",
                    "button"
                ]
                
                for selector in button_selectors:
                    try:
                        if selector.startswith('//'):
                            button = driver.find_element(By.XPATH, selector)
                        else:
                            button = driver.find_element(By.CSS_SELECTOR, selector)
                        
                        if button.is_displayed():
                            actions = ActionChains(driver)
                            actions.move_to_element(button).pause(1).click().perform()
                            await asyncio.sleep(3)
                            break
                    except:
                        continue
                
                # Check if redirected back to Telegram
                await asyncio.sleep(3)
                if 't.me' in driver.current_url or 'telegram' in driver.current_url.lower():
                    return {
                        'success': True,
                        'method': 'selenium',
                        'final_url': driver.current_url
                    }
                
                # Try direct navigation to Telegram
                try:
                    telegram_links = driver.find_elements(By.XPATH, "//a[contains(@href, 't.me')]")
                    if telegram_links:
                        telegram_links[0].click()
                        await asyncio.sleep(3)
                        return {'success': True, 'method': 'selenium'}
                except:
                    pass
                
            except Exception as e:
                logger.debug(f"Captcha handling error: {e}")
            
            return {
                'success': False,
                'error': 'Captcha not solved',
                'method': 'selenium'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'method': 'selenium'
            }
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
    
    async def _try_auto_redirect(self, driver) -> bool:
        """Check if page auto-redirects to Telegram"""
        await asyncio.sleep(3)
        return 't.me' in driver.current_url or 'telegram' in driver.current_url.lower()
    
    async def _try_button_click(self, driver) -> bool:
        """Try clicking verification buttons"""
        wait = WebDriverWait(driver, 10)
        
        button_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            ".btn",
            ".button",
            "#verify",
            "#submit",
            "[onclick*='verify']",
            "[onclick*='submit']",
            "button:contains('Verify')",
            "button:contains('Continue')",
            "button:contains('Submit')"
        ]
        
        for selector in button_selectors:
            try:
                element = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                
                # Human-like click
                actions = ActionChains(driver)
                actions.move_to_element(element)
                await asyncio.sleep(random.uniform(0.5, 1.5))
                actions.click()
                actions.perform()
                
                await asyncio.sleep(random.uniform(2, 4))
                
                if 't.me' in driver.current_url or 'telegram' in driver.current_url.lower():
                    return True
                    
            except Exception:
                continue
        
        return False
    
    async def _try_form_submit(self, driver) -> bool:
        """Try submitting forms"""
        try:
            forms = driver.find_elements(By.TAG_NAME, "form")
            
            for form in forms:
                try:
                    # Fill any required fields with dummy data
                    inputs = form.find_elements(By.TAG_NAME, "input")
                    for input_elem in inputs:
                        input_type = input_elem.get_attribute("type")
                        if input_type in ["text", "email"]:
                            input_elem.clear()
                            input_elem.send_keys("user@example.com")
                        elif input_type == "checkbox":
                            if not input_elem.is_selected():
                                input_elem.click()
                    
                    # Submit form
                    form.submit()
                    await asyncio.sleep(3)
                    
                    if 't.me' in driver.current_url or 'telegram' in driver.current_url.lower():
                        return True
                        
                except Exception:
                    continue
            
        except Exception:
            pass
        
        return False
    
    async def _try_javascript_bypass(self, driver) -> bool:
        """Try JavaScript-based bypass"""
        js_scripts = [
            "document.querySelector('button, input[type=submit], .btn')?.click();",
            "document.forms[0]?.submit();",
            "window.location.href = 'https://t.me/spambot';",
            "if(window.continueVerification) window.continueVerification();",
            "if(window.verify) window.verify();",
            "document.querySelector('[onclick]')?.click();"
        ]
        
        for script in js_scripts:
            try:
                driver.execute_script(script)
                await asyncio.sleep(2)
                
                if 't.me' in driver.current_url or 'telegram' in driver.current_url.lower():
                    return True
                    
            except Exception:
                continue
        
        return False
    
    async def _try_iframe_bypass(self, driver) -> bool:
        """Try handling iframes"""
        try:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            
            for iframe in iframes:
                try:
                    driver.switch_to.frame(iframe)
                    
                    # Try clicking buttons in iframe
                    buttons = driver.find_elements(By.TAG_NAME, "button")
                    for button in buttons:
                        try:
                            button.click()
                            await asyncio.sleep(2)
                            
                            driver.switch_to.default_content()
                            
                            if 't.me' in driver.current_url or 'telegram' in driver.current_url.lower():
                                return True
                                
                        except Exception:
                            continue
                    
                    driver.switch_to.default_content()
                    
                except Exception:
                    driver.switch_to.default_content()
                    continue
            
        except Exception:
            pass
        
        return False

# Global instance
captcha_bypass = CaptchaBypass()