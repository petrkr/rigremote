#!/usr/bin/env python3
"""Test radio ID generation."""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.utils import generate_radio_id

def test_radio_id_generation():
    """Test various radio name scenarios."""
    
    test_cases = [
        # (input_name, expected_pattern, existing_ids)
        ("My FT-991A", "my_ft991a", []),
        ("Yaesu FT-991A", "yaesu_ft991a", []),
        ("IC-7300", "ic_7300", []),
        ("Radio #1", "radio_1", []),
        ("Test Radio", "test_radio", []),
        ("Test Radio", "test_radio_1", ["test_radio"]),  # Conflict resolution
        ("Test Radio", "test_radio_2", ["test_radio", "test_radio_1"]),  # Multiple conflicts
        ("Ràdio ñoño", "radio_nono", []),  # Accented characters
        ("991A-Main", "radio_991a_main", []),  # Starts with number
        ("  Extra  Spaces  ", "extra_spaces", []),  # Extra spaces
        ("Special!@#$%Chars", "specialchars", []),  # Special characters
        ("", "radio", []),  # Empty name
    ]
    
    print("Testing radio ID generation...")
    
    for name, expected_start, existing in test_cases:
        result = generate_radio_id(name, existing)
        
        print(f"'{name}' → '{result}'")
        
        # Basic validation
        assert result, "ID should not be empty"
        assert result[0].isalpha(), f"ID should start with letter: {result}"
        assert result not in existing, f"ID should be unique: {result}"
        assert "_" not in result or "__" not in result, f"No double underscores: {result}"
        
        # Check expected pattern for non-conflict cases
        if not existing and expected_start:
            if expected_start.startswith("radio_"):
                assert result.startswith("radio_"), f"Expected to start with 'radio_': {result}"
            else:
                assert result == expected_start or result.startswith(expected_start), f"Expected pattern '{expected_start}', got '{result}'"
    
    print("✅ All radio ID generation tests passed!")

if __name__ == "__main__":
    test_radio_id_generation()