"""
End-to-End (E2E) tests
Tests complete user workflows from signup to chat interactions
Uses Selenium for browser automation
"""
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time


@pytest.fixture(scope='session')
def browser():
    """Create and teardown headless browser for E2E tests"""
    # Use headless Chrome for testing
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=options)
    driver.set_window_size(1024, 768)
    
    yield driver
    
    driver.quit()


@pytest.fixture
def live_server(browser):
    """Base URL for live server"""
    return 'http://127.0.0.1:8000'


@pytest.mark.e2e
@pytest.mark.django_db
class TestSignupE2E:
    """E2E tests for signup flow"""
    
    def test_complete_signup_flow(self, browser, live_server):
        """Test complete signup flow end-to-end"""
        # Navigate to signup page
        browser.get(f'{live_server}/auth/signup/')
        
        # Find and fill signup form
        username_field = WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.NAME, 'username'))
        )
        
        email_field = browser.find_element(By.NAME, 'email')
        password_field = browser.find_element(By.NAME, 'password')
        
        # Fill form
        username_field.send_keys('e2euser')
        email_field.send_keys('e2euser@example.com')
        password_field.send_keys('E2EPassword123')
        
        # Submit form
        submit_btn = browser.find_element(By.XPATH, '//button[@type="submit"]')
        submit_btn.click()
        
        # Wait for success message or login page
        time.sleep(1)
        
        # Check for success message or login page
        page_source = browser.page_source
        assert 'success' in page_source.lower() or 'login' in page_source.lower()
    
    def test_signup_duplicate_username_error(self, browser, live_server, test_user):
        """Test error when signing up with duplicate username"""
        browser.get(f'{live_server}/auth/signup/')
        
        username_field = WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.NAME, 'username'))
        )
        
        username_field.send_keys('testuser')  # Already exists
        email_field = browser.find_element(By.NAME, 'email')
        password_field = browser.find_element(By.NAME, 'password')
        
        email_field.send_keys('test2@example.com')
        password_field.send_keys('Password123')
        
        submit_btn = browser.find_element(By.XPATH, '//button[@type="submit"]')
        submit_btn.click()
        
        time.sleep(1)
        
        # Should show error
        assert 'error' in browser.page_source.lower()


@pytest.mark.e2e
@pytest.mark.django_db
class TestLoginE2E:
    """E2E tests for login flow"""
    
    def test_complete_login_flow(self, browser, live_server, test_user):
        """Test complete login flow end-to-end"""
        browser.get(f'{live_server}/auth/login/')
        
        # Find and fill login form
        username_field = WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.NAME, 'username'))
        )
        password_field = browser.find_element(By.NAME, 'password')
        
        # Fill form
        username_field.send_keys('testuser')
        password_field.send_keys('TestPassword123')
        
        # Submit
        submit_btn = browser.find_element(By.XPATH, '//button[@type="submit"]')
        submit_btn.click()
        
        # Wait for chat page to load
        time.sleep(2)
        
        # Should be redirected and authenticated
        assert 'chatbot' in browser.current_url or 'chat' in browser.page_source.lower()
    
    def test_login_wrong_password(self, browser, live_server, test_user):
        """Test login fails with wrong password"""
        browser.get(f'{live_server}/auth/login/')
        
        username_field = WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.NAME, 'username'))
        )
        password_field = browser.find_element(By.NAME, 'password')
        
        username_field.send_keys('testuser')
        password_field.send_keys('WrongPassword')
        
        submit_btn = browser.find_element(By.XPATH, '//button[@type="submit"]')
        submit_btn.click()
        
        time.sleep(1)
        
        # Should show error and stay on login page
        assert 'error' in browser.page_source.lower()


@pytest.mark.e2e
@pytest.mark.django_db
class TestChatFlowE2E:
    """E2E tests for chat interaction"""
    
    def test_create_new_chat_and_send_message(self, browser, live_server, test_user):
        """Test creating new chat and sending message"""
        # First login
        browser.get(f'{live_server}/auth/login/')
        username_field = WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.NAME, 'username'))
        )
        password_field = browser.find_element(By.NAME, 'password')
        
        username_field.send_keys('testuser')
        password_field.send_keys('TestPassword123')
        submit_btn = browser.find_element(By.XPATH, '//button[@type="submit"]')
        submit_btn.click()
        
        time.sleep(2)
        
        # Find "New Chat" button
        new_chat_btn = WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.XPATH, '//button[contains(text(), "Chat Baru") or contains(text(), "New")]'))
        )
        new_chat_btn.click()
        
        time.sleep(1)
        
        # Find message input and send message
        message_input = WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.ID, 'messageInput') or (By.NAME, 'content'))
        )
        
        message_input.send_keys('Apa itu Pertamina?')
        
        # Find and click send button
        send_btn = browser.find_element(By.XPATH, '//button[contains(@onclick, "sendMessage") or contains(text(), "Kirim")]')
        send_btn.click()
        
        time.sleep(2)
        
        # Message should appear in chat
        assert 'Pertamina' in browser.page_source
    
    def test_chat_history_persistence(self, browser, live_server, test_user):
        """Test chat messages are persistent across page reloads"""
        # Login and send message
        browser.get(f'{live_server}/auth/login/')
        username_field = WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.NAME, 'username'))
        )
        password_field = browser.find_element(By.NAME, 'password')
        
        username_field.send_keys('testuser')
        password_field.send_keys('TestPassword123')
        submit_btn = browser.find_element(By.XPATH, '//button[@type="submit"]')
        submit_btn.click()
        
        time.sleep(2)
        
        # Send message
        message_input = WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.ID, 'messageInput'))
        )
        message_input.send_keys('Test message for persistence')
        
        send_btn = browser.find_element(By.XPATH, '//button[contains(@onclick, "sendMessage")]')
        send_btn.click()
        
        time.sleep(2)
        
        # Reload page
        browser.refresh()
        time.sleep(2)
        
        # Message should still be visible
        assert 'Test message' in browser.page_source


@pytest.mark.e2e
@pytest.mark.django_db
class TestProfileE2E:
    """E2E tests for profile management"""
    
    def test_update_profile_flow(self, browser, live_server, test_user):
        """Test updating user profile"""
        # Login first
        browser.get(f'{live_server}/auth/login/')
        username_field = WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.NAME, 'username'))
        )
        password_field = browser.find_element(By.NAME, 'password')
        
        username_field.send_keys('testuser')
        password_field.send_keys('TestPassword123')
        submit_btn = browser.find_element(By.XPATH, '//button[@type="submit"]')
        submit_btn.click()
        
        time.sleep(2)
        
        # Navigate to profile
        browser.get(f'{live_server}/auth/profile/')
        
        time.sleep(1)
        
        # Find and update profile fields
        phone_field = WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.NAME, 'phone'))
        )
        
        phone_field.clear()
        phone_field.send_keys('08123456789')
        
        # Submit form
        submit_btn = browser.find_element(By.XPATH, '//button[@type="submit"]')
        submit_btn.click()
        
        time.sleep(1)
        
        # Success message should appear
        assert 'success' in browser.page_source.lower() or '08123456789' in browser.page_source


@pytest.mark.e2e
@pytest.mark.django_db
class TestSettingsE2E:
    """E2E tests for settings management"""
    
    def test_change_theme_setting(self, browser, live_server, test_user):
        """Test changing theme setting"""
        # Login
        browser.get(f'{live_server}/auth/login/')
        username_field = WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.NAME, 'username'))
        )
        password_field = browser.find_element(By.NAME, 'password')
        
        username_field.send_keys('testuser')
        password_field.send_keys('TestPassword123')
        submit_btn = browser.find_element(By.XPATH, '//button[@type="submit"]')
        submit_btn.click()
        
        time.sleep(2)
        
        # Navigate to settings
        browser.get(f'{live_server}/auth/settings/')
        
        time.sleep(1)
        
        # Find theme selector
        theme_select = WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.NAME, 'theme'))
        )
        
        # Change theme
        theme_select.send_keys('dark')
        
        # Submit
        submit_btn = browser.find_element(By.XPATH, '//button[@type="submit"]')
        submit_btn.click()
        
        time.sleep(1)
        
        # Success message
        assert 'success' in browser.page_source.lower()
    
    def test_change_language_setting(self, browser, live_server, test_user):
        """Test changing language setting"""
        # Login
        browser.get(f'{live_server}/auth/login/')
        username_field = WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.NAME, 'username'))
        )
        password_field = browser.find_element(By.NAME, 'password')
        
        username_field.send_keys('testuser')
        password_field.send_keys('TestPassword123')
        submit_btn = browser.find_element(By.XPATH, '//button[@type="submit"]')
        submit_btn.click()
        
        time.sleep(2)
        
        # Navigate to settings
        browser.get(f'{live_server}/auth/settings/')
        
        time.sleep(1)
        
        # Find language selector
        language_select = WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.NAME, 'language'))
        )
        
        # Change language
        language_select.send_keys('English')
        
        # Submit
        submit_btn = browser.find_element(By.XPATH, '//button[@type="submit"]')
        submit_btn.click()
        
        time.sleep(1)
        
        # Success message
        assert 'success' in browser.page_source.lower()


@pytest.mark.e2e
@pytest.mark.django_db
class TestLogoutE2E:
    """E2E tests for logout flow"""
    
    def test_logout_flow(self, browser, live_server, test_user):
        """Test logout redirects to login"""
        # Login first
        browser.get(f'{live_server}/auth/login/')
        username_field = WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.NAME, 'username'))
        )
        password_field = browser.find_element(By.NAME, 'password')
        
        username_field.send_keys('testuser')
        password_field.send_keys('TestPassword123')
        submit_btn = browser.find_element(By.XPATH, '//button[@type="submit"]')
        submit_btn.click()
        
        time.sleep(2)
        
        # Find and click logout button
        logout_btn = WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.XPATH, '//a[contains(text(), "Logout") or contains(text(), "Keluar")]'))
        )
        logout_btn.click()
        
        time.sleep(1)
        
        # Should be redirected to login
        assert 'login' in browser.current_url.lower()
