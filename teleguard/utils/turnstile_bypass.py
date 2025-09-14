"""Cloudflare Turnstile bypass with human behavior simulation"""

import asyncio
import random
import time
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

class TurnstileBypass:
    """Handle Cloudflare Turnstile captcha with human-like behavior"""
    
    async def bypass_turnstile(self, driver):
        """Main Turnstile bypass method"""
        try:
            # Extended human behavior simulation
            await self._extended_human_simulation(driver)
            
            # Wait for invisible checks to complete
            await asyncio.sleep(random.uniform(8, 12))
            
            # Check if already passed (invisible mode)
            if await self._check_invisible_pass(driver):
                return True
            
            # Handle managed mode checkbox if present
            checkbox_element = await self._find_turnstile_checkbox(driver)
            if checkbox_element:
                await self._natural_checkbox_interaction(driver, checkbox_element)
                await asyncio.sleep(random.uniform(5, 8))
            
            # Click continue button
            await self._click_continue_button(driver)
            
            return 't.me' in driver.current_url
            
        except Exception:
            return False
    
    async def _find_turnstile_checkbox(self, driver):
        """Find Turnstile checkbox element"""
        selectors = [
            "iframe[src*='turnstile']",
            ".cf-turnstile",
            "[data-sitekey]",
            "input[type='checkbox']"
        ]
        
        for selector in selectors:
            try:
                if 'iframe' in selector:
                    iframe = driver.find_element(By.CSS_SELECTOR, selector)
                    driver.switch_to.frame(iframe)
                    return driver.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
                else:
                    return driver.find_element(By.CSS_SELECTOR, selector)
            except:
                if 'iframe' in selector:
                    driver.switch_to.default_content()
                continue
        return None
    
    async def _extended_human_simulation(self, driver):
        """Extended human behavior simulation for Turnstile"""
        try:
            # Natural page interaction
            await asyncio.sleep(random.uniform(1, 3))
            
            # Organic scrolling pattern
            for _ in range(random.randint(2, 4)):
                scroll_amount = random.randint(50, 200)
                driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
                await asyncio.sleep(random.uniform(0.8, 2.0))
            
            # Natural mouse movements with pauses
            actions = ActionChains(driver)
            for _ in range(random.randint(5, 8)):
                x = random.randint(50, 1000)
                y = random.randint(50, 700)
                actions.move_by_offset(random.randint(-50, 50), random.randint(-50, 50))
                await asyncio.sleep(random.uniform(0.2, 0.8))
            actions.perform()
            
            # Simulate reading time
            await asyncio.sleep(random.uniform(2, 5))
            
        except Exception:
            pass
    
    async def _check_invisible_pass(self, driver):
        """Check if Turnstile passed in invisible mode"""
        try:
            # Look for success indicators
            success_selectors = [
                "[data-cf-turnstile-response]",
                ".cf-turnstile[data-response]",
                "input[name='cf-turnstile-response'][value]"
            ]
            
            for selector in success_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    if element.get_attribute('value') or element.get_attribute('data-response'):
                        return True
                except:
                    continue
            
            return False
        except:
            return False
    
    async def _natural_checkbox_interaction(self, driver, element):
        """Natural checkbox interaction with pre-click behavior"""
        try:
            # Hover near checkbox first
            actions = ActionChains(driver)
            actions.move_to_element_with_offset(element, random.randint(-20, 20), random.randint(-20, 20))
            actions.pause(random.uniform(0.5, 1.0))
            
            # Move closer to checkbox
            actions.move_to_element_with_offset(element, random.randint(-5, 5), random.randint(-5, 5))
            actions.pause(random.uniform(0.3, 0.8))
            
            # Final click with slight offset
            actions.move_to_element_with_offset(element, random.randint(-2, 2), random.randint(-2, 2))
            actions.pause(random.uniform(0.1, 0.4))
            actions.click()
            actions.perform()
            
        except Exception:
            element.click()
    

    
    async def _click_continue_button(self, driver):
        """Find and click continue button"""
        selectors = [
            "//a[contains(text(), 'Go back to bot')]",
            "//button[contains(text(), 'Continue')]",
            "//a[contains(@href, 't.me')]",
            "button[type='submit']"
        ]
        
        for selector in selectors:
            try:
                button = driver.find_element(By.XPATH, selector)
                if button.is_displayed():
                    await self._human_like_click(driver, button)
                    await asyncio.sleep(2)
                    break
            except:
                continue