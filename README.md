# Fleet Edge Release Notes Generator

Generates diff-style release notes from CI Glue promotions for any Fleet Edge
release (R.4.x, R.5.x, …).

## Prerequisites

- Python 3.10+  (no third-party packages needed — stdlib only)
- A CI Glue API token

## Setup (one-time, per person)

**1. Get your CI Glue token**

Log in to [CI Glue](https://ci-glue.fleetedgeportal.com) and copy your API token,
then save it:

```bash
# macOS / Linux
mkdir -p ~/.config/ci-glue
echo "YOUR_TOKEN_HERE" > ~/.config/ci-glue/token

# Windows (Git Bash / PowerShell)
mkdir "$HOME\.config\ci-glue" -Force
"YOUR_TOKEN_HERE" | Out-File "$HOME\.config\ci-glue\token" -Encoding ascii
```

Alternatively, set the environment variable:

```bash
export CI_GLUE_TOKEN=your_token_here   # macOS/Linux
$env:CI_GLUE_TOKEN="your_token_here"   # PowerShell
```

**2. Clone this repo**

```bash
git clone <repo-url>
cd <repo-name>
```

That's it — `releases.json` is already in the repo with current mappings.

---

## Usage

### Most common commands

```bash
# Diff notes for the latest build in a release (main workflow)
python release_notes_generator.py --release R.5.1 --build latest

# Save to a markdown file
python release_notes_generator.py --release R.5.1 --build latest --output R5.1_notes.md

# Diff notes for a specific build
python release_notes_generator.py --release R.5.1 --build 2.16.443.8525-master --output notes.md

# All promotions in a release (full manifest, no diff)
python release_notes_generator.py --release R.4.4 --output R4.4_all.md
```

### Discovery

```bash
# Show all branches and their mapped release labels
python release_notes_generator.py --list-branches

# Show stored release→branch mappings
python release_notes_generator.py --list-releases

# Show every individual CI Glue promotion
python release_notes_generator.py --list-promotions
```

### Output formats

```bash
# Default: plain text to stdout
python release_notes_generator.py --release R.5.1 --build latest

# Markdown file
python release_notes_generator.py --release R.5.1 --build latest --output notes.md

# Force markdown to stdout
python release_notes_generator.py --release R.5.1 --build latest --format markdown

# Raw JSON (full API data)
python release_notes_generator.py --release R.5.1 --build latest --format json
```

---

## Adding a new release mapping

When a new release branch starts, add the mapping to `releases.json` and commit it:

```bash
python release_notes_generator.py --map-release "R.6.1=2.17"
git add releases.json
git commit -m "Add release mapping R.6.1=2.17"
git push
```

Everyone on the team gets the new mapping on their next `git pull`.

---

## How release labels map to CI Glue versions

CI Glue tracks builds with internal version strings like `2.16.443.8525-master`.
The product release labels (R.5.1, R.4.4 …) are JIRA labels and aren't stored in
CI Glue directly. The `releases.json` file provides the bridge:

| Release | CI Glue prefix | Notes |
|---------|---------------|-------|
| R.4.2   | 2.12          | hotfix branch (`-R4.2-update` suffix) |
| R.4.3   | 2.14          | master branch |
| R.4.4   | 2.15          | master branch |
| R.5.1   | 2.16          | master branch (in QA as of Oct 2026) |

To identify the prefix for a new release, run `--list-branches` and look for the
newest major.minor group that appeared around the release start date.

---

## Power-user flags (no release map needed)

```bash
# By version prefix directly
python release_notes_generator.py --version-prefix 2.16 --build latest

# By date range
python release_notes_generator.py --after 2026-09-01 --before 2026-10-15

# Diff against an explicit baseline
python release_notes_generator.py --release R.5.1 --build latest \
    --compare-to 2.15.451.8446-master
```
