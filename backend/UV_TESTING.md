# Testing with UV Python

This guide shows how to run tests using **UV** (modern Python package manager) instead of traditional pip.

## 🚀 UV Installation

First, install UV if you haven't already:

```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or using pip
pip install uv
```

## 📦 Setting Up the Environment

### 1. Create Virtual Environment with UV

```bash
cd backend

# Create and activate virtual environment
uv venv

# Activate (on macOS/Linux)
source .venv/bin/activate

# Activate (on Windows)
.venv\Scripts\activate
```

### 2. Install Dependencies with UV

```bash
# Install all dependencies (including dev dependencies)
uv sync --dev

# Or install specific groups
uv sync --dev --group testing
uv sync --dev --group linting
uv sync --dev --group docs
```

### 3. Verify Installation

```bash
# Check installed packages
uv pip list

# Should show pytest, pytest-django, pytest-cov, etc.
```

## 🧪 Running Tests with UV

### Method 1: Using UV Run (Recommended)

```bash
# Run all tests with UV
uv run pytest tests/

# Run with coverage
uv run pytest tests/ --cov=apps --cov=config --cov-report=html

# Run specific test file
uv run pytest tests/test_automation.py

# Run with verbose output
uv run pytest tests/ -v
```

### Method 2: Using Activated Environment

```bash
# Activate environment first
source .venv/bin/activate

# Then run tests normally
pytest tests/ --cov=apps --cov=config
```

### Method 3: Using UV Script

Add to `pyproject.toml`:

```toml
[tool.uv]
dev-dependencies = [
    "pytest>=8.0.0",
    "pytest-django>=4.8.0", 
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.12.0",
    "factory-boy>=3.3.0",
    "faker>=23.0.0",
]

[project.scripts]
test = "pytest tests/ --cov=apps --cov=config"
test-fast = "pytest tests/ -x -v"
test-coverage = "pytest tests/ --cov=apps --cov=config --cov-report=html --cov-report=term"
```

Then run:
```bash
uv run test
uv run test-fast  
uv run test-coverage
```

## 🎯 UV-Specific Test Commands

### Quick Test Commands

```bash
# Basic test run
uv run pytest tests/

# With coverage report
uv run pytest tests/ --cov=apps --cov=config --cov-report=term-missing

# HTML coverage report
uv run pytest tests/ --cov=apps --cov=config --cov-report=html

# Run specific test categories
uv run pytest tests/ -m "unit"                    # Unit tests only
uv run pytest tests/ -m "automation"              # Automation tests only
uv run pytest tests/ -m "not slow"                # Skip slow tests

# Debug tests
uv run pytest tests/ --pdb                        # Drop into debugger on failure
uv run pytest tests/ -s                           # Show print statements
uv run pytest tests/ --tb=long                    # Detailed traceback

# Run failing tests first
uv run pytest tests/ --lf                         # Last failed
uv run pytest tests/ --ff                         # Failed first
```

### Advanced UV Test Patterns

```bash
# Parallel test execution (if pytest-xdist installed)
uv run pytest tests/ -n auto

# Profile test performance
uv run pytest tests/ --profile

# Generate JUnit XML for CI/CD
uv run pytest tests/ --junitxml=test-results.xml

# Run tests matching pattern
uv run pytest tests/ -k "test_create"             # Tests with "test_create"
uv run pytest tests/ -k "automation and not slow" # Complex patterns
```

## 🔧 UV Configuration

### Update pyproject.toml

```toml
[project]
name = "backend"
version = "0.1.0"
description = "Django Project Manager Backend"
requires-python = ">=3.12"
dependencies = [
    "Django==5.1.5",
    "djangorestframework==3.15.2",
    "django-cors-headers==4.6.0",
    "django-environ==0.12.0",
    "psycopg[binary]==3.2.13",
    "whitenoise==6.8.2",
    "gunicorn==23.0.0",
    "djangorestframework-simplejwt==5.3.1",
]

[project.optional-dependencies]
dev = [
    # Testing
    "pytest>=8.0.0",
    "pytest-django>=4.8.0",
    "pytest-cov>=4.1.0", 
    "pytest-mock>=3.12.0",
    "pytest-xdist>=3.5.0",
    "factory-boy>=3.3.0",
    "faker>=23.0.0",
    
    # Code Quality
    "ruff>=0.1.0",
    "black>=24.0.0",
    "isort>=5.13.0",
    "mypy>=1.8.0",
    
    # Documentation
    "sphinx>=7.0.0",
    "sphinx-rtd-theme>=2.0.0",
]

[tool.uv]
dev-dependencies = [
    "pytest>=8.0.0",
    "pytest-django>=4.8.0", 
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.12.0",
    "pytest-xdist>=3.5.0",
    "factory-boy>=3.3.0",
    "faker>=23.0.0",
]

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings"
python_files = ["tests.py", "test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "--cov=apps",
    "--cov=config", 
    "--cov-report=term-missing",
    "--cov-report=html",
    "--cov-fail-under=80",
    "--strict-markers",
    "--disable-warnings",
]
markers = [
    "slow: marks tests as slow",
    "integration: marks tests as integration tests",
    "unit: marks tests as unit tests",
    "automation: marks automation-related tests",
    "api: marks API endpoint tests",
]
filterwarnings = [
    "ignore::UserWarning",
    "ignore::DeprecationWarning",
]

[tool.ruff]
line-length = 88
target-version = "py312"

[tool.black]
line-length = 88
target-version = ["py312"]

[tool.isort]
profile = "black"
line_length = 88
```

## 🚀 Quick Start Commands

```bash
# One-liner setup and test
cd backend && uv venv && source .venv/bin/activate && uv sync --dev && uv run pytest tests/ --cov=apps --cov=config
```

## 📊 CI/CD with UV

### GitHub Actions Example

```yaml
name: Tests with UV

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Install UV
      uses: astral-sh/setup-uv@v2
      with:
        version: latest
    
    - name: Set up Python
      run: uv python install 3.12
    
    - name: Install dependencies
      run: uv sync --dev
    
    - name: Run tests
      run: uv run pytest tests/ --cov=apps --cov=config --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

## 🔍 Troubleshooting

### Common UV Issues

1. **Import errors**:
   ```bash
   # Ensure you're in the backend directory
   cd backend
   
   # Re-sync dependencies
   uv sync --dev
   ```

2. **Database issues**:
   ```bash
   # Run migrations first
   uv run python manage.py migrate
   ```

3. **Coverage not working**:
   ```bash
   # Install coverage dependencies
   uv sync --dev --group testing
   
   # Check installed packages
   uv pip list | grep coverage
   ```

### UV-Specific Tips

```bash
# Update all dependencies
uv sync --dev --upgrade

# Install specific package
uv add --dev pytest-cov

# Remove package
uv remove --dev pytest-cov

# Check for outdated packages
uv pip list --outdated

# Export requirements
uv export --dev --output-file requirements-dev.txt
```

## 🎯 Performance Tips

```bash
# Parallel test execution
uv run pytest tests/ -n auto

# Run tests in memory order (faster)
uv run pytest tests/ --cache-clear

# Skip slow tests during development
uv run pytest tests/ -m "not slow"

# Run only changed tests (with pytest-watch)
uv run pytest-watch tests/
```

That's it! You now have a complete UV-based testing setup. The commands are faster and more reliable than traditional pip workflows. 🚀