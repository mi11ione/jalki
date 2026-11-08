#!/usr/bin/env python3
"""Compare a run's outputs with the reference fingerprints in expected_outputs.json and print a table.

    python verify_outputs.py --out build

Exit 0 only if every file matches. A mismatch on other library versions can be last-digit float noise, so check
requirements.txt first. Synthetic pack only: nothing here is Apetit's real emissions."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def tree_sha(root):
    """One fingerprint for a folder: the hash of its sorted (relative path, file hash) list."""
    items = sorted((str(p.relative_to(root)), sha(p)) for p in Path(root).rglob("*") if p.is_file())
    return hashlib.sha256(json.dumps(items).encode()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="build", help="the folder given to run_all.py --out")
    out = Path(ap.parse_args().out).resolve()
    exp = json.loads((HERE / "expected_outputs.json").read_text(encoding="utf-8"))
    bad = 0
    print(f"{'output':62s} {'result':10s} sha256")
    for rel, want in exp["files"].items():
        p = out / rel
        got = "" if not p.exists() else (tree_sha(p) if p.is_dir() else sha(p))
        ok = got == want
        bad += not ok
        print(f"{rel:62s} {'match' if ok else ('MISSING' if not got else 'DIFFERENT'):10s} {got[:16]}")
    print(f"\n{len(exp['files']) - bad} of {len(exp['files'])} match the reference run ({exp['environment']})")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
