from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "checksums.sha256"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    failures = []
    checked = 0
    for line_number, raw in enumerate(
        MANIFEST.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            expected, relative = line.split(None, 1)
        except ValueError:
            failures.append(f"line {line_number}: invalid manifest entry")
            continue
        path = ROOT / relative.strip()
        if not path.is_file():
            failures.append(f"missing: {relative}")
            continue
        observed = sha256(path)
        checked += 1
        if observed.lower() != expected.lower():
            failures.append(
                f"mismatch: {relative}\n  expected {expected}\n  observed {observed}"
            )
    if failures:
        raise SystemExit("Checksum verification failed:\n" + "\n".join(failures))
    print(f"Verified {checked} files.")


if __name__ == "__main__":
    main()
