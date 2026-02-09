# Liquidctl GUI Refactoring Plan

## Current Issues
1. **app.py is 1708 lines** - Single monolithic file
2. **Inconsistent error handling** - Different patterns across codebase  
3. **Poor error context** - Hard to diagnose issues
4. **Mixed concerns** - UI, business logic, device control all together
5. **Limited debugging info** - Need structured logging

## Refactoring Strategy

### Phase 1: Error Handling & Logging (IMMEDIATE)
✅ Create centralized error handling module
✅ Add structured logging with context
✅ Standardize error message format
✅ Add operation tracing for debugging

### Phase 2: Code Organization (HIGH PRIORITY)
- Extract device operations from app.py → `lib/device_controller.py`
- Extract profile management → `lib/profile_manager.py`  
- Extract UI builders → `lib/ui_builders.py`
- Keep app.py focused on window management only

### Phase 3: Documentation (MEDIUM PRIORITY)
- Add type hints to all function signatures
- Add comprehensive docstrings with examples
- Document error codes and their meanings
- Create architecture diagram

### Phase 4: Testing Infrastructure (ONGOING)
- Expand unit tests for error scenarios
- Add integration tests
- Add device simulation tests

## Key Improvements for AI Debugging

1. **Structured Error Messages**
   ```python
   # Before: "Device not found"
   # After: "[ERROR][DEVICE_INIT] Device 'NZXT Kraken X' not found. Available: ['x53', 'Gigabyte RGB Fusion']. Operation: initialize. Context: auto-init-startup"
   ```

2. **Operation Tracing**
   ```python
   # Add trace IDs to operations
   [TRACE:abc123][SET_COLOR] device=NZXT channel=ring color=#ff0000 → API call → SUCCESS
   ```

3. **Clear Module Boundaries**
   - `app.py` - Window management only
   - `device_controller.py` - All device operations
   - `profile_manager.py` - Profile save/load/apply
   - `error_handler.py` - Centralized error handling

## Files to Create
- `src/liquidctl_gui/lib/error_handler.py` - Error handling utilities
- `src/liquidctl_gui/lib/device_controller.py` - Device operations
- `src/liquidctl_gui/lib/profile_manager.py` - Profile management
- `docs/ARCHITECTURE.md` - System architecture
- `docs/ERROR_CODES.md` - Error code reference

## Implementation Order
1. Create error_handler.py with logging config ← START HERE
2. Update all files to use new error handler
3. Extract device operations
4. Extract profile management
5. Add comprehensive docstrings
6. Update tests
