#!/usr/bin/env python3
"""
Test runner script for the project manager backend.

This script provides convenient commands for running tests with different options.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, check=True):
    """Run a shell command and return the result."""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, check=check)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Run tests for the project manager backend")
    parser.add_argument("--coverage", action="store_true", help="Run tests with coverage report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--failfast", "-x", action="store_true", help="Stop on first failure")
    parser.add_argument("--markers", "-m", help="Run tests with specific markers")
    parser.add_argument("--no-cov", action="store_true", help="Disable coverage even if configured")
    parser.add_argument("--html-report", action="store_true", help="Generate HTML coverage report")
    parser.add_argument("--file", "-f", help="Run specific test file")
    parser.add_argument("--pattern", help="Run tests matching pattern")
    
    args = parser.parse_args()
    
    # Base command
    cmd_parts = ["python", "-m", "pytest"]
    
    # Add test discovery
    cmd_parts.append("tests/")
    
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
        
        if args.html_report:
            cmd_parts.append("--cov-report=html")
    
    # Markers
    if args.markers:
        cmd_parts.extend(["-m", args.markers])
    
    # Specific file
    if args.file:
        cmd_parts.append(args.file)
    
    # Pattern matching
    if args.pattern:
        cmd_parts.extend(["-k", args.pattern])
    
    # Additional useful options
    cmd_parts.extend([
        "--tb=short",  # Shorter traceback format
        "--disable-warnings",
    ])
    
    cmd = " ".join(cmd_parts)
    
    # Change to backend directory
    backend_dir = Path(__file__).parent
    os.chdir(backend_dir)
    
    print("=" * 60)
    print("Running tests for Project Manager Backend")
    print("=" * 60)
    print(f"Command: {cmd}")
    print(f"Working directory: {os.getcwd()}")
    print("=" * 60)
    
    # Run the tests
    success = run_command(cmd, check=False)
    
    if success:
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        
        if args.coverage and not args.no_cov:
            print("\n📊 Coverage report generated")
            if args.html_report:
                print("📄 HTML report available in: htmlcov/index.html")
    else:
        print("\n" + "=" * 60)
        print("❌ Some tests failed!")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()