#!/bin/bash
# Debug script - Run liquidctl-gui with detailed logging
# Logs are saved to app_debug.log in the project root

cd "$(dirname "$0")/.."
./launch.sh 2>&1 | tee app_debug.log
