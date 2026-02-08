#!/bin/bash
# Release automation script for liquidctl-gui
# Usage: ./scripts/release.sh [version]
# Example: ./scripts/release.sh 0.2.0

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get version from argument or prompt
if [ -z "$1" ]; then
    echo -e "${YELLOW}Enter version number (e.g., 0.2.0):${NC}"
    read VERSION
else
    VERSION=$1
fi

# Validate version format
if ! [[ $VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo -e "${RED}Error: Invalid version format. Use semantic versioning (e.g., 0.2.0)${NC}"
    exit 1
fi

echo -e "${GREEN}=== Releasing version $VERSION ===${NC}"
echo ""

# Detect if we're on a fork
ORIGIN_URL=$(git config --get remote.origin.url)
if [[ ! "$ORIGIN_URL" =~ "amatson97/liquidctl-gui" ]]; then
    echo -e "${YELLOW}⚠ Warning: This appears to be a fork${NC}"
    echo "  Origin: $ORIGIN_URL"
    echo "  Official: https://github.com/amatson97/liquidctl-gui"
    echo ""
    echo "You can create a release on your fork, but it won't affect the official repo."
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# Check if working directory is clean
if [ -n "$(git status --porcelain)" ]; then
    echo -e "${YELLOW}Warning: Working directory has uncommitted changes.${NC}"
    echo "Uncommitted files:"
    git status --short
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# Check if version is already tagged
if git rev-parse "v$VERSION" >/dev/null 2>&1; then
    echo -e "${RED}Error: Tag v$VERSION already exists!${NC}"
    exit 1
fi

# Update version in __init__.py
echo -e "${GREEN}[1/6] Updating version in __init__.py...${NC}"
sed -i "s/__version__ = \".*\"/__version__ = \"$VERSION\"/" src/liquidctl_gui/__init__.py

# Verify the update
CURRENT_VERSION=$(grep -oP '__version__ = "\K[^"]+' src/liquidctl_gui/__init__.py)
if [ "$CURRENT_VERSION" != "$VERSION" ]; then
    echo -e "${RED}Error: Failed to update version in __init__.py${NC}"
    exit 1
fi
echo "  ✓ Version updated to $VERSION"

# Run tests
echo -e "${GREEN}[2/6] Running tests...${NC}"
if PYTHONPATH=src python -m unittest tests.test_unit 2>&1 | tail -1 | grep -q "OK"; then
    echo "  ✓ All tests passed"
else
    echo -e "${RED}Error: Tests failed!${NC}"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# Stage version changes
echo -e "${GREEN}[3/6] Staging changes...${NC}"
git add src/liquidctl_gui/__init__.py
if [ -n "$(git diff --cached --name-only)" ]; then
    echo "  ✓ Changes staged"
else
    echo "  ℹ No changes to stage"
fi

# Commit version bump
echo -e "${GREEN}[4/6] Creating commit...${NC}"
if git diff --cached --quiet; then
    echo "  ℹ No changes to commit"
else
    git commit -m "chore: bump version to $VERSION"
    echo "  ✓ Commit created"
fi

# Create annotated tag
echo -e "${GREEN}[5/6] Creating git tag v$VERSION...${NC}"
git tag -a "v$VERSION" -m "Release version $VERSION

See CHANGELOG.md for details."
echo "  ✓ Tag v$VERSION created"

# Summary
echo ""
echo -e "${GREEN}=== Release prepared successfully! ===${NC}"
echo ""
echo "Next steps:"
echo "  1. Review the changes:"
echo "     git show v$VERSION"
echo ""
echo "  2. Push to GitHub:"
echo "     git push origin main"
echo "     git push origin v$VERSION"
echo ""
echo "  3. Create GitHub release:"
echo "     gh release create v$VERSION --title \"Release v$VERSION\" --notes-file CHANGELOG.md"
echo "     OR visit: https://github.com/amatson97/liquidctl-gui/releases/new?tag=v$VERSION"
echo ""
read -p "Push now? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}Pushing to origin...${NC}"
    
    # Try to push - will fail if user doesn't have permissions
    if git push origin main 2>/dev/null || git push origin master 2>/dev/null; then
        echo -e "${GREEN}✓ Pushed commits to main${NC}"
    else
        echo -e "${RED}✗ Failed to push to main${NC}"
        echo "  This may be because:"
        echo "  - You don't have write access to the repository"
        echo "  - You're working on a fork (use your fork's remote instead)"
        echo "  - Network issues"
        exit 1
    fi
    
    if git push origin "v$VERSION" 2>/dev/null; then
        echo -e "${GREEN}✓ Pushed tag v$VERSION${NC}"
        echo ""
        echo "Create GitHub release at:"
        echo "https://github.com/amatson97/liquidctl-gui/releases/new?tag=v$VERSION"
    else
        echo -e "${RED}✗ Failed to push tag${NC}"
        echo "  If working on a fork, you can create a release there instead."
        exit 1
    fi
else
    echo "Remember to push manually when ready."
    echo ""
    echo "To push to your fork instead of upstream:"
    echo "  git remote -v  # Check your remotes"
    echo "  git push YOUR_FORK_NAME main"
    echo "  git push YOUR_FORK_NAME v$VERSION"
fi
