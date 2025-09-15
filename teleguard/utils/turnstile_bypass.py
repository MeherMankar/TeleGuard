"""Cloudflare Turnstile bypass utilities"""

import asyncio
import logging
import random
from typing import Optional

logger = logging.getLogger(__name__)

class TurnstileBypass:
    """Specialized Cloudflare Turnstile bypass"""
    
    def __init__(self):
        self.max_attempts = 3
        self.wait_timeout = 30
    
    async def bypass_turnstile(self, driver) -> bool:
        """Attempt to bypass Cloudflare Turnstile challenge"""
        try:
            # Wait for page to load
            await asyncio.sleep(random.uniform(3, 5))
            
            # Check if already passed
            if await self._check_success(driver):
                return True
            
            # Try multiple bypass methods
            methods = [
                self._method_wait_and_click,
                self._method_javascript_trigger,
                self._method_iframe_interaction,
                self._method_passive_wait
            ]
            
            for method in methods:
                try:
                    success = await method(driver)
                    if success:
                        return True
                    await asyncio.sleep(random.uniform(2, 4))
                except Exception as e:
                    logger.debug(f"Turnstile method failed: {e}")
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"Turnstile bypass error: {e}")
            return False
    
    async def _check_success(self, driver) -> bool:
        """Check if challenge is already completed"""
        try:
            # Check URL for success indicators
            url = driver.current_url.lower()
            if any(word in url for word in ['success', 'complete', 'verified', 'passed']):
                return True
            
            # Check for absence of challenge elements
            challenge_selectors = [
                '.cf-turnstile',
                '[data-sitekey]',
                'iframe[src*="turnstile"]',
                '.challenge-form'
            ]
            
            for selector in challenge_selectors:
                try:
                    elements = driver.find_elements("css selector", selector)
                    if elements:
                        return False  # Challenge still present
                except:
                    continue
            
            # If no challenge elements found, likely successful
            return True
            
        except Exception:
            return False
    
    async def _method_wait_and_click(self, driver) -> bool:
        """Wait for Turnstile widget and attempt click"""
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            wait = WebDriverWait(driver, 15)
            
            # Look for Turnstile checkbox
            selectors = [
                "input[type='checkbox']",
                ".cf-turnstile input",
                "[data-sitekey] input",
                "iframe[src*='turnstile']"
            ]
            
            for selector in selectors:
                try:
                    element = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    
                    # Human-like interaction
                    await asyncio.sleep(random.uniform(1, 3))
                    
                    if selector.endswith('iframe'):
                        # Handle iframe
                        driver.switch_to.frame(element)
                        checkbox = driver.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
                        checkbox.click()
                        driver.switch_to.default_content()
                    else:
                        element.click()
                    
                    # Wait for processing
                    await asyncio.sleep(random.uniform(3, 6))
                    
                    return await self._check_success(driver)
                    
                except Exception:
                    continue
            
            return False
            
        except Exception as e:
            logger.debug(f"Wait and click method failed: {e}")
            return False
    
    async def _method_javascript_trigger(self, driver) -> bool:
        """Use JavaScript to trigger Turnstile completion"""
        try:
            # Wait for Turnstile to load
            await asyncio.sleep(random.uniform(2, 4))
            
            js_scripts = [
                # Try to trigger Turnstile callback
                """
                if (window.turnstile && window.turnstile.render) {
                    try {
                        const widgets = document.querySelectorAll('.cf-turnstile');
                        widgets.forEach(widget => {
                            if (widget.dataset.callback) {
                                window[widget.dataset.callback]('success');
                            }
                        });
                    } catch(e) {}
                }
                """,
                
                # Try to simulate successful verification
                """
                const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                checkboxes.forEach(cb => {
                    if (!cb.checked) {
                        cb.checked = true;
                        cb.dispatchEvent(new Event('change', {bubbles: true}));
                    }
                });
                """,
                
                # Try to remove challenge elements
                """
                const challenges = document.querySelectorAll('.cf-turnstile, [data-sitekey]');
                challenges.forEach(el => el.style.display = 'none');
                """
            ]
            
            for script in js_scripts:
                try:
                    driver.execute_script(script)
                    await asyncio.sleep(random.uniform(2, 4))
                    
                    if await self._check_success(driver):
                        return True
                        
                except Exception:
                    continue
            
            return False
            
        except Exception as e:
            logger.debug(f"JavaScript method failed: {e}")
            return False
    
    async def _method_iframe_interaction(self, driver) -> bool:
        """Interact with Turnstile iframe"""
        try:
            from selenium.webdriver.common.by import By
            
            # Find Turnstile iframes
            iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='turnstile'], iframe[src*='cloudflare']")
            
            for iframe in iframes:
                try:
                    driver.switch_to.frame(iframe)
                    
                    # Look for interactive elements
                    interactive_elements = driver.find_elements(By.CSS_SELECTOR, 
                        "input, button, [role='button'], [onclick], [data-callback]")
                    
                    for element in interactive_elements:
                        try:
                            if element.is_displayed() and element.is_enabled():
                                await asyncio.sleep(random.uniform(1, 2))
                                element.click()
                                await asyncio.sleep(random.uniform(2, 4))
                                break
                        except:
                            continue
                    
                    driver.switch_to.default_content()
                    
                    if await self._check_success(driver):
                        return True
                        
                except Exception:
                    driver.switch_to.default_content()
                    continue
            
            return False
            
        except Exception as e:
            logger.debug(f"Iframe method failed: {e}")
            return False
    
    async def _method_passive_wait(self, driver) -> bool:
        """Passively wait for Turnstile to complete automatically"""
        try:
            # Some Turnstile challenges complete automatically
            for i in range(self.wait_timeout):
                await asyncio.sleep(1)
                
                if await self._check_success(driver):
                    return True
                
                # Check every 5 seconds
                if i % 5 == 0:
                    # Simulate human activity
                    try:
                        driver.execute_script("window.scrollBy(0, 10);")
                    except:
                        pass
            
            return False
            
        except Exception as e:
            logger.debug(f"Passive wait method failed: {e}")
            return False