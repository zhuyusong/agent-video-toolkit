"""Audit the tracked publication tree; never print matching secret text."""
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ROOT_FILES = {"pyproject.toml", "MANIFEST.in", "README.md", "README.en.md", "LICENSE", "THIRD_PARTY.md", "CONTRIBUTING.md", "SECURITY.md", "AGENTS.md", ".gitignore", ".gitattributes"}
ALLOWED_DIRS = {"src", "tests", "docs", "scripts", ".github", "examples"}
ALLOWED_SUFFIXES = {".py", ".js", ".md", ".toml", ".json", ".yml", ".yaml"}
PATTERNS = [
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("github-token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("service-key", re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16})\b")),
    ("credential-url", re.compile(r"https?://[^\s/@:]+:[^\s/@]+@")),
    ("credential-assignment", re.compile(r'''(?i)(?:api[_-]?key|password|authorization|cookie|access[_-]?token)\s*[:=]\s*["'][^"'\n]{16,}["']''')),
]


def main():
    paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode("utf-8").split("\0")
    paths = [p for p in paths if p]
    if not paths:
        raise SystemExit("No tracked files; stage the intended publication tree first")
    findings = []
    size = 0
    for name in paths:
        path = ROOT / name
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            findings.append((name, "link")); continue
        if path.parts[len(ROOT.parts)] not in ALLOWED_DIRS and name not in ALLOWED_ROOT_FILES:
            findings.append((name, "unexpected-path"))
        if name not in ALLOWED_ROOT_FILES and path.suffix not in ALLOWED_SUFFIXES:
            findings.append((name, "unexpected-resource"))
        data = path.read_bytes()
        size += len(data)
        if len(data) > 256000:
            findings.append((name, "large-file"))
        try:
            body = data.decode("utf-8")
        except UnicodeDecodeError:
            findings.append((name, "binary")); continue
        if "\x00" in body:
            findings.append((name, "binary"))
        for label, pattern in PATTERNS:
            if pattern.search(body):
                findings.append((name, label))
        if re.search(r"C:\\(?:项目|Users)\\", body):
            findings.append((name, "local-user-path"))
    if findings:
        for name, label in findings:
            print(f"{name}: {label}")
        raise SystemExit(1)
    print(f"Publication scan passed: {len(paths)} text files, {size} bytes; no matching secrets, binaries or local user paths.")
    print("Pattern scanning is supplementary; maintainers must also review every staged file.")


if __name__ == "__main__":
    main()
