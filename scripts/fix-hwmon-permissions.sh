#!/bin/bash
# Helper script called by udev to fix hwmon permissions
# Sets group ownership and permissions on pwm control files

HWMON_PATH="$1"

if [ -z "$HWMON_PATH" ]; then
    exit 1
fi

# Fix permissions on pwm files (fan/pump control)
for file in "$HWMON_PATH"/pwm[0-9]* ; do
    if [ -e "$file" ]; then
        chgrp liquidctl "$file" 2>/dev/null
        chmod 0660 "$file" 2>/dev/null
    fi
done

# Fix permissions on sensor files (optional - read-only)
for file in "$HWMON_PATH"/temp[0-9]*_input "$HWMON_PATH"/fan[0-9]*_input ; do
    if [ -e "$file" ]; then
        chgrp liquidctl "$file" 2>/dev/null
        chmod 0440 "$file" 2>/dev/null
    fi
done

exit 0
