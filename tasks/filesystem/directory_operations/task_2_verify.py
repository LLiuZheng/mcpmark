#!/usr/bin/env python3
"""
Verification script for Filesystem Task 4: Directory Analysis
"""

import sys
import os
from pathlib import Path
import re

def get_test_directory() -> Path:
    """Get the test directory from FILESYSTEM_TEST_ROOT env var."""
    test_root = os.environ.get("FILESYSTEM_TEST_ROOT")
    if not test_root:
        raise ValueError("FILESYSTEM_TEST_ROOT environment variable is required")
    return Path(test_root)

def verify_task(test_dir: Path) -> bool:
    """Verify the task was completed correctly."""
    report_file = test_dir / "directory_report.txt"
    
    if not report_file.exists():
        print("❌ File 'directory_report.txt' not found")
        return False
    
    try:
        content = report_file.read_text()
        
        # Check required sections
        required = [
            "Directory Analysis Report",
            "Generated:",
            "Summary:",
            "Total files:",
            "Total directories:",
            "Text files in root:",
            "Root directory .txt files:",
            "Analysis complete"
        ]
        
        for pattern in required:
            if pattern not in content:
                print(f"❌ Missing section: '{pattern}'")
                return False
        
        # Check date format
        if not re.search(r'Generated: \d{4}-\d{2}-\d{2}', content):
            print("❌ Missing or incorrect date format")
            return False
        
        # Check file counts exist
        if not re.search(r'Total files:\s*\d+', content):
            print("❌ Missing file count")
            return False
            
        if not re.search(r'Total directories:\s*\d+', content):
            print("❌ Missing directory count")
            return False
        
        print("✅ Directory analysis report created correctly")
        return True
        
    except Exception as e:
        print(f"❌ Error reading report: {e}")
        return False

def main():
    """Main verification function."""
    test_dir = get_test_directory()
    
    if verify_task(test_dir):
        print("🎉 Task 4 verification: PASS")
        sys.exit(0)
    else:
        print("❌ Task 4 verification: FAIL")
        sys.exit(1)

if __name__ == "__main__":
    main()