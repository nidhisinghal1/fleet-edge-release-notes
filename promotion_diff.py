#!/usr/bin/env python3
"""
promotion_diff.py — Track changes between CI Glue promotions by stage

Shows exactly what changed between two fleet-edge promotions, labelled by
pipeline stage (Dev → QA or QA → Prod).

Usage examples
--------------

  # What changed in the latest Dev → QA promotion (vs previous QA)?
  python promotion_diff.py --release R.5.1 --stage qa

  # What changed in the latest QA → Prod promotion (vs previous Prod)?
  python promotion_diff.py --release R.5.1 --stage prod

  # What's in QA right now that has NOT yet gone to Prod?
  python promotion_diff.py --release R.5.1 --stage pending

  # Generate notes for ALL stages at once (three output files):
  python promotion_diff.py --release R.5.1 --all-stages --output R5.1

  # Explicit build numbers:
  python promotion_diff.py --from 2.16.203.8402-master --to 2.16.443.8525-master

  # Save to file:
  python promotion_diff.py --release R.5.1 --stage qa --output R5.1_dev_to_qa.md

  # See all promotions for a release:
  python promotion_diff.py --release R.5.1 --list

  # Discovery helpers (no --release needed):
  python promotion_diff.py --list-all
  python promotion_diff.py --list-releases

Stage meanings
--------------
  qa      : Dev → QA    (compare latest QA promotion to previous QA promotion)
  prod    : QA → Prod   (compare latest Prod promotion to previous Prod promotion)
  pending : QA → Prod gap (compare latest QA build to latest Prod build — not
            yet promoted, shows what would go out if promoted to Prod now)

Token
-----
  ~/.config/ci-glue/token  or  CI_GLUE_TOKEN env var

Release map
-----------
  releases.json next to this script (committed to repo)
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
# Config
# ---------------------------------------------------------------------------

TOKEN_FILE   = Path.home() / ".config" / "ci-glue" / "token"
BASE_URL     = "https://ci-glue.fleetedgeportal.com/api"
PAGE_SIZE    = 100
_SCRIPT_DIR  = Path(__file__).resolve().parent
_LOCAL_MAP   = _SCRIPT_DIR / "releases.json"
_USER_MAP    = Path.home() / ".config" / "ci-glue" / "releases.json"
RELEASE_MAP_FILE = _LOCAL_MAP if _LOCAL_MAP.exists() else _USER_MAP

STAGE_META = {
    "qa":      {"label": "Dev → QA",      "env": "qa",   "prev_env": "qa"},
    "prod":    {"label": "QA → Prod",     "env": "prod", "prev_env": "prod"},
    "pending": {"label": "QA → Prod (pending)", "env": "qa", "prev_env": "prod"},
}

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def load_token() -> str:
    t = os.environ.get("CI_GLUE_TOKEN")
    if t:
        return t.strip()
    if not TOKEN_FILE.exists():
        sys.exit(f"Token not found at {TOKEN_FILE}. Set CI_GLUE_TOKEN or run CI Glue login.")
    return TOKEN_FILE.read_text().strip()


def _get(url: str, token: str, verbose: bool) -> dict:
    if verbose:
        print(f"  GET {url}", flush=True)
    req = urllib.request.Request(url, headers={"Authorization": f"Token {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {url}\n{e.read().decode(errors='replace')}")


def fetch_all(endpoint: str, token: str, verbose: bool) -> list[dict]:
    items, url = [], f"{BASE_URL}/{endpoint}?limit={PAGE_SIZE}"
    while url:
        page = _get(url, token, verbose)
        items.extend(page.get("results", []))
        url = page.get("next")
    return items


def fetch_version(vid: str, token: str, verbose: bool) -> dict:
    try:
        return _get(f"{BASE_URL}/versions/{vid}/", token, verbose)
    except SystemExit:
        return {}

# ---------------------------------------------------------------------------
# Release map
# ---------------------------------------------------------------------------

def load_release_map() -> dict[str, str]:
    return json.loads(RELEASE_MAP_FILE.read_text()) if RELEASE_MAP_FILE.exists() else {}


def save_release_map(mapping: dict[str, str]) -> None:
    target = _LOCAL_MAP if _LOCAL_MAP.exists() else _USER_MAP
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(mapping, indent=2, sort_keys=True))


def normalize_label(label: str) -> str:
    label = label.strip().upper()
    body  = label.lstrip("R").lstrip(". ")
    parts = re.split(r"[.\s_-]+", body)
    return "R." + ".".join(p for p in parts if p)


def resolve_prefix(label: str, release_map: dict, promotions: list) -> str | None:
    norm = normalize_label(label)
    if norm in release_map:
        return release_map[norm]
    for k, v in release_map.items():
        if k.upper() == norm.upper():
            return v
    digits = re.sub(r"[^0-9]", "", norm)
    if digits:
        for p in fe_promotions(promotions):
            vs = (p.get("version_being_promoted") or {}).get("version_string", "")
            if f"R{digits}" in vs.upper().replace("-", "").replace(".", ""):
                parts = vs.split(".")
                if len(parts) >= 2:
                    return f"{parts[0]}.{parts[1]}"
    return None

# ---------------------------------------------------------------------------
# Promotions
# ---------------------------------------------------------------------------

def fe_promotions(promotions: list[dict]) -> list[dict]:
    return [
        p for p in promotions
        if p.get("promotion_type") == "COMPLETE"
        and (p.get("version_being_promoted") or {}).get("component") == "fleet-edge"
    ]


def promotions_for(all_p: list[dict], prefix: str,
                   env: str | None = None) -> list[dict]:
    out = []
    for p in fe_promotions(all_p):
        vs  = (p.get("version_being_promoted") or {}).get("version_string", "")
        penv = (p.get("environment") or "").lower()
        if not vs.startswith(prefix):
            continue
        if env and penv != env.lower():
            continue
        out.append(p)
    return out


def latest_in(all_p: list[dict], prefix: str, env: str) -> dict | None:
    matches = promotions_for(all_p, prefix, env)
    return max(matches, key=lambda p: p.get("created_at") or "") if matches else None


def previous_in(all_p: list[dict], target: dict, env: str) -> dict | None:
    """Most recent promotion before target in the same prefix and env."""
    fe    = fe_promotions(all_p)
    t_vs  = (target.get("version_being_promoted") or {}).get("version_string", "")
    t_env = (target.get("environment") or "").lower()
    prefix = ".".join(t_vs.split(".")[:2]) if "." in t_vs else t_vs

    t_idx = next(
        (i for i, p in enumerate(fe)
         if (p.get("version_being_promoted") or {}).get("version_string") == t_vs
         and (p.get("environment") or "").lower() == t_env),
        None,
    )
    if t_idx is None:
        return None

    for p in reversed(fe[:t_idx]):
        vs   = (p.get("version_being_promoted") or {}).get("version_string", "")
        penv = (p.get("environment") or "").lower()
        if vs.startswith(prefix) and penv == env.lower():
            return p
    return None


def find_by_vs(all_p: list[dict], vs: str, env: str | None = None) -> dict | None:
    for p in fe_promotions(all_p):
        if (p.get("version_being_promoted") or {}).get("version_string") != vs:
            continue
        if env and (p.get("environment") or "").lower() != env.lower():
            continue
        return p
    return None

# ---------------------------------------------------------------------------
# Manifest diff
# ---------------------------------------------------------------------------

def manifest_dict(version: dict) -> dict[str, dict]:
    return {i["component"]: i for i in version.get("version_manifest", [])}


def diff_manifests(new_m: dict, old_m: dict) -> tuple[list[dict], list[str]]:
    changed, unchanged = [], []
    for comp, item in sorted(new_m.items()):
        old    = old_m.get(comp)
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


def enrich(changed: list[dict], token: str, verbose: bool) -> list[dict]:
    total, out = len(changed), []
    for i, item in enumerate(changed, 1):
        vid = item.get("version_id")
        if vid:
            v   = fetch_version(vid, token, verbose)
            ch  = v.get("change") or {}
            item = {
                **item,
                "sha":     (ch.get("commit_id") or "")[:8],
                "branch":  ch.get("branch") or "",
                "author":  ch.get("created_by") or "",
                "message": (ch.get("change_message") or "").split("\n")[0].strip()[:120],
                "issues":  ch.get("issues") or [],
                "repo":    ch.get("repository") or "",
            }
        else:
            item = {**item, "sha": "", "branch": "", "author": "",
                    "message": "", "issues": [], "repo": ""}
        out.append(item)
        if i % 10 == 0 or i == total:
            print(f"  enriched {i}/{total} components", flush=True)
    return out


def group_by_jira(changed: list[dict]) -> dict[str, list[dict]]:
    g: dict[str, list[dict]] = defaultdict(list)
    for item in changed:
        issues = item.get("issues") or []
        g[", ".join(sorted(issues)) if issues else ""].append(item)
    return dict(g)

# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def fmt_dt(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return iso


def render_markdown(stage_label: str, release_label: str,
                    new_vs: str, old_vs: str | None,
                    new_env: str, new_promoted_at: str,
                    changed: list[dict], unchanged: list[str]) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    baseline_note = old_vs or "N/A — first promotion in this environment"
    lines = [
        f"# {release_label} — {stage_label}",
        "",
        f"| | |",
        f"|---|---|",
        f"| **Stage** | {stage_label} |",
        f"| **Build** | `{new_vs}` |",
        f"| **Environment** | `{new_env}` |",
        f"| **Promoted at** | {new_promoted_at} |",
        f"| **Baseline** | `{baseline_note}` |",
        f"| **Changed components** | {len(changed)} |",
        f"| **Unchanged components** | {len(unchanged)} |",
        f"| **Generated** | {generated} |",
        "",
        "---",
        "",
    ]

    # JIRA-grouped section
    lines += ["## Changes by JIRA Ticket", ""]
    groups   = group_by_jira(changed)
    ticketed = {k: v for k, v in groups.items() if k}
    no_ticket = groups.get("", [])

    if not changed:
        lines += ["> No changes — this build is identical to the baseline.", ""]
    else:
        for key in sorted(ticketed):
            items   = ticketed[key]
            summary = next((i["message"] for i in items if i.get("message")), "—")
            comps   = ", ".join(f"`{i['component']}`" for i in items)
            authors = ", ".join(sorted({i["author"] for i in items if i.get("author")}))
            lines += [
                f"### {key}",
                "",
                f"**{summary}**",
                f"- Components: {comps}",
            ]
            if authors:
                lines.append(f"- Author(s): {authors}")
            lines.append("")

        if no_ticket:
            comps = ", ".join(f"`{i['component']}`" for i in no_ticket)
            lines += ["### (No JIRA ticket)", "", f"Components: {comps}", ""]

    lines += ["---", ""]

    # Component table
    lines += [
        "## Component Version Changes",
        "",
        "| Component | From | To | JIRA | Commit | Author | Change |",
        "|-----------|------|----|------|--------|--------|--------|",
    ]
    for item in changed:
        issues = ", ".join(item.get("issues") or []) or "—"
        lines.append(
            f"| `{item['component']}` "
            f"| `{item['from_vs']}` "
            f"| **`{item['to_vs']}`** "
            f"| {issues} "
            f"| `{item.get('sha') or '—'}` "
            f"| {item.get('author') or '—'} "
            f"| {item.get('message') or '—'} |"
        )

    if unchanged:
        lines += [
            "",
            "---",
            "",
            "## Unchanged Components",
            "",
            ", ".join(f"`{c}`" for c in sorted(unchanged)),
            "",
        ]

    return "\n".join(lines)


def render_text(stage_label: str, release_label: str,
                new_vs: str, old_vs: str | None,
                new_env: str, new_promoted_at: str,
                changed: list[dict], unchanged: list[str]) -> str:
    sep  = "=" * 72
    thin = "-" * 72
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    baseline_note = old_vs or "N/A — first promotion in this environment"
    lines = [
        sep,
        f"  {release_label} — {stage_label}",
        sep,
        f"  Stage       : {stage_label}",
        f"  Build       : {new_vs}",
        f"  Environment : {new_env}",
        f"  Promoted at : {new_promoted_at}",
        f"  Baseline    : {baseline_note}",
        f"  Changed     : {len(changed)} components",
        f"  Unchanged   : {len(unchanged)} components",
        f"  Generated   : {generated}",
        sep,
        "",
    ]

    if not changed:
        lines += ["  No changes — this build is identical to the baseline.", ""]
    else:
        groups   = group_by_jira(changed)
        ticketed = {k: v for k, v in groups.items() if k}
        no_ticket = groups.get("", [])

        lines += ["  CHANGES BY JIRA TICKET", thin, ""]
        for key in sorted(ticketed):
            items   = ticketed[key]
            summary = next((i["message"] for i in items if i.get("message")), "—")
            comps   = ", ".join(i["component"] for i in items)
            lines  += [f"  [{key}]", f"    {summary}", f"    Components: {comps}", ""]

        if no_ticket:
            comps = ", ".join(i["component"] for i in no_ticket)
            lines += ["  [No JIRA ticket]", f"    Components: {comps}", ""]

        lines += [thin, "", "  COMPONENT VERSION CHANGES", thin]
        lines.append(f"  {'Component':<35} {'From':<12} {'To':<12} {'JIRA':<25} Author")
        lines.append("  " + "-" * 70)
        for item in changed:
            issues = ", ".join(item.get("issues") or []) or "—"
            lines.append(
                f"  {item['component']:<35} {item['from_vs']:<12} "
                f"{item['to_vs']:<12} {issues:<25} {item.get('author') or '—'}"
            )
            if item.get("message"):
                lines.append(f"    → {item['message']}")

    if unchanged:
        lines += ["", thin, "", "  UNCHANGED COMPONENTS", thin]
        for i in range(0, len(unchanged), 4):
            lines.append("  " + "  ".join(sorted(unchanged)[i:i+4]))

    return "\n".join(lines)

# ---------------------------------------------------------------------------
# Core diff runner
# ---------------------------------------------------------------------------

def run_diff(all_p: list[dict], token: str, verbose: bool,
             new_vs: str, old_vs: str | None,
             stage: str, no_enrich: bool) -> dict:
    """Fetch manifests, diff, enrich. Returns data dict."""
    meta = STAGE_META[stage]
    print(f"  [{meta['label']}]  {new_vs}  ←  {old_vs or 'none'}", flush=True)

    new_promo = find_by_vs(all_p, new_vs)
    new_vid   = (new_promo.get("version_being_promoted") or {}).get("id") if new_promo else None
    new_fv    = fetch_version(new_vid, token, verbose) if new_vid else {}
    new_m     = manifest_dict(new_fv)
    new_env   = (new_promo.get("environment") or "—") if new_promo else meta["env"]
    new_at    = fmt_dt((new_promo or {}).get("created_at"))

    old_m: dict = {}
    if old_vs:
        old_promo = find_by_vs(all_p, old_vs)
        old_vid   = (old_promo.get("version_being_promoted") or {}).get("id") if old_promo else None
        old_fv    = fetch_version(old_vid, token, verbose) if old_vid else {}
        old_m     = manifest_dict(old_fv)

    changed, unchanged = diff_manifests(new_m, old_m)
    print(f"  Changed: {len(changed)}  Unchanged: {len(unchanged)}", flush=True)

    if changed and not no_enrich:
        changed = enrich(changed, token, verbose)

    return {
        "stage":         stage,
        "stage_label":   meta["label"],
        "new_vs":        new_vs,
        "old_vs":        old_vs,
        "environment":   new_env,
        "promoted_at":   new_at,
        "changed":       changed,
        "unchanged":     unchanged,
    }


def write_output(data: dict, release_label: str,
                 fmt: str, output_path: Path | None) -> None:
    if fmt == "json":
        content = json.dumps(data, indent=2, default=str)
    elif fmt == "markdown":
        content = render_markdown(
            data["stage_label"], release_label,
            data["new_vs"], data["old_vs"],
            data["environment"], data["promoted_at"],
            data["changed"], data["unchanged"],
        )
    else:
        content = render_text(
            data["stage_label"], release_label,
            data["new_vs"], data["old_vs"],
            data["environment"], data["promoted_at"],
            data["changed"], data["unchanged"],
        )

    if output_path:
        output_path.write_text(content, encoding="utf-8")
        print(f"  Written: {output_path}")
    else:
        print()
        print(content)

# ---------------------------------------------------------------------------
# List helpers
# ---------------------------------------------------------------------------

def render_promotion_list(all_p: list[dict], prefix: str | None,
                          release_map: dict) -> str:
    prefix_to_label = {v: k for k, v in release_map.items()}
    lines = [
        f"{'Date':<12}  {'Env':<8}  {'Stage':<20}  {'Version'}",
        f"{'-'*12}  {'-'*8}  {'-'*20}  {'-'*35}",
    ]
    for p in fe_promotions(all_p):
        vs  = (p.get("version_being_promoted") or {}).get("version_string", "—")
        env = (p.get("environment") or "—").lower()
        dt  = (p.get("created_at") or "")[:10]
        if prefix and not vs.startswith(prefix):
            continue
        pfx   = ".".join(vs.split(".")[:2]) if "." in vs else vs
        label = prefix_to_label.get(pfx, "")
        stage = "Dev → QA" if env == "qa" else "QA → Prod" if env == "prod" else env
        lbl_str = f"[{label}] " if label else ""
        lines.append(f"{dt:<12}  {env:<8}  {lbl_str}{stage:<20}  {vs}")
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Track changes between Dev→QA and QA→Prod promotions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Targeting
    g = parser.add_argument_group("Targeting")
    g.add_argument("--release", metavar="LABEL",
        help="Release label (e.g. R.5.1). Looks up prefix from releases.json.")
    g.add_argument("--stage", choices=["qa", "prod", "pending"],
        help="qa=Dev→QA, prod=QA→Prod, pending=what's in QA but not yet in Prod.")
    g.add_argument("--all-stages", action="store_true",
        help="Generate notes for all stages (qa, prod, pending). "
             "With --output, writes three files.")
    g.add_argument("--from", dest="from_vs", metavar="VERSION",
        help="Explicit baseline version string.")
    g.add_argument("--to", dest="to_vs", metavar="VERSION",
        help="Explicit target version string.")
    g.add_argument("--version-prefix", metavar="PREFIX",
        help="CI Glue version prefix (e.g. 2.16). Bypasses release map.")

    # Listing
    gl = parser.add_argument_group("Listing")
    gl.add_argument("--list", action="store_true",
        help="List promotions for the selected release.")
    gl.add_argument("--list-all", action="store_true",
        help="List all fleet-edge promotions.")
    gl.add_argument("--list-releases", action="store_true",
        help="Show stored release→prefix mappings.")
    gl.add_argument("--map-release", metavar="LABEL=PREFIX",
        help="Store a new release mapping (e.g. \"R.6.1=2.17\") and exit.")

    # Output
    go = parser.add_argument_group("Output")
    go.add_argument("--output", metavar="FILE_OR_BASE",
        help="File path. With --all-stages, treated as base name "
             "(e.g. R5.1 → R5.1_dev_to_qa.md, R5.1_qa_to_prod.md, R5.1_pending.md).")
    go.add_argument("--format", choices=["text", "markdown", "json"],
        help="Format. Default: markdown if --output set, else text.")
    go.add_argument("--no-enrich", action="store_true",
        help="Skip per-component API calls for commit/JIRA info (much faster).")
    go.add_argument("--verbose", action="store_true",
        help="Print each API URL.")

    args = parser.parse_args()
    fmt  = args.format or ("markdown" if args.output else "text")

    # ── Map management (no API) ───────────────────────────────────────────────
    if args.map_release:
        if "=" not in args.map_release:
            sys.exit('Format: --map-release "R.5.1=2.16"')
        raw_label, prefix = args.map_release.split("=", 1)
        label   = normalize_label(raw_label.strip())
        mapping = load_release_map()
        mapping[label] = prefix.strip()
        save_release_map(mapping)
        print(f"Saved: {label} → {prefix.strip()}  ({RELEASE_MAP_FILE})")
        return

    if args.list_releases:
        mapping = load_release_map()
        if not mapping:
            print("No mappings yet. Run: --map-release \"R.5.1=2.16\"")
        else:
            print(f"{'Release':<12}  Prefix  (from {RELEASE_MAP_FILE})")
            print(f"{'-'*12}  {'-'*8}")
            for k in sorted(mapping):
                print(f"{k:<12}  {mapping[k]}")
        return

    # ── Load API data ─────────────────────────────────────────────────────────
    token       = load_token()
    release_map = load_release_map()

    print("Fetching promotions …", flush=True)
    all_p = fetch_all("promotions", token, args.verbose)

    # ── Resolve release label → prefix ────────────────────────────────────────
    prefix = args.version_prefix
    if args.release:
        prefix = resolve_prefix(args.release, release_map, all_p)
        if not prefix:
            norm = normalize_label(args.release)
            sys.exit(
                f"No prefix for '{norm}'. Run --list-all then:\n"
                f"  --map-release \"{norm}=<prefix>\""
            )
        print(f"Release {normalize_label(args.release)} → prefix {prefix}", flush=True)

    release_label = (
        args.release_label if hasattr(args, "release_label") and args.release_label
        else normalize_label(args.release) if args.release
        else prefix or "fleet-edge"
    )
    # release_label attribute may not exist from older arg groups
    if not hasattr(args, "release_label"):
        release_label = normalize_label(args.release) if args.release else prefix or "fleet-edge"

    # ── List modes ────────────────────────────────────────────────────────────
    if args.list_all or args.list:
        print(render_promotion_list(all_p, prefix, release_map))
        return

    # ── EXPLICIT --from / --to mode ───────────────────────────────────────────
    if args.from_vs or args.to_vs:
        if not args.to_vs:
            sys.exit("--to VERSION is required with --from.")
        stage = args.stage or "qa"
        data  = run_diff(all_p, token, args.verbose,
                         args.to_vs, args.from_vs, stage, args.no_enrich)
        out = Path(args.output) if args.output else None
        write_output(data, release_label, fmt, out)
        return

    # ── Release-based modes ───────────────────────────────────────────────────
    if not prefix:
        parser.error("Specify --release, --version-prefix, or --from/--to.")

    if args.all_stages:
        base = Path(args.output) if args.output else None
        suffix_map = {
            "qa":      "_dev_to_qa",
            "prod":    "_qa_to_prod",
            "pending": "_pending",
        }

        for stage in ("qa", "prod", "pending"):
            meta = STAGE_META[stage]
            print(f"\n--- {meta['label']} ---", flush=True)

            new_p = latest_in(all_p, prefix, meta["env"])
            if not new_p:
                print(f"  No {meta['env']} promotions found — skipping.", flush=True)
                continue
            new_vs = (new_p.get("version_being_promoted") or {}).get("version_string")

            if stage == "pending":
                old_p  = latest_in(all_p, prefix, "prod")
                old_vs = (old_p.get("version_being_promoted") or {}).get("version_string") if old_p else None
            else:
                old_p  = previous_in(all_p, new_p, meta["prev_env"])
                old_vs = (old_p.get("version_being_promoted") or {}).get("version_string") if old_p else None

            data = run_diff(all_p, token, args.verbose,
                            new_vs, old_vs, stage, args.no_enrich)

            if base:
                suffix = suffix_map[stage]
                ext    = base.suffix or ".md"
                stem   = base.stem if base.suffix else str(base)
                out    = base.parent / (stem + suffix + ext)
            else:
                out = None

            write_output(data, release_label, fmt, out)
        return

    if not args.stage:
        parser.error("Specify --stage qa|prod|pending, or --all-stages.")

    meta   = STAGE_META[args.stage]
    new_p  = latest_in(all_p, prefix, meta["env"])
    if not new_p:
        sys.exit(f"No '{meta['env']}' promotions found for prefix '{prefix}'.")
    new_vs = (new_p.get("version_being_promoted") or {}).get("version_string")

    if args.stage == "pending":
        old_p  = latest_in(all_p, prefix, "prod")
        old_vs = (old_p.get("version_being_promoted") or {}).get("version_string") if old_p else None
    else:
        old_p  = previous_in(all_p, new_p, meta["prev_env"])
        old_vs = (old_p.get("version_being_promoted") or {}).get("version_string") if old_p else None

    data = run_diff(all_p, token, args.verbose,
                    new_vs, old_vs, args.stage, args.no_enrich)
    out  = Path(args.output) if args.output else None
    write_output(data, release_label, fmt, out)


if __name__ == "__main__":
    main()
