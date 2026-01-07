#!/bin/bash

# UV Test Setup Script for Project Manager Backend
# This script sets up the complete testing environment with UV

set -e  # Exit on any error

echo "🚀 Setting up UV Testing Environment for Project Manager Backend"
echo "==============================================================="

# Check if UV is installed
if ! command -v uv &> /dev/null; then
    echo "❌ UV is not installed. Please install UV first:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "   # OR"
    echo "   pip install uv"
    exit 1
fi

echo "✅ UV found: $(uv --version)"

# Change to backend directory
cd "$(dirname "$0")"

echo "📁 Working directory: $(pwd)"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "🔧 Creating virtual environment..."
    uv venv
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source .venv/bin/activate

# Sync dependencies
echo "📦 Installing dependencies..."
uv sync --dev

# Verify pytest installation
echo "🧪 Verifying pytest installation..."
uv run pytest --version

# Run a quick test to verify setup
echo "🏃‍♂️ Running quick setup test..."
uv run pytest tests/test_accounts.py::TestUserModel::test_create_user -v --tb=short || {
    echo "⚠️  Some tests may need adjustment for your specific User model"
}

echo ""
echo "🎉 UV Testing Environment Setup Complete!"
echo "========================================="
echo ""
echo "📋 Quick Commands:"
echo "   # Run all tests"
echo "   python uv_test.py"
echo ""
echo "   # Run with coverage"
echo "   python uv_test.py --coverage --html"
echo ""
echo "   # Run specific test file"
echo "   python uv_test.py -f test_automation.py"
echo ""
echo "   # Run automation tests only"
echo "   python uv_test.py -m automation"
echo ""
echo "   # Run with verbose output"
echo "   python uv_test.py -v"
echo ""
echo "   # Run tests in parallel"
echo "   python uv_test.py -n 4"
echo ""
echo "📚 Documentation:"
echo "   - UV Testing Guide: UV_TESTING.md"
echo "   - General Testing Guide: TESTING.md"
echo "   - Test README: tests/README.md"
echo ""
echo "🚀 Happy Testing!"