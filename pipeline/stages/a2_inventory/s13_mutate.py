"""Can the verifier fail? Corrupt a copy of the trail in one way at a time and require s12_verify.py to reject it.
The copy lives in a scratch folder under stages/a2_inventory and is deleted afterwards. Synthetic pack."""
from ccn_paths import PACKAGE, stage_dir
import csv, os, shutil, subprocess, sys
from pathlib import Path

CODE = Path(__file__).resolve().parent
HERE = stage_dir("a2_inventory")
A = HERE / "audit"
M = HERE / "_mut"


def rd(n):
    with open(M / n, newline="", encoding="utf-8") as f:
        r = list(csv.DictReader(f))
    return r, list(r[0].keys())


def wr(n, rows, cols):
    with open(M / n, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def first(rows, pred):
    return next(r for r in rows if pred(r))


def m_tonnes():
    r, c = rd("edges.csv"); e = first(r, lambda x: x["role"] == "activity"); e["tco2e"] = str(float(e["tco2e"]) + 1); wr("edges.csv", r, c)
def m_factor():
    r, c = rd("factors.csv"); f = first(r, lambda x: x["factor_id"].startswith("EF-TKM")); f["value"] = str(float(f["value"]) * 1.1); wr("factors.csv", r, c)
def m_row():
    r, c = rd("edges.csv"); e = first(r, lambda x: "erp_purchase" in x["source_file"] and x["role"] == "activity"); e["source_row"] = str(int(e["source_row"]) + 1); wr("edges.csv", r, c)
def m_raw():
    r, c = rd("edges.csv"); e = first(r, lambda x: "waste_transfer" in x["source_file"]); e["raw_value"] = str(float(e["raw_value"]) * 10 + 1); wr("edges.csv", r, c)
def m_line():
    r, c = rd("lines.csv"); l = first(r, lambda x: x["scope"] == "scope1"); l["tco2e"] = str(float(l["tco2e"]) + 5); wr("lines.csv", r, c)
def m_drop_edge():
    r, c = rd("edges.csv"); i = next(n for n, x in enumerate(r) if x["role"] == "activity" and float(x["tco2e"]) > 1); del r[i]; wr("edges.csv", r, c)
def m_orphan():
    r, c = rd("corrections.csv"); del r[0]; wr("corrections.csv", r, c)
def m_approve():
    r, c = rd("corrections.csv"); r[0]["approval"] = "approved"; wr("corrections.csv", r, c)
def m_impute():
    r, c = rd("edges.csv"); e = first(r, lambda x: not x["source_row"] and x["role"] == "activity"); e["correction_ids"] = ""; wr("edges.csv", r, c)


caught = 0
cases = [m_tonnes, m_factor, m_row, m_raw, m_line, m_drop_edge, m_orphan, m_approve, m_impute]
for fn in cases:
    if M.exists():
        shutil.rmtree(M)
    shutil.copytree(A, M)
    fn()
    p = subprocess.run([sys.executable, str(CODE / "s12_verify.py")], env=dict(os.environ, AUDIT_DIR=str(M)), capture_output=True, text=True)
    fails = [l[5:70] for l in p.stdout.splitlines() if l.startswith("FAIL")]
    ok = p.returncode != 0
    caught += ok
    print(f"{fn.__name__:12s} {'caught' if ok else 'MISSED'} {fails[:2] if fails else p.stderr[-120:]}")
shutil.rmtree(M)
print(f"mutations caught {caught} of {len(cases)}")
