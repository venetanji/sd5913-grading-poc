from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import PurePosixPath
from typing import Any

MAX_FILES = 18
MAX_FILE_CHARS = 10_000
MAX_TOTAL_CHARS = 38_000
TEXT_SUFFIXES = {".md", ".py", ".toml", ".yml", ".yaml", ".txt", ".json", ".csv", ".html", ".js", ".css", ".svg"}
SKIP_PARTS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".cache"}


def run_git(args: list[str], *, cwd: str | None = None, timeout: int = 90) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=timeout, check=False,
    )
    if result.returncode:
        # Do not relay remote stderr: Git may include identifying URLs or credentials.
        raise RuntimeError(f"git command failed (exit {result.returncode}): {args[0]}")
    return result.stdout


def repo_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]


def selected_paths(paths: list[str], assignment: int) -> list[str]:
    eligible = []
    for path in paths:
        parts = PurePosixPath(path).parts
        suffix = PurePosixPath(path).suffix.lower()
        if any(part.lower() in SKIP_PARTS for part in parts) or suffix not in TEXT_SUFFIXES:
            continue
        name = PurePosixPath(path).name.lower()
        if name.startswith(("readme", "process")):
            priority = 0
        elif suffix == ".py":
            priority = 1
        elif name in {"pyproject.toml", "requirements.txt", "package.json"}:
            priority = 2
        else:
            priority = 3
        eligible.append((priority, len(parts), path.lower(), path))
    eligible.sort()
    # The evidence pack favors the assignment's reflection/process, code and config.
    primary = [p for _, _, _, p in eligible if PurePosixPath(p).name.lower().startswith(("readme", "process"))]
    rest = [p for p in (row[3] for row in eligible) if p not in primary]
    return (primary + rest)[:MAX_FILES]


def collect_evidence(repo_url: str, assignment: int, scratch: str) -> dict[str, Any]:
    rid = repo_id(repo_url)
    run_git(["clone", "--quiet", "--depth=1", "--filter=blob:none", "--no-checkout", repo_url, scratch], timeout=180)
    tree = run_git(["ls-tree", "-r", "--name-only", "HEAD"], cwd=scratch).splitlines()
    paths = selected_paths(tree, assignment)
    excerpts = []
    used = 0
    for path in paths:
        try:
            text = run_git(["show", f"HEAD:{path}"], cwd=scratch, timeout=30)
        except RuntimeError:
            continue
        text = text[:MAX_FILE_CHARS]
        room = MAX_TOTAL_CHARS - used
        if room <= 0:
            break
        text = text[:room]
        used += len(text)
        excerpts.append({"path": path, "text": text})
    log = run_git(["log", "--format=%aI", "-n", "30", "HEAD"], cwd=scratch).splitlines()
    readme = next((x["text"] for x in excerpts if PurePosixPath(x["path"]).name.lower().startswith("readme")), "")
    process = next((x["text"] for x in excerpts if PurePosixPath(x["path"]).name.lower() == "process.md"), "")
    code_files = [x for x in excerpts if PurePosixPath(x["path"]).suffix.lower() in {".py", ".js", ".html"}]
    data_paths = [p for p in tree if p.lower().startswith("data/")]
    output_paths = [p for p in tree if p.lower().startswith(("out/", "output/", "outputs/"))]
    commit_days = sorted({date[:10] for date in log})
    checks: list[dict[str, Any]] = []
    if assignment == 1:
        word_count = len(re.findall(r"\b[\w’'-]+\b", re.sub(r"```.*?```", " ", readme, flags=re.S)))
        checks.extend([
            {"check": "README present", "result": bool(readme)},
            {"check": "README 500-1000 words (rough markdown count)", "result": 500 <= word_count <= 1000, "observed": word_count},
            {"check": "PROCESS.md present and non-empty", "result": bool(process.strip())},
            {"check": "commit history spans multiple days", "result": len(commit_days) > 1, "observed_days": len(commit_days)},
        ])
    else:
        checks.extend([
            {"check": "README present", "result": bool(readme)},
            {"check": "README at least 150 words (rough markdown count)", "result": len(readme.split()) >= 150, "observed": len(readme.split())},
            {"check": "PROCESS.md present and non-empty", "result": bool(process.strip())},
            {"check": "Python source present", "result": bool(code_files)},
            {"check": "data files present", "result": bool(data_paths), "observed": len(data_paths)},
            {"check": "output assets present", "result": bool(output_paths), "observed": len(output_paths)},
            {"check": "commit history spans multiple days", "result": len(commit_days) > 1, "observed_days": len(commit_days)},
        ])
    # File lists are metadata only; data and binary assets are not fetched into the prompt.
    return {
        "submission_id": rid,
        "assignment": assignment,
        "evidence_policy": "shallow partial clone; selected text blobs only; bounded excerpts; URL omitted; submission ID is a stable plain hash, not anonymization",
        "inventory": {"tracked_path_count": len(tree), "data_paths": data_paths[:80], "output_paths": output_paths[:40]},
        "preflight": checks,
        "history": {"sampled_commit_count": len(log), "distinct_commit_days": len(commit_days)},
        "files": excerpts,
    }


def read_urls(path: str) -> list[str]:
    urls = []
    with open(path, encoding="utf-8") as f:
        for line_no, raw in enumerate(f, 1):
            value = raw.strip()
            if not value or value.startswith("#"):
                continue
            component = r"(?:[A-Za-z0-9_.-]|%[0-9A-Fa-f]{2})+"
            if not re.fullmatch(rf"https://github\.com/{component}/{component}/?", value):
                raise ValueError(f"invalid GitHub repository URL on line {line_no}")
            urls.append(value.rstrip("/"))
    return urls


def jsonl_write(path: str, records: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
