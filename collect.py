#!/usr/bin/env python3
"""
Collect line-of-code stats by walking each repo's commits authored by user
and fetching per-commit file stats. Bypasses the broken /stats/contributors
endpoint. Counts lines per language by file extension.
"""
from __future__ import annotations
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

USER = "zxzinn"
MAX_WORKERS = 6

EXT_TO_LANG = {
    "py": "Python", "pyi": "Python",
    "ts": "TypeScript", "tsx": "TypeScript",
    "js": "JavaScript", "jsx": "JavaScript", "mjs": "JavaScript", "cjs": "JavaScript",
    "vue": "Vue", "svelte": "Svelte",
    "rs": "Rust", "go": "Go", "java": "Java", "kt": "Kotlin",
    "cs": "C#", "cpp": "C++", "cc": "C++", "cxx": "C++", "hpp": "C++", "h": "C/C++ Header",
    "c": "C", "zig": "Zig", "swift": "Swift", "dart": "Dart",
    "rb": "Ruby", "php": "PHP", "lua": "Lua", "scala": "Scala",
    "html": "HTML", "css": "CSS", "scss": "SCSS", "sass": "Sass",
    "md": "Markdown", "mdx": "MDX",
    "yml": "YAML", "yaml": "YAML", "toml": "TOML", "json": "JSON", "xml": "XML",
    "sh": "Shell", "bash": "Shell", "zsh": "Shell", "fish": "Shell",
    "sql": "SQL", "graphql": "GraphQL", "gql": "GraphQL",
    "tf": "Terraform", "hcl": "HCL",
    "ipynb": "Jupyter Notebook", "proto": "Protobuf",
    "ex": "Elixir", "exs": "Elixir",
}
EXCLUDE_FILENAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lock", "bun.lockb",
    "uv.lock", "poetry.lock", "Pipfile.lock", "Cargo.lock", "go.sum",
    "composer.lock", "Gemfile.lock",
}
EXCLUDE_PATH_FRAGMENTS = ("node_modules/", "vendor/", "dist/", "build/", ".next/",
                          ".venv/", "venv/", "__pycache__/", "target/")


def lang_of(path: str) -> str | None:
    name = Path(path).name
    if name in EXCLUDE_FILENAMES:
        return None
    if any(frag in path for frag in EXCLUDE_PATH_FRAGMENTS):
        return None
    if name.lower() == "dockerfile" or name.lower().startswith("dockerfile."):
        return "Dockerfile"
    if "." not in name:
        return None
    ext = name.rsplit(".", 1)[1].lower()
    if ext in {"min", "map"}:
        return None
    return EXT_TO_LANG.get(ext)


def gh(path: str) -> tuple[int, str, dict]:
    r = subprocess.run(["gh", "api", path, "-i"], capture_output=True, text=True)
    out = r.stdout
    if "\n\n" in out:
        head, body = out.split("\n\n", 1)
    else:
        head, body = out, ""
    status = 0
    headers = {}
    for line in head.splitlines():
        if line.startswith("HTTP/"):
            try:
                status = int(line.split()[1])
            except (ValueError, IndexError):
                pass
        elif ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    return status, body, headers


def list_target_repos() -> list[dict]:
    query = """
    {
      viewer {
        repositories(first: 100, ownerAffiliations: OWNER, orderBy: {field: PUSHED_AT, direction: DESC}) {
          nodes { nameWithOwner isPrivate isFork }
        }
        repositoriesContributedTo(first: 100, contributionTypes: [COMMIT], includeUserRepositories: false) {
          nodes { nameWithOwner isPrivate isFork }
        }
      }
    }
    """
    r = subprocess.run(["gh", "api", "graphql", "-f", f"query={query}"], capture_output=True, text=True)
    data = json.loads(r.stdout)["data"]["viewer"]
    seen = {}
    for n in data["repositories"]["nodes"] + data["repositoriesContributedTo"]["nodes"]:
        seen[n["nameWithOwner"]] = n
    return list(seen.values())


def list_commit_shas(repo: str) -> list[str]:
    shas: list[str] = []
    page = 1
    while True:
        path = f"repos/{repo}/commits?author={USER}&per_page=100&page={page}"
        status, body, _ = gh(path)
        if status == 409:
            return []
        if status == 404:
            return []
        if status == 422:
            return []
        if status != 200:
            print(f"  ! commits list status {status} on {repo} page {page}", file=sys.stderr)
            return shas
        try:
            commits = json.loads(body)
        except json.JSONDecodeError:
            return shas
        if not commits:
            break
        shas.extend(c["sha"] for c in commits)
        if len(commits) < 100:
            break
        page += 1
        if page > 50:
            print(f"  ! capped at 5000 commits for {repo}", file=sys.stderr)
            break
    return shas


def fetch_commit_stats(repo: str, sha: str) -> dict | None:
    status, body, _ = gh(f"repos/{repo}/commits/{sha}")
    if status != 200:
        return None
    try:
        c = json.loads(body)
    except json.JSONDecodeError:
        return None
    files = c.get("files") or []
    by_lang: dict[str, dict] = defaultdict(lambda: {"add": 0, "del": 0})
    other_add = other_del = 0
    for f in files:
        lang = lang_of(f.get("filename", ""))
        a, d = f.get("additions", 0), f.get("deletions", 0)
        if lang is None:
            other_add += a
            other_del += d
        else:
            by_lang[lang]["add"] += a
            by_lang[lang]["del"] += d
    return {
        "by_lang": dict(by_lang),
        "other_add": other_add,
        "other_del": other_del,
        "total_add": c.get("stats", {}).get("additions", 0),
        "total_del": c.get("stats", {}).get("deletions", 0),
    }


def process_repo(repo_info: dict) -> dict:
    name = repo_info["nameWithOwner"]
    print(f"  listing commits for {name}", file=sys.stderr)
    shas = list_commit_shas(name)
    if not shas:
        return {"repo": name, "commits": 0, "by_lang": {}, "totals": {"add": 0, "del": 0, "other_add": 0, "other_del": 0}}
    print(f"  {name}: {len(shas)} commits", file=sys.stderr)
    by_lang: dict[str, dict] = defaultdict(lambda: {"add": 0, "del": 0})
    total_add = total_del = other_add = other_del = 0
    for i, sha in enumerate(shas):
        stats = fetch_commit_stats(name, sha)
        if stats is None:
            continue
        for lang, v in stats["by_lang"].items():
            by_lang[lang]["add"] += v["add"]
            by_lang[lang]["del"] += v["del"]
        total_add += stats["total_add"]
        total_del += stats["total_del"]
        other_add += stats["other_add"]
        other_del += stats["other_del"]
    print(f"  ✓ {name}: +{total_add} -{total_del}", file=sys.stderr)
    return {
        "repo": name,
        "private": repo_info["isPrivate"],
        "fork": repo_info["isFork"],
        "commits": len(shas),
        "by_lang": dict(by_lang),
        "totals": {"add": total_add, "del": total_del, "other_add": other_add, "other_del": other_del},
    }


def main():
    repos = list_target_repos()
    print(f"Scanning {len(repos)} repos with {MAX_WORKERS} workers", file=sys.stderr)
    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(process_repo, r): r["nameWithOwner"] for r in repos}
        done = 0
        for fut in as_completed(futures):
            done += 1
            try:
                results.append(fut.result())
            except Exception as e:
                print(f"  ! {futures[fut]} failed: {e}", file=sys.stderr)
            print(f"[{done}/{len(repos)}] {futures[fut]} done", file=sys.stderr)
    grand_lang: dict[str, dict] = defaultdict(lambda: {"add": 0, "del": 0})
    grand_add = grand_del = grand_commits = 0
    contributed = 0
    for r in results:
        if r["totals"]["add"] + r["totals"]["del"] == 0:
            continue
        contributed += 1
        grand_add += r["totals"]["add"]
        grand_del += r["totals"]["del"]
        grand_commits += r["commits"]
        for lang, v in r["by_lang"].items():
            grand_lang[lang]["add"] += v["add"]
            grand_lang[lang]["del"] += v["del"]
    out = {
        "user": USER,
        "totals": {"added": grand_add, "deleted": grand_del, "net": grand_add - grand_del,
                   "commits": grand_commits, "repos_contributed": contributed},
        "languages": {k: v for k, v in sorted(grand_lang.items(), key=lambda x: -(x[1]["add"]+x[1]["del"]))},
        "per_repo": sorted([r for r in results if r["totals"]["add"]+r["totals"]["del"] > 0],
                            key=lambda r: -(r["totals"]["add"]+r["totals"]["del"])),
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
