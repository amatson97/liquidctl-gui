# Profile Management - Bug Fixes and New Features

## Issues Fixed

### 1. **Profile State Not Retained**
**Problem:** When users saved profiles and restarted the app, their settings were lost because:
- Profile state (`last_colors`, `last_modes`, `last_speeds`) initialized as empty dictionaries on startup
- Only `example.json` was auto-loaded, so other saved profiles were ignored
- No automatic state preservation between sessions

**Solution:**
- Added automatic state saving to `~/.liquidctl-gui/current_profile.json` whenever colors, modes, or speeds are changed
- Auto-restore previous session state on startup
- All user actions (color changes, mode changes, speed changes) now trigger auto-save

### 2. **No Profile List/Management**
**Problem:** Users couldn't see or manage their saved profiles:
- Profiles were saved via file chooser anywhere on the filesystem
- No way to list existing profiles
- No built-in profile browser or deletion capability

**Solution:**
- Created dedicated profiles directory: `~/.liquidctl-gui/profiles/`
- Added profile browser dialog with list/load/delete capabilities
- Profile names are user-friendly (no need to remember file paths)

### 3. **Profiles Accumulating Unwanted Settings**
**Problem:** Saved profiles would accumulate settings from previous configurations:
- Loading a profile would merge with existing state instead of replacing it
- Saving a new profile would include settings from previously loaded profiles
- Profiles became bloated with unintended settings over time

**Solution:**
- Changed `apply_profile_data()` to replace state instead of merging
- Each profile now contains only its own settings
- Loading a profile completely replaces the current state

## New Features

### Profile Directory Structure
```
~/.liquidctl-gui/
├── config.json                 # App configuration
├── current_profile.json        # Auto-saved session state
└── profiles/                   # User profiles
    ├── gaming.json
    ├── quiet.json
    └── my_profile.json
```

### Profile Management Functions

All profiles are stored in `~/.liquidctl-gui/profiles/`:

1. **Save Profile** - Prompts for a profile name and saves to profiles directory
2. **Load Profile** - Shows browser with all saved profiles, allows loading or deletion
3. **Auto-Save** - Automatically saves current state when any setting changes
4. **Auto-Load** - Restores previous session on startup

### Auto-Save Behavior

The app now automatically saves your current state when you:
- Change LED colors
- Change LED modes  
- Change fan/pump speeds
- Apply preset colors
- Apply preset speeds

This ensures your settings are preserved even if you close the app without explicitly saving a profile.

### Profile Browser

The new Load Profile dialog provides:
- **List View** - See all your saved profiles at a glance
- **Load Button** - Apply a selected profile
- **Delete Button** - Remove unwanted profiles with confirmation
- **Scrollable List** - Easy navigation even with many profiles

## Usage Examples

### Saving a Profile
1. Configure your devices (colors, modes, speeds)
2. Click "Save Profile"
3. Enter a descriptive name (e.g., "gaming", "quiet", "blue_theme")
4. Click "Save"

Your profile is now saved in `~/.liquidctl-gui/profiles/<name>.json`

### Loading a Profile
1. Click "Load Profile"
2. Select a profile from the list
3. Click "Open" to apply it

All colors, modes, and speeds from the profile will be applied to your devices.

### Deleting a Profile
1. Click "Load Profile"
2. Select the profile to delete
3. Click "Delete"
4. Confirm the deletion

### Session Restore

When you start the app:
1. It automatically loads your last session state
2. All your previous settings are restored
3. No need to manually load a profile each time

## Migration Notes

### For Existing Users

If you have an existing `~/.liquidctl-gui/example.json` file:
- It will still auto-load on startup (for backward compatibility)
- Consider saving it as a named profile using "Save Profile"
- Future sessions will use the auto-saved current state

### For New Users

The app will:
- Create `~/.liquidctl-gui/profiles/` directory automatically
- Auto-save your settings as you work
- Restore your settings when you restart the app

## Technical Details

### New Functions in `lib/config.py`

- `save_profile(profile, name)` - Save a named profile
- `load_profile(name)` - Load a named profile
- `list_profiles()` - List all available profiles
- `delete_profile(name)` - Delete a profile
- `save_current_state(profile)` - Auto-save current state
- `load_current_state()` - Load auto-saved state

### Modified Functions in `app.py`

- `save_profile()` - Now prompts for name and uses profile directory
- `load_profile()` - Now shows profile browser with list/delete
- `apply_profile_data()` - New helper to apply profile data
- `_auto_save_state()` - Auto-saves state when settings change
- All color/mode/speed methods now call `_auto_save_state()`

### Startup Sequence

1. Load app configuration from `config.json`
2. Load devices (from config or detect new)
3. Try to load previous session from `current_profile.json`
4. If no session state, try loading `example.json` (backward compatibility)
5. Auto-initialize devices if enabled

## Testing

Run the test script to verify profile management:

```bash
python3 test_profile_management.py
```

This tests:
- Profile saving
- Profile listing
- Profile loading
- Profile deletion
- Current state save/load
- Data integrity

## Support

If you encounter issues:
1. Check `~/.liquidctl-gui/` directory exists and is writable
2. Verify profile files are valid JSON
3. Check logs for error messages
4. Report issues with profile file contents (sanitize device names if needed)
