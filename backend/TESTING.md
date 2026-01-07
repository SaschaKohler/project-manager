# Testing Guide

This document describes the testing setup and best practices for the Project Manager backend.

## 🏗️ Test Structure

```
backend/tests/
├── __init__.py                    # Package initialization
├── conftest.py                    # Pytest configuration and fixtures
├── test_accounts.py              # User model and authentication tests
├── test_tenants_models.py        # Organization and membership tests
├── test_projects_models.py       # Project, task, and related models
├── test_automation.py            # Automation engine and rules tests
├── test_web_views.py             # Web views and HTTP endpoints
└── run_tests.py                  # Convenience test runner script
```

## 🚀 Getting Started

### Prerequisites

Install the development dependencies:

```bash
pip install -r requirements-dev.txt
```

This includes:
- `pytest` - Test framework
- `pytest-django` - Django integration
- `pytest-cov` - Coverage reporting
- `pytest-mock` - Mocking utilities
- `factory-boy` - Test data factories (optional)

### Running Tests

#### Quick Start

```bash
# Run all tests
python run_tests.py

# Run with coverage
python run_tests.py --coverage

# Run specific test file
python run_tests.py --file test_projects_models.py

# Run with verbose output
python run_tests.py --verbose

# Run only unit tests
python run_tests.py --markers unit

# Run automation tests only
python run_tests.py --markers automation
```

#### Manual Commands

```bash
# Basic test run
pytest tests/

# With coverage
pytest tests/ --cov=apps --cov=config

# Verbose output
pytest tests/ -v

# Stop on first failure
pytest tests/ -x

# Run specific test
pytest tests/test_projects_models.py::TestTask::test_task_time_tracking

# Run tests matching pattern
pytest tests/ -k "test_create"

# Run tests with specific markers
pytest tests/ -m "unit"
pytest tests/ -m "not slow"
```

## 📋 Test Categories

Tests are organized by functionality:

### Unit Tests (`unit`)
- Model methods and properties
- Form validation
- Utility functions
- Individual components in isolation

### Integration Tests (`integration`)
- View functionality
- API endpoints
- Database operations
- Cross-component interactions

### Automation Tests (`automation`)
- Automation rule execution
- Trigger handling
- Action implementations

### API Tests (`api`)
- REST API endpoints
- Authentication
- Serialization/deserialization

## 🧪 Writing Tests

### Test Naming Conventions

- **Files**: `test_<module_name>.py`
- **Classes**: `Test<ComponentName>`
- **Methods**: `test_<behavior>_<condition>`

### Example Test Structure

```python
class TestTaskModel:
    """Test cases for Task model."""
    
    def test_create_basic_task(self, task_factory):
        """Test creating a basic task."""
        task = task_factory()
        
        assert task.title == "Test Task"
        assert task.status == Task.Status.TODO
        assert task.priority == Task.Priority.MEDIUM
    
    def test_task_time_tracking(self, task_factory):
        """Test task time tracking functionality."""
        task = task_factory(tracked_seconds=3661)  # 1h 1m 1s
        
        assert task.tracked_human == "1h 01m"
```

### Using Fixtures

```python
def test_automation_trigger(self, automation_engine, complete_setup):
    """Test automation trigger with proper setup."""
    task = complete_setup["task1"]
    
    # Create automation rule
    rule = automation_rule_factory(
        name="Test Rule",
        trigger_type=TaskAutomationRule.TriggerType.TASK_CREATED
    )
    
    # Test automation
    logs = automation_engine.trigger_task_created(task)
    
    assert len(logs) == 1
    assert logs[0].status == TaskAutomationLog.Status.SUCCESS
```

### Testing HTTP Views

```python
def test_dashboard_requires_login(self, client):
    """Test that dashboard requires login."""
    response = client.get(reverse("web:app_home"))
    assert response.status_code == 302  # Redirect to login

def test_dashboard_data(self, active_organization, authenticated_client):
    """Test dashboard displays correct data."""
    # Create test data using factories
    project = project_factory(organization=active_organization)
    
    # Test the view
    response = authenticated_client.get(reverse("web:app_home"))
    
    assert response.status_code == 200
    assert "project_count" in response.context
    assert response.context["project_count"] == 1
```

### Testing API Endpoints

```python
def test_calendar_events_api(self, api_client, active_organization):
    """Test calendar events API."""
    # Authenticate
    user = active_organization.memberships.first().user
    api_client.force_authenticate(user=user)
    
    # Create test data
    task = task_factory(
        project__organization=active_organization,
        scheduled_start=timezone.now()
    )
    
    # Test API
    response = api_client.get(reverse("web:calendar_events"))
    
    assert response.status_code == 200
    events = response.json()
    assert len(events) >= 1
```

## 🏭 Factories

The testing setup includes factories for creating test data:

### Available Factories

```python
# User factory
user = user_factory(email="test@example.com")

# Organization factory  
org = organization_factory(name="Test Org", slug="test-org")

# Project factory
project = project_factory(
    organization=org,
    created_by=user,
    title="Custom Project"
)

# Task factory
task = task_factory(
    project=project,
    assigned_to=user,
    status=Task.Status.IN_PROGRESS
)

# Automation rule factory
rule = automation_rule_factory(
    organization=org,
    trigger_type=TaskAutomationRule.TriggerType.TASK_CREATED
)
```

### Customizing Factory Data

```python
# Override default values
project = project_factory(
    title="My Custom Project",
    category=Project.Category.DEVELOPMENT,
    priority=Project.Priority.HIGH
)

# Use keyword arguments
task = task_factory(
    title="Urgent Task",
    status=Task.Status.IN_PROGRESS,
    priority=Task.Priority.HIGH
)
```

## 🔍 Testing Best Practices

### 1. **Test One Thing at a Time**
Each test should verify a single behavior or outcome.

```python
# ✅ Good - Tests one specific behavior
def test_task_time_tracking_calculation(self, task_factory):
    task = task_factory(tracked_seconds=3661)
    assert task.tracked_human == "1h 01m"

# ❌ Bad - Tests multiple things
def test_task_creation_and_properties(self, task_factory):
    task = task_factory()
    assert task.title == "Test Task"
    assert task.status == Task.Status.TODO
    assert task.priority == Task.Priority.MEDIUM
    # ... many more assertions
```

### 2. **Use Descriptive Test Names**
Test names should describe what is being tested and expected outcome.

```python
# ✅ Good
def test_automation_rule_triggers_on_task_status_change_to_done(self):
    pass

def test_calendar_api_filters_by_project_when_project_id_provided(self):
    pass

# ❌ Bad
def test_automation(self):
    pass

def test_calendar(self):
    pass
```

### 3. **Test Edge Cases**
Don't just test the happy path.

```python
def test_automation_rule_ignores_inactive_rules(self, automation_engine):
    """Test that inactive rules don't trigger."""
    # Test with inactive rule
    rule = automation_rule_factory(is_active=False)
    task = task_factory()
    
    logs = automation_engine.trigger_task_created(task)
    assert len(logs) == 0

def test_task_label_assignment_prevents_duplicates(self, task_factory, org):
    """Test that same label can't be assigned twice."""
    label = task_factory()  # This would need to be adapted
    task = task_factory()
    
    # First assignment should work
    TaskLabelAssignment.objects.create(task=task, label=label)
    
    # Second should fail
    with pytest.raises(Exception):
        TaskLabelAssignment.objects.create(task=task, label=label)
```

### 4. **Mock External Dependencies**
Use mocking for external services and complex integrations.

```python
@patch('apps.projects.automation.external_service.call')
def test_automation_with_external_service(self, mock_service, automation_engine):
    """Test automation that calls external service."""
    mock_service.return_value = {"status": "success"}
    
    # Test automation
    result = automation_engine.trigger_task_created(task)
    
    # Verify external service was called
    mock_service.assert_called_once_with(task.id)
```

### 5. **Clean Up After Tests**
Use fixtures and context managers for proper cleanup.

```python
def test_with_temporary_files(self, temp_media_dir):
    """Test that uses temporary media directory."""
    # Test with temporary files
    test_file = temp_media_dir / "test.txt"
    test_file.write_text("test content")
    
    # File automatically cleaned up after test

def test_database_state(self, db):
    """Test with clean database state."""
    # Database automatically reset after each test
    pass
```

## 📊 Coverage

### Running with Coverage

```bash
# Generate coverage report
python run_tests.py --coverage

# Generate HTML report
python run_tests.py --coverage --html-report

# View coverage report
cat htmlcov/index.html  # Open in browser
```

### Coverage Goals

- **Minimum**: 80% overall coverage
- **Critical components**: 95%+ coverage
- **New code**: 100% coverage

### Coverage Exclusions

Some code can be excluded from coverage:
- `__str__` methods
- Simple property getters
- Third-party code
- Debug/development code

Add to `pytest.ini`:
```ini
[coverage:run]
omit = 
    */migrations/*
    */venv/*
    */tests/*
    */settings/*
```

## 🚨 Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v3
      with:
        python-version: '3.12'
    
    - name: Install dependencies
      run: |
        cd backend
        pip install -r requirements-dev.txt
    
    - name: Run tests
      run: |
        cd backend
        python run_tests.py --coverage --html-report
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./backend/coverage.xml
```

## 🛠️ Troubleshooting

### Common Issues

1. **Database not created**
   ```bash
   # Ensure migrations are applied
   python manage.py migrate
   ```

2. **Import errors**
   ```bash
   # Add backend to Python path
   export PYTHONPATH="${PYTHONPATH}:$(pwd)"
   ```

3. **Fixture not found**
   ```bash
   # Check conftest.py is in tests directory
   ls tests/conftest.py
   ```

4. **Coverage not working**
   ```bash
   # Install coverage dependencies
   pip install pytest-cov
   ```

### Debugging Tests

```bash
# Run with debugger
pytest tests/test_projects_models.py::TestTask::test_task_time_tracking -s --pdb

# Drop into debugger on failure
pytest tests/ --pdb-trace

# Verbose output with print statements
pytest tests/ -s -v
```

## 📝 Adding New Tests

1. **Create test file**: `test_<module>.py`
2. **Import test framework**: `import pytest`
3. **Write test classes**: `class Test<Component>:`
4. **Add test methods**: `def test_<behavior>(self, ...):`
5. **Use factories and fixtures**
6. **Run tests**: `python run_tests.py --file test_<module>.py`

## 🎯 Test Checklist

Before submitting code:

- [ ] All tests pass
- [ ] New functionality has tests
- [ ] Edge cases are covered
- [ ] Code coverage is maintained or improved
- [ ] Tests are readable and well-named
- [ ] No commented-out test code
- [ ] Integration tests verify real workflows

Happy testing! 🎉