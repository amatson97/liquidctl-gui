# Contributing

Thanks for contributing! This is a small GTK app and feedback is welcome.

## Ways to Contribute

- **Bug Reports**: Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md)
- **Feature Requests**: Use the [feature request template](.github/ISSUE_TEMPLATE/feature_request.md)
- **Code Contributions**: Submit a pull request (see below)
- **Documentation**: Improvements to docs are always welcome
- **Testing**: Test on different hardware and report results

## Development Setup

The project includes a launcher script that automates the recommended setup:

```bash
./launch.sh
```

This will create a `.venv`, install `liquidctl` into it, and can prompt to install\
GTK system packages on Debian/Ubuntu. If you prefer manual setup, you can create\
a virtual environment and install `liquidctl` yourself.

## Run
```
PYTHONPATH=src python3 -m liquidctl_gui
```

## Tests
```
PYTHONPATH=src python3 -m unittest tests.test_unit
```

## Pull Request Process

### For Contributors (Forks):

1. **Fork the repository**
   - Click "Fork" on GitHub
   - Clone your fork: `git clone https://github.com/YOUR_USERNAME/liquidctl-gui.git`

2. **Create a feature branch**
   ```bash
   git checkout -b feature/my-new-feature
   # or
   git checkout -b fix/bug-description
   ```

3. **Make your changes**
   - Write clear, commented code
   - Follow existing code style
   - Add tests if applicable

4. **Test your changes**
   ```bash
   PYTHONPATH=src python3 -m unittest tests.test_unit
   ./launch.sh  # Manual testing
   ```

5. **Commit with clear messages**
   ```bash
   git add .
   git commit -m "feat: add new feature description"
   # or
   git commit -m "fix: resolve issue with X"
   ```

6. **Push to your fork**
   ```bash
   git push origin feature/my-new-feature
   ```

7. **Open a Pull Request**
   - Go to the original repo on GitHub
   - Click "New Pull Request"
   - Select your fork and branch
   - Fill out the PR template
   - Submit!

### For Maintainers (Merging PRs):

1. **Review the PR**
   - Check code quality
   - Verify tests pass
   - Test manually if needed

2. **Merge via GitHub UI**
   - Use "Squash and merge" for clean history (recommended)
   - Or "Merge commit" to preserve all commits
   - Add PR number to merge commit message

3. **Pull merged changes locally**
   ```bash
   git checkout main
   git pull origin main
   ```

4. **Update CHANGELOG.md**
   - Add merged features/fixes to upcoming version section
   - Credit contributors

5. **Release when ready** (see below)

## Release Process (Maintainers Only)

> **Note for Contributors**: These scripts work on forks too, but you won't be able to push tags to the upstream repository (requires write access). If you're testing release automation on your fork, the scripts will work locally but won't affect the official repository.

After merging PRs and updating CHANGELOG:

```bash
# Pre-release validation (recommended first step)
./scripts/pre-release-check.sh

# Interactive release wizard
./scripts/prepare-release.sh

# Or direct
./scripts/release.sh 0.3.0
```

The script will:
- Update version number
- Run tests
- Create commit and tag **locally**
- Prompt to push (which triggers GitHub Actions release)

**Repository permissions required to complete release:**
- Write access to push to `main` branch
- Permission to push tags
- Ability to trigger GitHub Actions workflows

See [scripts/README.md](scripts/README.md) and [docs/RELEASE_WORKFLOW.md](docs/RELEASE_WORKFLOW.md) for details.

## Code Style Guidelines

- Use 4 spaces for indentation
- Follow PEP 8 where practical
- Add docstrings to classes and non-obvious functions
- Keep functions focused and reasonably sized
- Comment complex logic

## Commit Message Format (Optional but Recommended)

We loosely follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat: add new feature`
- `fix: resolve bug with X`
- `docs: update README`
- `test: add tests for Y`
- `refactor: restructure Z`
- `chore: update dependencies`

## Issues and PRs
- Please describe your hardware setup and OS version.
- Include logs or error output when relevant.
- Keep PRs small and focused when possible.
