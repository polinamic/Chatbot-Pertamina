"""
Testing guide and reference documentation
Comprehensive guide to running and maintaining the test suite
"""

# COMPREHENSIVE TESTING GUIDE FOR CHATBOT-PERTAMINA

## Overview

This testing system provides comprehensive coverage across multiple layers:

- **Unit Tests**: Test individual models, forms, and utilities in isolation
- **Integration Tests**: Test views, models, and database interactions together
- **E2E Tests**: Test complete user workflows using Selenium browser automation
- **API Tests**: Test REST API endpoints and serialization
- **Database Tests**: Test relationships, cascading, and data integrity
- **Security Tests**: Test for common vulnerabilities (SQL injection, XSS, CSRF)
- **Authorization Tests**: Test access control and data isolation

## Installation

### 1. Install Testing Dependencies

```bash
pip install -r requirements-test.txt
```

### 2. Verify pytest Configuration

The `pytest.ini` file is already configured with:
- Django settings module
- Coverage options
- Test discovery patterns
- Plugin configurations

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Specific Test Category

```bash
# Unit tests for models
pytest tests/test_models.py

# Authentication and authorization tests
pytest tests/test_auth.py

# View/integration tests
pytest tests/test_views.py

# API endpoint tests
pytest tests/test_api.py

# Database integrity tests
pytest tests/test_database.py

# End-to-end tests
pytest tests/test_e2e.py -v
```

### Run Specific Test Class

```bash
pytest tests/test_models.py::TestUserModel
pytest tests/test_auth.py::TestLoginFlow
pytest tests/test_views.py::TestChatPageView
```

### Run Specific Test Function

```bash
pytest tests/test_models.py::TestUserModel::test_user_creation
pytest tests/test_auth.py::TestLoginFlow::test_successful_login
```

### Run with Coverage Report

```bash
pytest --cov=apps --cov-report=html
# Opens htmlcov/index.html in browser
```

### Run in Parallel (Faster)

```bash
pytest -n auto
```

### Run with Verbose Output

```bash
pytest -v
```

### Run Only Fast Tests (Skip E2E)

```bash
pytest -m "not e2e"
```

### Run Only Security Tests

```bash
pytest tests/test_database.py::TestSecurityVulnerabilities
```

## Test Structure

### conftest.py
Contains pytest configuration and shared fixtures:
- `test_user` - Standard test user
- `test_user_with_profile_and_settings` - User with related models
- `test_admin_user` - Admin user
- `authenticated_client` - Logged-in test client
- `test_conversation` - Sample conversation
- `test_conversation_with_messages` - Conversation with pre-populated messages
- `multiple_users` - 3 test users for isolation testing
- `valid_signup_data`, `valid_login_data` - Form data fixtures
- Form and API data fixtures

### factories.py
Model factories for generating test data:
- `UserFactory` - Creates users with random data
- `UserProfileFactory` - Creates profiles
- `UserSettingsFactory` - Creates settings
- `ConversationFactory` - Creates conversations
- `MessageFactory` - Creates messages

### test_models.py
Unit tests for model functionality:
- User creation and password hashing
- Profile auto-creation via signals
- Settings with user isolation
- Conversation and message relationships
- Data integrity constraints

### test_auth.py
Authentication and authorization tests:
- Signup flow (NO auto-login)
- Login with success/failure cases
- Access control (requires authentication)
- User data isolation
- Session security

### test_views.py
Integration tests for views:
- Chat page rendering
- Profile page CRUD
- Settings page updates
- Conversation creation
- Message sending and retrieval
- User isolation verification

### test_api.py
REST API endpoint tests:
- Conversation CRUD operations
- Message sending via API
- User profile endpoints
- Settings endpoints
- Error handling and response format validation
- Permission checks

### test_database.py
Database integrity and security:
- Cascade delete relationships
- Foreign key integrity
- Validation constraints
- SQL injection protection
- XSS prevention
- CSRF protection
- User permission isolation
- Query optimization

### test_e2e.py
End-to-end browser automation tests:
- Complete signup flow
- Login flow
- Chat creation and messaging
- Chat history persistence
- Profile updates
- Settings changes
- Logout flow

## Key Testing Patterns

### Testing User Isolation

```python
@pytest.mark.django_db
def test_user_cannot_see_other_conversation(self, multiple_users):
    user1, user2, user3 = multiple_users
    
    conv1 = Conversation.objects.create(user=user1, title='Conv')
    
    # User2 cannot see User1's conversation
    assert conv1 not in user2.conversations.all()
```

### Testing Authentication Required

```python
@pytest.mark.django_db
def test_unauthenticated_cannot_access_chat(self, client):
    response = client.get('/chatbot/', follow=True)
    
    # Should redirect to login
    assert 'login' in response.request['PATH_INFO'].lower()
```

### Testing API with Authentication

```python
@pytest.mark.django_db
def test_list_conversations_authenticated(self, authenticated_api_client):
    response = authenticated_api_client.get('/api/v1/conversations/')
    
    assert response.status_code == 200
    assert isinstance(response.data, list)
```

### Testing Security Vulnerabilities

```python
@pytest.mark.django_db
def test_sql_injection_protection(self, authenticated_api_client):
    response = authenticated_api_client.get(
        "/api/v1/conversations/?search='; DROP TABLE conversations; --"
    )
    
    # Should return safely
    assert response.status_code in [200, 400]
    # Table should still exist
    assert Conversation.objects.count() >= 0
```

## Coverage Requirements

Target coverage levels:
- **Models**: 95%+ (critical for data integrity)
- **Views**: 85%+ (important for functionality)
- **API**: 90%+ (essential for client integration)
- **Utils**: 80%+ (helpers and utilities)
- **Overall**: 80%+ target

### Check Coverage

```bash
pytest --cov=apps --cov-report=term-missing
```

## Common Issues and Solutions

### Issue: Database Tests Fail

**Solution**: Ensure migrations are applied:
```bash
python manage.py migrate
pytest
```

### Issue: E2E Tests Time Out

**Solution**: Increase timeout and ensure server is running:
```bash
pytest tests/test_e2e.py -v --timeout=60
```

### Issue: Permission Denied on Chrome/Chromedriver

**Solution**: Use headless mode (already configured):
```bash
# Already in test_e2e.py
options.add_argument('--headless')
```

### Issue: Session Tests Fail

**Solution**: Ensure Django settings has SESSION_ENGINE configured:
```python
# In config/settings.py
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
```

## Continuous Integration Setup

### GitHub Actions Workflow

`.github/workflows/tests.yml` automatically runs:
1. All unit tests
2. Fast integration tests
3. Security checks
4. Coverage report

On every commit to main branch.

### Running Tests Locally Before Push

```bash
# Full test suite
pytest -v

# With coverage
pytest --cov=apps --cov-report=term-missing

# Fast tests only (skip E2E)
pytest -m "not e2e"
```

## Best Practices

### 1. Use Fixtures for Setup
```python
@pytest.mark.django_db
def test_something(self, test_user_with_profile_and_settings):
    # Fixture automatically creates user, profile, settings
    user = test_user_with_profile_and_settings
```

### 2. Use Factories for Test Data
```python
from tests.factories import ConversationFactory

def test_something(self):
    # Automatically creates conversation with random data
    conversation = ConversationFactory()
```

### 3. Test Isolation
```python
@pytest.mark.django_db
def test_user_cannot_see_other_data(self, multiple_users):
    # multiple_users fixture provides 3 isolated users
    user1, user2, user3 = multiple_users
```

### 4. Test Both Success and Failure Cases
```python
def test_login_success(self, client, test_user, valid_login_data):
    # Test successful login
    ...

def test_login_wrong_password(self, client, test_user):
    # Test failure case
    ...
```

### 5. Verify Both Positive and Negative Security
```python
def test_admin_required(self, client, test_user):
    # Test that regular user cannot access admin page
    response = client.get('/admin/')
    assert response.status_code == 403
```

## Performance Optimization

### Using select_related and prefetch_related

```python
# Good: Optimized query
conversations = Conversation.objects.select_related('user').filter(...)
```

### Database Query Analysis

```bash
# Show database queries during test
pytest --capture=no --pdb
```

### Parallel Test Execution

```bash
# Run tests in parallel (4 workers)
pytest -n 4
```

## Maintenance

### Adding New Tests

1. Create test function in appropriate test file
2. Use relevant fixtures and factories
3. Test both success and failure cases
4. Update pytest marks if needed (@pytest.mark.django_db, @pytest.mark.e2e)
5. Run coverage report to ensure coverage

### Updating Fixtures

Edit `tests/conftest.py` to modify fixtures used across all tests

### Updating Factories

Edit `tests/factories.py` to change how test data is generated

## Running Tests in CI/CD

Tests are automatically run on:
- Pull requests
- Commits to main branch
- Manual trigger via GitHub Actions

### View CI Results

```bash
# GitHub Actions logs
# https://github.com/YOUR_REPO/actions
```

## Additional Resources

- pytest documentation: https://docs.pytest.org/
- factory-boy documentation: https://factoryboy.readthedocs.io/
- Django testing guide: https://docs.djangoproject.com/en/stable/topics/testing/
- Selenium documentation: https://selenium-python.readthedocs.io/

## Contact & Support

For test failures or coverage questions, check:
1. Test output logs
2. Coverage report (htmlcov/index.html)
3. Django test documentation
4. pytest debugging guide
