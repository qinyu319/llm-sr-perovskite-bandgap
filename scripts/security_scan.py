from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BINARY_SUFFIXES = {
    ".docx",
    ".xlsx",
    ".xls",
    ".png",
    ".jpg",
    ".jpeg",
    ".pdf",
    ".zip",
    ".pyc",
}
PATTERNS = {
    "OpenAI-style key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "bearer credential": re.compile(
        r"\bAuthorization\s*[:=]\s*Bearer\s+[A-Za-z0-9._~+/-]{12,}",
        re.IGNORECASE,
    ),
    "private Windows user path": re.compile(
        r"\b[A-Z]:\\Users\\[^\\\r\n]+", re.IGNORECASE
    ),
    "private project path": re.compile(r"\bD:\\202606(?:\\|$)", re.IGNORECASE),
    "manuscript-system link": re.compile(
        r"https?://[^\s]*(?:manuscriptcentral|editorialmanager)[^\s]*",
        re.IGNORECASE,
    ),
}


def repository_files() -> list[Path]:
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [
        ROOT / item.decode("utf-8")
        for item in result.stdout.split(b"\0")
        if item
    ]


def main() -> int:
    findings: list[str] = []
    files = repository_files()

    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        if any(ord(char) > 127 for char in relative):
            findings.append(f"{relative}: non-ASCII path")
        if " " in relative:
            findings.append(f"{relative}: space in path")
        if path.suffix.lower() in BINARY_SUFFIXES or not path.is_file():
            continue
        if relative == "scripts/security_scan.py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in PATTERNS.items():
            match = pattern.search(text)
            if match:
                line = text.count("\n", 0, match.start()) + 1
                findings.append(f"{relative}:{line}: {label}")

    if findings:
        print("Publication security scan failed:")
        for finding in findings:
            print(f"  {finding}")
        return 1

    print(f"Publication security scan passed ({len(files)} files checked).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
