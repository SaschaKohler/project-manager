#!/usr/bin/env python3
"""
UV-optimized test runner for the project manager backend.

This script provides convenient commands for running tests with UV Python.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, check=True):
    """Run a shell command and return the result."""
    print(f"🔧 Running: {cmd}")
    result = subprocess.run(cmd, shell=True, check=check)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Run tests with UV Python for the project manager backend")
    parser.add_argument("--coverage", action="store_true", help="Run tests with coverage report")
    parser.add_argument("--html", action="store_true", help="Generate HTML coverage report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--failfast", "-x", action="store_true", help="Stop on first failure")
    parser.add_argument("--markers", "-m", help="Run tests with specific markers")
    parser.add_argument("--no-cov", action="store_true", help="Disable coverage")
    parser.add_argument("--file", "-f", help="Run specific test file")
    parser.add_argument("--pattern", help="Run tests matching pattern")
    parser.add_argument("--parallel", "-n", type=int, help="Run tests in parallel (requires pytest-xdist)")
    parser.add_argument("--slow", action="store_true", help="Include slow tests")
    parser.add_argument("--update-snapshots", action="store_true", help="Update test snapshots")
    
    args = parser.parse_args()
    
    # Base command with UV
    cmd_parts = ["uv", "run", "pytest"]
    
    # Add test discovery
    cmd_parts.append("tests/")
    
    # Parallel execution
    if args.parallel:
        cmd_parts.extend(["-n", str(args.parallel)])
    
    # Verbosity
    if args.verbose:
        cmd_parts.append("-v")
    
    # Fail fast
    if args.failfast:
        cmd_parts.append("-x")
    
    # Coverage
    if args.coverage and not args.no_cov:
        cmd_parts.extend([
            "--cov=apps",
            "--cov=config", 
            "--cov-report=term-missing"
        ])
        
        if args.html:
            cmd_parts.append("--cov-report=html")
    
    # Markers
    if args.markers:
        cmd_parts.extend(["-m", args.markers])
    elif not args.slow:
        # Skip slow tests by default
        cmd_parts.extend(["-m", "not slow"])
    
    # Specific file
    if args.file:
        cmd_parts.append(args.file)
    
    # Pattern matching
    if args.pattern:
        cmd_parts.extend(["-k", args.pattern])
    
    # Update snapshots
    if args.update_snapshots:
        cmd_parts.append("--snapshot-update")
    
    # Additional useful options
    cmd_parts.extend([
        "--tb=short",
        "--disable-warnings",
        "--strict-markers",
    ])
    
    cmd = " ".join(cmd_parts)
    
    # Change to backend directory
    backend_dir = Path(__file__).parent
    os.chdir(backend_dir)
    
    print("=" * 70)
    print("🧪 Running tests with UV Python - Project Manager Backend")
    print("=" * 70)
    print(f"📋 Command: {cmd}")
    print(f"📁 Working directory: {os.getcwd()}")
    print(f"🐍 UV Version: {get_uv_version()}")
    print("=" * 70)
    
    # Run the tests
    success = run_command(cmd, check=False)
    
    if success:
        print("\n" + "=" * 70)
        print("✅ All tests passed!")
        print("=" * 70)
        
        if args.coverage and not args.no_cov:
            print("\n📊 Coverage report generated")
            if args.html:
                print("📄 HTML report available in: htmlcov/index.html")
                print("🌐 Open in browser: open htmlcov/index.html")
    else:
        print("\n" + "=" * 70)
        print("❌ Some tests failed!")
        print("=" * 70)
        print("\n💡 Tips:")
        print("   • Run with --verbose for detailed output")
        print("   • Run with --failfast to stop at first failure")
        print("   • Run with --file <test_file> to test specific modules")
        print("   • Run with --pattern <pattern> to match test names")
        sys.exit(1)


def get_uv_version():
    """Get UV version."""
    try:
        result = subprocess.run(["uv", "--version"], capture_output=True, text=True)
        return result.stdout.strip()
    except:
        return "Unknown"


if __name__ == "__main__":
    # Show help if no arguments
    if len(sys.argv) == 1:
        print("🧪 UV Test Runner for Project Manager Backend")
        print("\n🚀 Quick start:")
        print("   python uv_test.py                    # Run all tests")
        print("   python uv_test.py --coverage         # With coverage")
        print("   python uv_test.py --coverage --html  # HTML coverage report")
        print("   python uv_test.py -f test_automation.py  # Specific file")
        print("   python uv_test.py -m automation      # Automation tests only")
        print("   python uv_test.py -v                 # Verbose output")
        print("   python uv_test.py -x                 # Stop on first failure")
        print("   python uv_test.py -n 4               # Run in parallel")
        print("\n📚 Setup:")
        print("   uv venv")
        print("   source .venv/bin/activate")
        print("   uv sync --dev")
        print("\nFor more options: python uv_test.py --help")
        sys.exit(0)
    
    main()