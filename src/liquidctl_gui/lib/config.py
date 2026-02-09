"""User configuration helpers for liquidctl-gui."""

import json
from copy import deepcopy
from pathlib import Path


CONFIG_DIR = Path.home() / ".liquidctl-gui"
CONFIG_FILE = CONFIG_DIR / "config.json"
PROFILES_DIR = CONFIG_DIR / "profiles"
CURRENT_PROFILE_FILE = CONFIG_DIR / "current_profile.json"


def _merge_dicts(base, override):
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _merge_dicts(base[key], value)
        else:
            base[key] = value
    return base


def load_config(defaults):
    config = deepcopy(defaults)
    if not CONFIG_FILE.exists():
        return config, False, None
    try:
        data = json.loads(CONFIG_FILE.read_text())
    except Exception as exc:
        return config, False, exc
    return _merge_dicts(config, data), True, None


def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


def save_profile(profile, name):
    """Save a profile to the profiles directory."""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    profile_path = PROFILES_DIR / f"{name}.json"
    profile_path.write_text(json.dumps(profile, indent=2))
    return profile_path


def load_profile(name):
    """Load a profile by name from the profiles directory."""
    profile_path = PROFILES_DIR / f"{name}.json"
    if not profile_path.exists():
        return None
    try:
        return json.loads(profile_path.read_text())
    except Exception:
        return None


def list_profiles():
    """List all available profile names."""
    if not PROFILES_DIR.exists():
        return []
    profiles = []
    for path in sorted(PROFILES_DIR.glob("*.json")):
        profiles.append(path.stem)  # filename without .json extension
    return profiles


def delete_profile(name):
    """Delete a profile by name."""
    profile_path = PROFILES_DIR / f"{name}.json"
    if profile_path.exists():
        profile_path.unlink()
        return True
    return False


def save_current_state(profile, profile_name=None):
    """Save current application state for auto-restore.
    
    Args:
        profile: Dict with colors, modes, speeds
        profile_name: Name of active profile (None if no named profile active)
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    state = {
        "colors": profile.get("colors", {}),
        "modes": profile.get("modes", {}),
        "speeds": profile.get("speeds", {}),
        "active_profile": profile_name
    }
    CURRENT_PROFILE_FILE.write_text(json.dumps(state, indent=2))


def load_current_state():
    """Load previously saved application state.
    
    Returns:
        Tuple of (profile_dict, profile_name) or (None, None)
    """
    if not CURRENT_PROFILE_FILE.exists():
        return None, None
    try:
        state = json.loads(CURRENT_PROFILE_FILE.read_text())
        profile = {
            "colors": state.get("colors", {}),
            "modes": state.get("modes", {}),
            "speeds": state.get("speeds", {})
        }
        profile_name = state.get("active_profile")
        return profile, profile_name
    except Exception:
        return None, None
