#!/bin/bash
# Pre-release checklist script

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Pre-Release Checklist ===${NC}"
echo ""

# Check for uncommitted changes
echo -n "Checking for uncommitted changes... "
if [ -z "$(git status --porcelain)" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    echo "  Uncommitted changes found:"
    git status --short
    UNCOMMITTED=1
fi

# Check for unpushed commits
echo -n "Checking for unpushed commits... "
UNPUSHED=$(git log origin/main..HEAD --oneline 2>/dev/null | wc -l)
if [ "$UNPUSHED" -eq 0 ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⚠${NC}"
    echo "  $UNPUSHED unpushed commit(s)"
fi

# Check for open PRs (requires gh CLI)
if command -v gh &> /dev/null; then
    echo -n "Checking for open PRs... "
    OPEN_PRS=$(gh pr list --state open --json number --jq '. | length' 2>/dev/null || echo "?")
    if [ "$OPEN_PRS" = "0" ]; then
        echo -e "${GREEN}✓ (none)${NC}"
    elif [ "$OPEN_PRS" = "?" ]; then
        echo -e "${YELLOW}? (install gh CLI to check)${NC}"
    else
        echo -e "${YELLOW}⚠${NC}"
        echo "  $OPEN_PRS open PR(s) - consider merging first"
        gh pr list --state open
    fi
else
    echo -e "${YELLOW}⚠ GitHub CLI not installed${NC}"
    echo "  Install with: sudo apt install gh"
    echo "  Check PRs at: https://github.com/amatson97/liquidctl-gui/pulls"
fi

# Run tests
echo -n "Running tests... "
if PYTHONPATH=src python3 -m unittest tests.test_unit &>/dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    echo "  Tests failed! Run: PYTHONPATH=src python3 -m unittest tests.test_unit"
    TESTS_FAILED=1
fi

# Check CHANGELOG updated
echo -n "Checking CHANGELOG.md updated... "
if grep -q "## \[Unreleased\]" CHANGELOG.md 2>/dev/null || \
   grep -q "$(date +%Y-%m)" CHANGELOG.md 2>/dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⚠${NC}"
    echo "  Consider updating CHANGELOG.md"
fi

# Check README version
echo -n "Checking README version matches __init__.py... "
README_VERSION=$(grep -oP 'Version \K[0-9]+\.[0-9]+\.[0-9]+' README.md | head -1)
INIT_VERSION=$(grep -oP '__version__ = "\K[^"]+' src/liquidctl_gui/__init__.py)
if [ "$README_VERSION" = "$INIT_VERSION" ]; then
    echo -e "${GREEN}✓ ($INIT_VERSION)${NC}"
else
    echo -e "${YELLOW}⚠${NC}"
    echo "  README: $README_VERSION, __init__.py: $INIT_VERSION"
fi

echo ""
echo -e "${GREEN}=== Summary ===${NC}"

if [ -n "$UNCOMMITTED" ] || [ -n "$TESTS_FAILED" ]; then
    echo -e "${RED}✗ Issues found - fix before releasing${NC}"
    exit 1
else
    echo -e "${GREEN}✓ Ready for release!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Merge any pending PRs"
    echo "  2. Update CHANGELOG.md if needed"
    echo "  3. Run: ./scripts/prepare-release.sh"
fi
