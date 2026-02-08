"""User configuration helpers for liquidctl-gui."""

import json
from copy import deepcopy
from pathlib import Path


CONFIG_DIR = Path.home() / ".liquidctl-gui"
CONFIG_FILE = CONFIG_DIR / "config.json"


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
