#!/usr/bin/env python3
"""
Release Notes Generator - CI Glue (Fleet Edge)

Generates diff-style or manifest-style release notes from CI Glue promotions.
Release labels (R.5.1, R.4.4 …) are mapped to CI Glue version prefixes (2.16,
2.15 …) via a local config file that you populate once.

Quick start
-----------
  # 1. See all known branches (helps you identify which prefix = which release):
  python release_notes_generator.py --list-branches

  # 2. Store the mapping (only needed once per release):
  python release_notes_generator.py --map-release "R.5.1=2.16"
  python release_notes_generator.py --map-release "R.4.4=2.15"
  python release_notes_generator.py --map-release "R.4.3=2.14"

  # 3a. Diff notes for the latest build in a release:
  python release_notes_generator.py --release R.5.1 --build latest

  # 3b. Diff notes for a specific build:
  python release_notes_generator.py --release R.5.1 --build 2.16.443.8525-master

  # 3c. All promotions in a release (manifest view):
  python release_notes_generator.py --release R.5.1

  # Save to markdown file:
  python release_notes_generator.py --release R.5.1 --build latest --output notes.md

  # Show stored release mappings:
  python release_notes_generator.py --list-releases

  # List all promotions:
  python release_notes_generator.py --list-promotions

Power-user flags (no release map needed)
-----------------------------------------
  python release_notes_generator.py --build 2.16.443.8525-master
  python release_notes_generator.py --build 2.16.443.8525-master --compare-to 2.16.203.8402-master
  python release_notes_generator.py --version-prefix 2.16 --after 2026-09-01
  python release_notes_generator.py --after 2026-10-01

Token
-----
  Reads from ~/.config/ci-glue/token.  Override with CI_GLUE_TOKEN env var.

Release map
-----------
  Stored at ~/.config/ci-glue/releases.json
  Format: { "R.5.1": "2.16", "R.4.4": "2.15", ... }
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TOKEN_FILE = Path.home() / ".config" / "ci-glue" / "token"
BASE_URL   = "https://ci-glue.fleetedgeportal.com/api"
PAGE_SIZE  = 100

# releases.json is looked up next to this script first (so it can be committed
# to a shared repo), then falls back to the per-user config directory.
_SCRIPT_DIR      = Path(__file__).resolve().parent
_LOCAL_MAP       = _SCRIPT_DIR / "releases.json"
_USER_MAP        = Path.home() / ".config" / "ci-glue" / "releases.json"
RELEASE_MAP_FILE = _LOCAL_MAP if _LOCAL_MAP.exists() else _USER_MAP

# ---------------------------------------------------------------------------
# Auth / HTTP helpers
# ---------------------------------------------------------------------------

def load_token() -> str:
    env_token = os.environ.get("CI_GLUE_TOKEN")
    if env_token:
        return env_token.strip()
    if not TOKEN_FILE.exists():
        sys.exit(
            f"ERROR: Token file not found at {TOKEN_FILE}\n"
            "Run the CI Glue login flow or set CI_GLUE_TOKEN=<token>."
        )
    return TOKEN_FILE.read_text().strip()


def fetch_json(url: str, token: str, verbose: bool = False) -> dict:
    if verbose:
        print(f"  GET {url}", flush=True)
    req = urllib.request.Request(url, headers={"Authorization": f"Token {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        sys.exit(f"HTTP {e.code} for {url}\n{body}")


def fetch_all_pages(endpoint: str, token: str, verbose: bool = False) -> list[dict]:
    results = []
    url = f"{BASE_URL}/{endpoint}?limit={PAGE_SIZE}"
    while url:
        data = fetch_json(url, token, verbose=verbose)
        results.extend(data.get("results", []))
        url = data.get("next")
    return results


def fetch_one(endpoint: str, uid: str, token: str, verbose: bool = False) -> dict | None:
    try:
        return fetch_json(f"{BASE_URL}/{endpoint}/{uid}/", token, verbose=verbose)
    except SystemExit:
        return None

# ---------------------------------------------------------------------------
# Release map (persistent config)
# ---------------------------------------------------------------------------

def load_release_map() -> dict[str, str]:
    if RELEASE_MAP_FILE.exists():
        return json.loads(RELEASE_MAP_FILE.read_text())
    return {}


def save_release_map(mapping: dict[str, str]) -> None:
    # Write to the local (repo) file if it exists, otherwise the user config file.
    target = _LOCAL_MAP if _LOCAL_MAP.exists() else _USER_MAP
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(mapping, indent=2, sort_keys=True))


def normalize_label(label: str) -> str:
    """Normalise 'r.5.1', 'R5.1', 'R 5.1' → 'R.5.1'."""
    label = label.strip().upper()
    # Strip leading R and dots/spaces
    body = label.lstrip("R").lstrip(". ")
    # Rebuild as R.X.Y
    parts = re.split(r"[.\s_-]+", body)
    return "R." + ".".join(p for p in parts if p)


def lookup_prefix(label: str, release_map: dict[str, str],
                  all_promotions: list[dict]) -> str | None:
    """
    Find the version prefix for a release label.
    1. Exact match in release map (after normalisation).
    2. Case-insensitive key match.
    3. Auto-detect from branch names in promotion version strings (e.g. R4.2-update).
    """
    norm = normalize_label(label)

    # 1. Normalised exact match
    if norm in release_map:
        return release_map[norm]

    # 2. Case-insensitive map search
    for k, v in release_map.items():
        if k.upper() == norm.upper():
            return v

    # 3. Auto-detect from branch names like "2.12.375.7998-R4.2-update"
    # Collapse label to digits: R.4.2 → "42", R.5.1 → "51"
    digits = re.sub(r"[^0-9]", "", norm)  # "42", "51", etc.
    if digits:
        for p in fleet_edge_promotions(all_promotions):
            vs = (p.get("version_being_promoted") or {}).get("version_string", "")
            # Check if the branch part (after the build number) contains the label digits
            branch_part = vs.upper().replace("-", "").replace(".", "")
            if f"R{digits}" in branch_part:
                parts = vs.split(".")
                if len(parts) >= 2:
                    return f"{parts[0]}.{parts[1]}"

    return None

# ---------------------------------------------------------------------------
# Promotions
# ---------------------------------------------------------------------------

def get_all_promotions(token: str, verbose: bool) -> list[dict]:
    print("Fetching promotions from CI Glue …", flush=True)
    return fetch_all_pages("promotions", token, verbose=verbose)


def fleet_edge_promotions(promotions: list[dict]) -> list[dict]:
    """All COMPLETE fleet-edge promotions, in API order."""
    return [
        p for p in promotions
        if (p.get("promotion_type") == "COMPLETE"
            and (p.get("version_being_promoted") or {}).get("component") == "fleet-edge")
    ]


def filter_promotions(promotions: list[dict],
                      version_prefix: str | None = None,
                      after: str | None = None,
                      before: str | None = None) -> list[dict]:
    results = []
    for p in fleet_edge_promotions(promotions):
        vs      = (p.get("version_being_promoted") or {}).get("version_string", "")
        created = (p.get("created_at") or "")[:10]
        if version_prefix and not vs.startswith(version_prefix):
            continue
        if after  and created < after:
            continue
        if before and created > before:
            continue
        results.append(p)
    return results


def find_promotion_by_version(promotions: list[dict], vs: str) -> dict | None:
    for p in fleet_edge_promotions(promotions):
        if (p.get("version_being_promoted") or {}).get("version_string") == vs:
            return p
    return None


def latest_promotion_in_prefix(promotions: list[dict], prefix: str) -> dict | None:
    """Return the most recently created promotion whose version starts with prefix."""
    matches = filter_promotions(promotions, version_prefix=prefix)
    if not matches:
        return None
    return max(matches, key=lambda p: p.get("created_at") or "")


def find_previous_promotion(all_promotions: list[dict], target: dict) -> dict | None:
    """Previous promotion in the same major.minor branch, falling back to any previous."""
    fe = fleet_edge_promotions(all_promotions)
    target_vs = (target.get("version_being_promoted") or {}).get("version_string", "")
    parts = target_vs.split(".")
    branch_prefix = ".".join(parts[:2]) if len(parts) >= 2 else ""

    target_idx = next(
        (i for i, p in enumerate(fe)
         if (p.get("version_being_promoted") or {}).get("version_string") == target_vs),
        None,
    )
    if target_idx is None:
        return None

    for p in reversed(fe[:target_idx]):
        vs = (p.get("version_being_promoted") or {}).get("version_string", "")
        if branch_prefix and vs.startswith(branch_prefix):
            return p

    return fe[target_idx - 1] if target_idx > 0 else None

# ---------------------------------------------------------------------------
# Branch discovery (for --list-branches)
# ---------------------------------------------------------------------------

def branch_summary(promotions: list[dict], release_map: dict[str, str]) -> str:
    """Group fleet-edge promotions by major.minor and summarise each branch."""
    # Invert release map: prefix → label
    prefix_to_label: dict[str, str] = {}
    for label, prefix in release_map.items():
        prefix_to_label.setdefault(prefix, label)

    branches: dict[str, list[dict]] = defaultdict(list)
    for p in fleet_edge_promotions(promotions):
        vs = (p.get("version_being_promoted") or {}).get("version_string", "")
        parts = vs.split(".")
        key = ".".join(parts[:2]) if len(parts) >= 2 else vs
        branches[key].append(p)

    lines = [
        f"{'Branch':<10}  {'Release':<10}  {'Promotions':>11}  {'First':>12}  {'Latest':>12}  {'Environments'}",
        f"{'-'*10}  {'-'*10}  {'-'*11}  {'-'*12}  {'-'*12}  {'-'*20}",
    ]
    for branch in sorted(branches.keys(), key=lambda b: [int(x) for x in b.split(".") if x.isdigit()]):
        ps       = branches[branch]
        label    = prefix_to_label.get(branch, "—")
        count    = len(ps)
        dates    = sorted(p.get("created_at", "")[:10] for p in ps)
        first    = dates[0] if dates else "—"
        latest   = dates[-1] if dates else "—"
        envs     = ", ".join(sorted({p.get("environment", "?") for p in ps}))
        lines.append(f"{branch:<10}  {label:<10}  {count:>11}  {first:>12}  {latest:>12}  {envs}")

    lines += [
        "",
        "Tip: run  --map-release \"R.X.Y=<branch>\"  to store a mapping.",
    ]
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# Version / manifest helpers
# ---------------------------------------------------------------------------

def get_full_version(vid: str, token: str, verbose: bool) -> dict:
    return fetch_one("versions", vid, token, verbose=verbose) or {}


def manifest_dict(version: dict) -> dict[str, dict]:
    return {item["component"]: item for item in version.get("version_manifest", [])}


def diff_manifests(new_manifest: dict, old_manifest: dict) -> tuple[list, list]:
    changed, unchanged = [], []
    for comp, item in sorted(new_manifest.items()):
        old    = old_manifest.get(comp)
        old_vs = old["version_string"] if old else None
        new_vs = item["version_string"]
        if old_vs != new_vs:
            changed.append({
                "component":  comp,
                "from_vs":    old_vs or "NEW",
                "to_vs":      new_vs,
                "version_id": item.get("id"),
            })
        else:
            unchanged.append(comp)
    return changed, unchanged


def enrich_with_change_info(changed: list[dict], token: str, verbose: bool) -> list[dict]:
    enriched = []
    total = len(changed)
    for i, item in enumerate(changed, 1):
        vid = item.get("version_id")
        if vid:
            v  = get_full_version(vid, token, verbose)
            ch = v.get("change") or {}
            item = dict(item)
            item["sha"]     = (ch.get("commit_id") or "")[:8]
            item["branch"]  = ch.get("branch") or ""
            item["author"]  = ch.get("created_by") or ""
            item["message"] = (ch.get("change_message") or "").split("\n")[0].strip()[:120]
            item["issues"]  = ch.get("issues") or []
            item["repo"]    = ch.get("repository") or ""
        else:
            item = {**item, "sha": "", "branch": "", "author": "",
                    "message": "", "issues": [], "repo": ""}
        enriched.append(item)
        if i % 10 == 0 or i == total:
            print(f"  {i}/{total} components fetched", flush=True)
    return enriched


def group_by_jira(changed: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in changed:
        issues = item.get("issues") or []
        key    = ", ".join(sorted(issues)) if issues else ""
        groups[key].append(item)
    return dict(groups)

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def fmt_dt(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return iso

# ---------------------------------------------------------------------------
# Diff-style renderer
# ---------------------------------------------------------------------------

def render_diff_markdown(build_vs: str, prev_vs: str | None,
                         promoted_at: str, environment: str,
                         changed: list[dict], unchanged: list[str],
                         label: str) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Release Notes — {label}",
        f"",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Build | `{build_vs}` |",
        f"| Environment | `{environment}` |",
        f"| Promoted at | {promoted_at} |",
        f"| Generated | {generated} |",
        f"| Compared to | `{prev_vs or 'N/A — first promotion in branch'}` |",
        f"| Changed components | {len(changed)} |",
        f"| Unchanged components | {len(unchanged)} |",
        f"",
        "---", "",
    ]

    # Section 1: By JIRA ticket
    lines += ["## Changes by JIRA Ticket", ""]
    groups    = group_by_jira(changed)
    ticketed  = {k: v for k, v in groups.items() if k}
    no_ticket = groups.get("", [])

    for ticket_key in sorted(ticketed.keys()):
        items   = ticketed[ticket_key]
        summary = next((i["message"] for i in items if i.get("message")), "—")
        comps   = ", ".join(f"`{i['component']}`" for i in items)
        lines  += [f"### {ticket_key}", f"", f"**{summary}**  ", f"Components: {comps}", ""]

    if no_ticket:
        comps  = ", ".join(f"`{i['component']}`" for i in no_ticket)
        lines += ["### (No JIRA ticket)", f"", f"Components: {comps}", ""]

    lines += ["---", ""]

    # Section 2: Component version table
    lines += [
        "## Component Version Changes",
        f"",
        f"| Component | From | To | JIRA | Commit | Author | Message |",
        f"|-----------|------|----|------|--------|--------|---------|",
    ]
    for item in changed:
        issues = ", ".join(item.get("issues") or []) or "—"
        sha    = item.get("sha") or "—"
        author = item.get("author") or "—"
        msg    = item.get("message") or "—"
        lines.append(
            f"| `{item['component']}` "
            f"| `{item['from_vs']}` "
            f"| **`{item['to_vs']}`** "
            f"| {issues} "
            f"| `{sha}` "
            f"| {author} "
            f"| {msg} |"
        )

    lines += ["", "---", ""]

    # Section 3: Unchanged
    if unchanged:
        lines += [
            "## Unchanged Components", "",
            ", ".join(f"`{c}`" for c in sorted(unchanged)), "",
        ]

    return "\n".join(lines)


def render_diff_text(build_vs: str, prev_vs: str | None,
                     promoted_at: str, environment: str,
                     changed: list[dict], unchanged: list[str],
                     label: str) -> str:
    sep  = "=" * 72
    thin = "-" * 72
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        sep, f"  RELEASE NOTES — {label}", sep,
        f"  Build       : {build_vs}",
        f"  Environment : {environment}",
        f"  Promoted at : {promoted_at}",
        f"  Generated   : {generated}",
        f"  Compared to : {prev_vs or 'N/A — first promotion in branch'}",
        f"  Changed     : {len(changed)} components",
        f"  Unchanged   : {len(unchanged)} components",
        sep, "",
    ]

    lines += ["  CHANGES BY JIRA TICKET", thin, ""]
    groups    = group_by_jira(changed)
    ticketed  = {k: v for k, v in groups.items() if k}
    no_ticket = groups.get("", [])

    for ticket_key in sorted(ticketed.keys()):
        items   = ticketed[ticket_key]
        summary = next((i["message"] for i in items if i.get("message")), "—")
        comps   = ", ".join(i["component"] for i in items)
        lines  += [f"  [{ticket_key}]", f"    {summary}", f"    Components: {comps}", ""]

    if no_ticket:
        comps  = ", ".join(i["component"] for i in no_ticket)
        lines += ["  [No JIRA ticket]", f"    Components: {comps}", ""]

    lines += [thin, "", "  COMPONENT VERSION CHANGES", thin]
    col = f"  {'Component':<35} {'From':<12} {'To':<12} {'JIRA':<25} {'Author'}"
    lines += [col, "  " + "-" * 68]
    for item in changed:
        issues = ", ".join(item.get("issues") or []) or "—"
        author = item.get("author") or "—"
        lines.append(
            f"  {item['component']:<35} {item['from_vs']:<12} {item['to_vs']:<12} "
            f"{issues:<25} {author}"
        )
        if item.get("message"):
            lines.append(f"    → {item['message']}")

    if unchanged:
        lines += ["", thin, "", "  UNCHANGED COMPONENTS", thin]
        for i in range(0, len(unchanged), 4):
            lines.append("  " + "  ".join(sorted(unchanged)[i:i+4]))
        lines.append("")

    return "\n".join(lines)

# ---------------------------------------------------------------------------
# Manifest-only renderer (range/prefix mode)
# ---------------------------------------------------------------------------

def render_manifest_markdown(promotions: list[dict], label: str) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Release Notes — {label}", f"",
        f"**Generated:** {generated}  ",
        f"**Promotions included:** {len(promotions)}", f"",
        "---", "",
    ]
    for p in promotions:
        v    = p.get("version_being_promoted") or {}
        fv   = p.get("_full_version") or {}
        vs   = v.get("version_string", "—")
        env  = p.get("environment", "—")
        date = fmt_dt(p.get("created_at"))
        by   = p.get("status_set_by") or "—"

        lines += [
            f"## {vs}", f"",
            f"| Field | Value |", f"|-------|-------|",
            f"| Environment | `{env}` |",
            f"| Promoted at | {date} |",
            f"| Promoted by | {by} |", f"",
        ]
        manifest = fv.get("version_manifest") or []
        if manifest:
            lines += [
                f"**Component manifest ({len(manifest)} components):**", f"",
                "| Component | Version |", "|-----------|---------|",
            ]
            for item in sorted(manifest, key=lambda x: x.get("component", "")):
                lines.append(f"| `{item.get('component','—')}` | `{item.get('version_string','—')}` |")
            lines.append("")
        lines += ["---", ""]
    return "\n".join(lines)


def render_manifest_text(promotions: list[dict], label: str) -> str:
    sep  = "=" * 70
    thin = "-" * 70
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [sep, f"  RELEASE NOTES — {label}", sep,
             f"  Generated  : {generated}",
             f"  Promotions : {len(promotions)}", sep, ""]
    for p in promotions:
        v    = p.get("version_being_promoted") or {}
        fv   = p.get("_full_version") or {}
        vs   = v.get("version_string", "—")
        date = fmt_dt(p.get("created_at"))
        env  = p.get("environment", "—")
        lines += [f"  {vs}", f"  Env: {env}  Date: {date}"]
        for item in sorted(fv.get("version_manifest", []), key=lambda x: x.get("component", "")):
            lines.append(f"    {item.get('component','—'):<40} {item.get('version_string','—')}")
        lines += [thin, ""]
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# Promotion list renderer
# ---------------------------------------------------------------------------

def render_list(promotions: list[dict]) -> str:
    lines = [
        f"{'Date':<12}  {'Status':<12}  {'Env':<15}  Version",
        f"{'-'*12}  {'-'*12}  {'-'*15}  {'-'*30}",
    ]
    for p in fleet_edge_promotions(promotions):
        vs   = (p.get("version_being_promoted") or {}).get("version_string", "—")
        date = (p.get("created_at") or "")[:10]
        stat = p.get("status", "—")
        env  = p.get("environment", "—")
        lines.append(f"{date:<12}  {stat:<12}  {env:<15}  {vs}")
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Generate release notes from CI Glue promotions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # ── Release map management ───────────────────────────────────────────────
    parser.add_argument(
        "--map-release", metavar="LABEL=PREFIX",
        help="Store a release→version-prefix mapping and exit. "
             "Example: --map-release \"R.5.1=2.16\"",
    )
    parser.add_argument(
        "--list-releases", action="store_true",
        help="Show all stored release→prefix mappings and exit.",
    )
    parser.add_argument(
        "--list-branches", action="store_true",
        help="Group all fleet-edge promotions by major.minor branch and exit. "
             "Use this to identify which branch corresponds to each release.",
    )
    parser.add_argument(
        "--list-promotions", action="store_true",
        help="List every fleet-edge COMPLETE promotion and exit.",
    )

    # ── Primary release targeting ────────────────────────────────────────────
    parser.add_argument(
        "--release", metavar="LABEL",
        help="Release label, e.g. R.5.1. Looks up the version prefix from the "
             "stored map (run --map-release once to register it).",
    )
    parser.add_argument(
        "--build", metavar="VERSION | latest",
        help="Generate diff notes for a specific build, or 'latest' for the "
             "most recently promoted build in the release/prefix.",
    )
    parser.add_argument(
        "--compare-to", metavar="VERSION",
        help="Explicit baseline to diff against (overrides auto-detected previous).",
    )

    # ── Power-user filters ───────────────────────────────────────────────────
    parser.add_argument(
        "--version-prefix", metavar="PREFIX",
        help="Filter by CI Glue version prefix, e.g. 2.16 (no release map needed).",
    )
    parser.add_argument(
        "--after",  metavar="YYYY-MM-DD",
        help="Include promotions on or after this date.",
    )
    parser.add_argument(
        "--before", metavar="YYYY-MM-DD",
        help="Include promotions on or before this date.",
    )

    # ── Output ───────────────────────────────────────────────────────────────
    parser.add_argument(
        "--release-label", metavar="LABEL",
        help="Override the label shown in the report header.",
    )
    parser.add_argument(
        "--output", metavar="FILE",
        help="Write to this file. Default: stdout.",
    )
    parser.add_argument(
        "--format", choices=["text", "markdown", "json"],
        help="Output format. Default: 'markdown' if --output is set, else 'text'.",
    )
    parser.add_argument(
        "--no-manifest", action="store_true",
        help="Skip fetching full version manifests (faster, less detail).",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print each API call.",
    )

    args = parser.parse_args()
    fmt  = args.format or ("markdown" if args.output else "text")

    # ── --map-release (no API needed) ────────────────────────────────────────
    if args.map_release:
        if "=" not in args.map_release:
            sys.exit("Format must be LABEL=PREFIX, e.g. --map-release \"R.5.1=2.16\"")
        raw_label, prefix = args.map_release.split("=", 1)
        label  = normalize_label(raw_label.strip())
        prefix = prefix.strip()
        mapping = load_release_map()
        mapping[label] = prefix
        save_release_map(mapping)
        print(f"Saved: {label} → {prefix}  (in {RELEASE_MAP_FILE})")
        return

    # ── --list-releases (no API needed) ─────────────────────────────────────
    if args.list_releases:
        mapping = load_release_map()
        if not mapping:
            print(f"No release mappings stored yet.\n"
                  f"Run: --map-release \"R.5.1=2.16\"")
        else:
            print(f"{'Release':<12}  Version prefix  (stored in {RELEASE_MAP_FILE})")
            print(f"{'-'*12}  {'-'*14}")
            for label in sorted(mapping.keys()):
                print(f"{label:<12}  {mapping[label]}")
        return

    # ── Everything below needs the API ───────────────────────────────────────
    token           = load_token()
    all_promotions  = get_all_promotions(token, args.verbose)
    release_map     = load_release_map()

    # ── --list-branches ──────────────────────────────────────────────────────
    if args.list_branches:
        print(branch_summary(all_promotions, release_map))
        return

    # ── --list-promotions ────────────────────────────────────────────────────
    if args.list_promotions:
        print(render_list(all_promotions))
        return

    # ── Resolve release label → version prefix ───────────────────────────────
    version_prefix = args.version_prefix

    if args.release:
        resolved = lookup_prefix(args.release, release_map, all_promotions)
        if not resolved:
            norm = normalize_label(args.release)
            sys.exit(
                f"No version prefix found for release '{norm}'.\n"
                f"Run --list-branches to see available branches, then:\n"
                f"  --map-release \"{norm}=<prefix>\"  (e.g. --map-release \"{norm}=2.16\")"
            )
        version_prefix = resolved
        print(f"Release {normalize_label(args.release)} → version prefix {version_prefix}", flush=True)

    # ── Resolve --build latest ───────────────────────────────────────────────
    build_vs = args.build
    if build_vs and build_vs.lower() == "latest":
        if not version_prefix:
            sys.exit("--build latest requires --release or --version-prefix to scope the search.")
        latest = latest_promotion_in_prefix(all_promotions, version_prefix)
        if not latest:
            sys.exit(f"No promotions found with prefix '{version_prefix}'.")
        build_vs = (latest.get("version_being_promoted") or {}).get("version_string")
        print(f"Latest build in {version_prefix}: {build_vs}", flush=True)

    # ── Determine report label ───────────────────────────────────────────────
    if args.release_label:
        label = args.release_label
    elif args.release:
        label = normalize_label(args.release)
        if build_vs:
            label = f"{label} ({build_vs})"
    elif build_vs:
        label = build_vs
    elif version_prefix:
        label = f"fleet-edge {version_prefix}.x"
    else:
        label = f"{args.after or '…'} → {args.before or 'now'}"

    # ── DIFF MODE: --build ───────────────────────────────────────────────────
    if build_vs:
        target = find_promotion_by_version(all_promotions, build_vs)
        if not target:
            sys.exit(f"No promotion found for '{build_vs}'.\n"
                     "Run --list-promotions to see available versions.")

        if args.compare_to:
            prev = find_promotion_by_version(all_promotions, args.compare_to)
            if not prev:
                sys.exit(f"Baseline '{args.compare_to}' not found in promotions.")
        else:
            prev = find_previous_promotion(all_promotions, target)

        prev_vs = (prev.get("version_being_promoted") or {}).get("version_string") if prev else None
        print(f"Build      : {build_vs}", flush=True)
        print(f"Baseline   : {prev_vs or 'none (first promotion in branch)'}", flush=True)

        target_vid = (target.get("version_being_promoted") or {}).get("id")
        target_fv  = get_full_version(target_vid, token, args.verbose) if target_vid else {}
        new_manifest = manifest_dict(target_fv)

        if prev:
            prev_vid     = (prev.get("version_being_promoted") or {}).get("id")
            prev_fv      = get_full_version(prev_vid, token, args.verbose) if prev_vid else {}
            old_manifest = manifest_dict(prev_fv)
        else:
            old_manifest = {}

        changed, unchanged = diff_manifests(new_manifest, old_manifest)
        print(f"Changed    : {len(changed)} components", flush=True)
        print(f"Unchanged  : {len(unchanged)} components", flush=True)

        if changed and not args.no_manifest:
            print("Fetching commit/JIRA info for changed components …", flush=True)
            changed = enrich_with_change_info(changed, token, args.verbose)

        promoted_at = fmt_dt(target.get("created_at"))
        environment = target.get("environment", "—")

        if fmt == "json":
            output = json.dumps({
                "build": build_vs, "baseline": prev_vs, "label": label,
                "changed": changed, "unchanged": unchanged,
            }, indent=2, default=str)
        elif fmt == "markdown":
            output = render_diff_markdown(
                build_vs, prev_vs, promoted_at, environment,
                changed, unchanged, label,
            )
        else:
            output = render_diff_text(
                build_vs, prev_vs, promoted_at, environment,
                changed, unchanged, label,
            )

    # ── MANIFEST MODE: range / prefix ────────────────────────────────────────
    else:
        if not version_prefix and not args.after and not args.before:
            parser.error(
                "Nothing to do. Specify --release, --build, --version-prefix, "
                "--after/--before, or an info flag (--list-releases, "
                "--list-branches, --list-promotions)."
            )

        matching = filter_promotions(
            all_promotions,
            version_prefix=version_prefix,
            after=args.after,
            before=args.before,
        )
        if not matching:
            sys.exit("No promotions matched. Run --list-branches to see available versions.")

        print(f"Found {len(matching)} promotion(s). Fetching version details …", flush=True)

        if not args.no_manifest:
            enriched = []
            for i, p in enumerate(matching, 1):
                vid = (p.get("version_being_promoted") or {}).get("id")
                if vid:
                    p = dict(p)
                    p["_full_version"] = get_full_version(vid, token, args.verbose)
                enriched.append(p)
                if i % 5 == 0 or i == len(matching):
                    print(f"  {i}/{len(matching)} enriched", flush=True)
            matching = enriched

        if fmt == "json":
            output = json.dumps(matching, indent=2, default=str)
        elif fmt == "markdown":
            output = render_manifest_markdown(matching, label)
        else:
            output = render_manifest_text(matching, label)

    # ── Write output ─────────────────────────────────────────────────────────
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"\nRelease notes written to: {args.output}")
    else:
        print()
        print(output)


if __name__ == "__main__":
    main()
