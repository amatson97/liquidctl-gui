#!/usr/bin/env python3
"""
Test script for profile management functionality
"""

import sys
import json
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from liquidctl_gui.lib.config import (
    save_profile, load_profile, list_profiles,
    delete_profile, save_current_state, load_current_state,
    PROFILES_DIR, CURRENT_PROFILE_FILE
)

def test_profile_management():
    """Test the profile management functions."""
    print("Testing profile management...")
    
    # Test data
    test_profile = {
        "colors": {"device1:ring": "#ff0000", "device1:logo": "#00ff00"},
        "modes": {"device1:ring": "fixed", "device1:logo": "pulse"},
        "speeds": {"device1:pump": "60"}
    }
    
    # Test saving a profile
    print("\n1. Testing save_profile...")
    profile_path = save_profile(test_profile, "test_profile")
    print(f"   Saved profile to: {profile_path}")
    assert profile_path.exists(), "Profile file not created"
    
    # Test listing profiles
    print("\n2. Testing list_profiles...")
    profiles = list_profiles()
    print(f"   Found profiles: {profiles}")
    assert "test_profile" in profiles, "Profile not in list"
    
    # Test loading a profile
    print("\n3. Testing load_profile...")
    loaded_profile = load_profile("test_profile")
    print(f"   Loaded profile: {loaded_profile}")
    assert loaded_profile == test_profile, "Profile data mismatch"
    
    # Test current state save/load
    print("\n4. Testing save_current_state...")
    save_current_state(test_profile, "test_profile")
    print(f"   Saved current state to: {CURRENT_PROFILE_FILE}")
    assert CURRENT_PROFILE_FILE.exists(), "Current state file not created"
    
    print("\n5. Testing load_current_state...")
    current_state, profile_name = load_current_state()
    print(f"   Loaded current state: {current_state}")
    print(f"   Active profile name: {profile_name}")
    assert current_state == test_profile, "Current state data mismatch"
    assert profile_name == "test_profile", "Profile name mismatch"
    
    # Test deleting a profile
    print("\n6. Testing delete_profile...")
    result = delete_profile("test_profile")
    print(f"   Delete result: {result}")
    assert result is True, "Profile not deleted"
    
    profiles = list_profiles()
    print(f"   Remaining profiles: {profiles}")
    assert "test_profile" not in profiles, "Profile still in list after deletion"
    
    # Cleanup
    if CURRENT_PROFILE_FILE.exists():
        CURRENT_PROFILE_FILE.unlink()
        print("\n7. Cleaned up current state file")
    
    print("\n✅ All tests passed!")

if __name__ == "__main__":
    try:
        test_profile_management()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
