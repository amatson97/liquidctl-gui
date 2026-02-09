# Release Workflow Guide

## Overview

This guide explains how to manage contributions via pull requests and create releases.

## Fork & PR Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                    Contributor's Fork                       │
│  1. Fork repo                                               │
│  2. git clone https://github.com/CONTRIBUTOR/liquidctl-gui  │
│  3. git checkout -b feature/my-feature                      │
│  4. Make changes                                            │
│  5. git push origin feature/my-feature                      │
│  6. Open Pull Request                                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Maintainer Review                         │
│  1. Review PR on GitHub                                     │
│  2. Request changes or approve                              │
│  3. Merge to main (via GitHub UI)                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Local Repository                         │
│  git checkout main                                          │
│  git pull origin main      # Pull merged PR                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 Prepare for Release (Maintainer)            │
│  1. Update CHANGELOG.md with merged PRs                     │
│  2. ./scripts/pre-release-check.sh                          │
│  3. ./scripts/prepare-release.sh                            │
│  4. git push origin main && git push origin v0.X.Y          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions (Automatic)               │
│  - Automatically creates GitHub Release                     │
│  - Attaches CHANGELOG.md                                    │
│  - Tags the release                                         │
└─────────────────────────────────────────────────────────────┘
```

## Detailed Steps

### For Contributors (External PRs)

1. **Fork the repository**
   - Visit https://github.com/amatson97/liquidctl-gui
   - Click "Fork" button
   - Clone your fork locally

2. **Create a feature branch**
   ```bash
   git checkout -b feature/add-fan-curves
   # or
   git checkout -b fix/status-display-bug
   ```

3. **Make your changes**
   - Write code
   - Add tests
   - Update docs

4. **Test thoroughly**
   ```bash
   PYTHONPATH=src python3 -m unittest tests.test_unit
   ./launch.sh  # Manual testing
   ```

5. **Push and create PR**
   ```bash
   git push origin feature/add-fan-curves
   ```
   - Go to GitHub and create Pull Request
   - Fill out the PR template
   - Wait for review

### For Maintainers (Merging PRs)

#### Reviewing PRs

1. **Check the changes**
   - Read the code on GitHub
   - Check tests pass
   - Verify it follows contribution guidelines

2. **Test locally (optional but recommended)**
   ```bash
   # Add contributor's fork as remote
   git remote add contributor https://github.com/CONTRIBUTOR/liquidctl-gui
   git fetch contributor
   
   # Check out the PR branch
   git checkout -b pr-123 contributor/feature/add-fan-curves
   
   # Test it
   ./launch.sh
   PYTHONPATH=src python3 -m unittest tests.test_unit
   
   # Go back to main when done
   git checkout main
   git branch -D pr-123
   ```

3. **Merge the PR**
   - Use GitHub UI
   - **Recommended**: "Squash and merge" for clean history
   - Alternative: "Merge commit" to preserve all commits
   - Add meaningful merge commit message

#### Preparing a Release After Merging PRs

1. **Pull the merged changes**
   ```bash
   git checkout main
   git pull origin main
   ```

2. **Update CHANGELOG.md**
   ```markdown
   ## [Unreleased]
   
   ### Added
   - Fan curve editor (#45) @contributor1
   - Theme support (#47) @contributor2
   
   ### Fixed
   - Status display bug (#46) @contributor3
   ```

3. **Run pre-release checks**
   ```bash
   ./scripts/pre-release-check.sh
   ```
   
   This checks:
   - No uncommitted changes
   - No open PRs (if you want to include everything)
   - Tests pass
   - CHANGELOG updated
   - Versions consistent

4. **Create the release**
   ```bash
   ./scripts/prepare-release.sh
   ```
   
   - Choose version type (patch/minor/major)
   - Script will:
     - Update version in `__init__.py`
     - Run tests
     - Create commit
     - Create tag
     - Optionally push

5. **Verify and push (if not auto-pushed)**
   ```bash
   git log -1  # Review the version bump commit
   git tag     # Verify tag was created
   
   git push origin main
   git push origin v0.3.0
   ```

6. **GitHub Actions takes over**
   - Automatically creates GitHub Release
   - Attaches CHANGELOG content
   - Release is published!

## Tips

### Managing Multiple PRs

If you have several PRs to merge before a release:

1. Merge all PRs first (don't release yet)
2. Pull all merged changes: `git pull origin main`
3. Update CHANGELOG with all merged items
4. Then run release script once

### Crediting Contributors

In CHANGELOG.md, credit contributors:
```markdown
### Added
- New feature description (#PR_NUMBER) @username
```

In merge commits:
```
Merge pull request #45 from contributor/feature-branch

Add fan curve editor

Thanks to @contributor for this contribution!
```

### Emergency Hotfix PRs

For critical bugs requiring immediate release:

1. Merge the fix PR
2. Pull changes
3. Update CHANGELOG (just the fix)
4. Release as patch version: `./scripts/release.sh 0.2.1`
5. Push immediately

### Keeping Your Fork Synced (for contributors)

Contributors should sync their forks:

```bash
# Add upstream (one time)
git remote add upstream https://github.com/amatson97/liquidctl-gui

# Sync fork
git checkout main
git fetch upstream
git merge upstream/main
git push origin main
```

## Common Questions

**Q: Can I merge my own PR?**  
A: Yes, if you're the maintainer. But for larger projects, have another maintainer review.

**Q: Should I merge PRs to main or develop?**  
A: Main branch directly. We follow trunk-based development.

**Q: What if a PR conflicts with main?**  
A: Ask contributor to rebase or use GitHub's conflict resolution tool.

**Q: Can I edit a contributor's PR?**  
A: Yes, if they allow maintainer edits (default). Or ask them to make changes.

**Q: How do I test a PR without merging?**  
A: Check out the PR branch locally (see "Test locally" section above).

## Automation Status

| Task | Automated | Tool |
|------|-----------|------|
| PR merge | Manual via GitHub | GitHub UI |
| Update CHANGELOG | Manual | Text editor |
| Version bump | Automated | `release.sh` |
| Run tests | Automated | `release.sh` |
| Create git tag | Automated | `release.sh` |
| Create GitHub release | Automated | GitHub Actions |
| Attach changelog | Automated | GitHub Actions |

## Further Reading

- [CONTRIBUTING.md](../CONTRIBUTING.md) - For contributors
- [scripts/README.md](../scripts/README.md) - Release scripts documentation
- [GitHub PR docs](https://docs.github.com/en/pull-requests) - GitHub's PR guide
