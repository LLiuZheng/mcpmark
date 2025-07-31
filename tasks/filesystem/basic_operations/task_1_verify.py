#!/usr/bin/env python3
"""
Verification script for Filesystem Task 1: Create and Write File
"""

import sys
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================

# Expected file name
FILE_NAME = "new_document.txt"

# Expected content patterns
EXPECTED_PATTERNS = [
    "New Document Created by MCP",
    "MCP tools",
    "Creation date:",
    "Complete"
]

# =============================================================================
# IMPLEMENTATION
# =============================================================================

def get_test_directory() -> Path:
    """Get the test directory using relative path."""
    # Use relative path from this script to test environment
    script_dir = Path(__file__).parent
    return script_dir / "../../../test_environments/desktop"

def verify_file_exists(test_dir: Path, file_name: str) -> bool:
    """Verify that the file exists in the test directory."""
    file_path = test_dir / file_name
    
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return False
    
    if not file_path.is_file():
        print(f"❌ Path exists but is not a file: {file_path}")
        return False
    
    print(f"✅ File exists: {file_path}")
    return True

def verify_file_content(test_dir: Path, file_name: str) -> bool:
    """Verify the content of the file."""
    file_path = test_dir / file_name
    
    try:
        content = file_path.read_text()
        print(f"\n📄 File content:\n{content}\n")
        
        all_passed = True
        
        # Check for expected patterns
        for pattern in EXPECTED_PATTERNS:
            if pattern.lower() in content.lower():
                print(f"✅ Found expected pattern: '{pattern}'")
            else:
                print(f"❌ Missing expected pattern: '{pattern}'")
                all_passed = False
        
        # Check if file has multiple lines
        lines = content.strip().split('\n')
        if len(lines) >= 3:
            print(f"✅ File has {len(lines)} lines (expected at least 3)")
        else:
            print(f"❌ File has only {len(lines)} lines (expected at least 3)")
            all_passed = False
        
        # Check if first line contains "New Document Created by MCP"
        if lines and "New Document Created by MCP" in lines[0]:
            print("✅ First line contains 'New Document Created by MCP'")
        else:
            print("❌ First line does not contain 'New Document Created by MCP'")
            all_passed = False
        
        # Check for date format YYYY-MM-DD
        import re
        date_pattern = r'\d{4}-\d{2}-\d{2}'
        if re.search(date_pattern, content):
            print("✅ Contains date in YYYY-MM-DD format")
        else:
            print("❌ Missing date in YYYY-MM-DD format")
            all_passed = False
        
        # Check for timestamp pattern (flexible check)
        timestamp_patterns = ["20", ":", "-"]  # Common in timestamps
        has_timestamp = any(all(p in line for p in timestamp_patterns) for line in lines)
        if has_timestamp:
            print("✅ Found what appears to be a timestamp")
        else:
            print("⚠️  No obvious timestamp found (optional)")
        
        return all_passed
        
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False

def main():
    """Main verification function."""
    print("🔍 Verifying Filesystem Task 1: Create New File")
    print("=" * 50)
    
    # Get test directory
    test_dir = get_test_directory()
    print(f"📁 Test directory: {test_dir}")
    
    # Verify file exists
    if not verify_file_exists(test_dir, FILE_NAME):
        print("\n❌ Task 1 verification: FAIL")
        print(f"File {FILE_NAME} was not created")
        sys.exit(1)
    
    # Verify file content
    if not verify_file_content(test_dir, FILE_NAME):
        print("\n❌ Task 1 verification: FAIL")
        print("File content does not meet requirements")
        sys.exit(1)
    
    print("\n🎉 Task 1 verification: PASS")
    print(f"File {FILE_NAME} created successfully with correct content")
    sys.exit(0)

if __name__ == "__main__":
    main()