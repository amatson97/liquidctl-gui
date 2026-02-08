#!/bin/bash
# Interactive release preparation script
# Helps you prepare CHANGELOG and version updates before release

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}=== Release Preparation Wizard ===${NC}"
echo ""

# Get current version
CURRENT_VERSION=$(grep -oP '__version__ = "\K[^"]+' src/liquidctl_gui/__init__.py)
echo -e "Current version: ${BLUE}$CURRENT_VERSION${NC}"
echo ""

# Suggest next version
IFS='.' read -ra VERSION_PARTS <<< "$CURRENT_VERSION"
MAJOR=${VERSION_PARTS[0]}
MINOR=${VERSION_PARTS[1]}
PATCH=${VERSION_PARTS[2]}

NEXT_PATCH="$MAJOR.$MINOR.$((PATCH + 1))"
NEXT_MINOR="$MAJOR.$((MINOR + 1)).0"
NEXT_MAJOR="$((MAJOR + 1)).0.0"

echo "Version bump options:"
echo "  1) Patch release: $NEXT_PATCH (bug fixes)"
echo "  2) Minor release: $NEXT_MINOR (new features)"
echo "  3) Major release: $NEXT_MAJOR (breaking changes)"
echo "  4) Custom version"
echo ""
read -p "Select option (1-4): " OPTION

case $OPTION in
    1) NEW_VERSION=$NEXT_PATCH ;;
    2) NEW_VERSION=$NEXT_MINOR ;;
    3) NEW_VERSION=$NEXT_MAJOR ;;
    4) 
        read -p "Enter custom version: " NEW_VERSION
        ;;
    *)
        echo "Invalid option"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}Preparing release: $CURRENT_VERSION → $NEW_VERSION${NC}"
echo ""

# Checklist
echo -e "${YELLOW}Pre-release checklist:${NC}"
echo ""
echo "[ ] Run tests: PYTHONPATH=src python -m unittest tests.test_unit"
echo "[ ] Test the app manually with: ./launch.sh"
echo "[ ] Update CHANGELOG.md with new version section"
echo "[ ] Review and update README.md if needed"
echo "[ ] Commit all outstanding changes"
echo ""

read -p "Continue with release? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# Run the actual release
exec ./scripts/release.sh "$NEW_VERSION"
