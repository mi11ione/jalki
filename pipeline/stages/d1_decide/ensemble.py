"""Pre-registered A / B / ensemble decision (see PREREG.md), all scoring through the official ccn_tools scorer.

Prints every number and writes D1_catchment_priority_submission.csv (whichever candidate the rule ships) and
ensemble.json. Reads only submissions, the catchment table and the public dev key.
"""
from ccn_paths import PACKAGE, stage_dir
import itertools
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = stage_dir("d1_decide")
A_DIR = stage_dir("d1_model_a")
B_DIR = stage_dir("d1_model_b")
ROOT = PACKAGE
TOOLS = ROOT / "tools"

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402
from ccn_tools.baselines import STATE_WEIGHT  # noqa: E402
from ccn_tools.score import score_d1  # noqa: E402

KEYP = ROOT / "tasks" / "dev" / "D1_dev_catchments_2025.csv"
key = pd.read_csv(KEYP)
cat = pd.read_csv(ROOT / "data" / "06_nature" / "catchments.csv").set_index("catchment_id")
tpl = pd.read_csv(ROOT / "tasks" / "templates" / "D1_catchment_priority_submission.csv")
A = pd.read_csv(A_DIR / "D1_catchment_priority_submission.csv")
B = pd.read_csv(B_DIR / "D1_catchment_priority_submission.csv")
BASE = pd.read_csv(ROOT / "outputs" / "D1_baseline.csv")
PC, NC = "apetit_p_to_water_kg", "apetit_n_to_water_kg"
ids = list(tpl.catchment_id)
A, B, BASE = (d.set_index("catchment_id").loc[ids].reset_index() for d in (A, B, BASE))
dev = list(key.catchment_id)
assert ((A[PC] == 0) == (B[PC] == 0)).all() and ((A[NC] == 0) == (B[NC] == 0)).all(), "zero rows must agree"
print("zero-load catchments (both models):", list(A.loc[A[PC] == 0, "catchment_id"]))


def ranked(p, n, scope="all42"):
    """Official priority formula. scope=all42 mirrors baselines.d1_area; scope=active is A's choice (P > 1 kg)."""
    p, n = pd.Series(np.asarray(p, float), index=ids), pd.Series(np.asarray(n, float), index=ids)
    m = p > 1.0 if scope == "active" else p == p
    pr = (p / p[m].median() + 0.5 * n / n[m].median()) * cat.loc[ids, "ecological_status_class"].map(STATE_WEIGHT) * cat.loc[ids, "p_sensitivity"]
    return pr, pr.rank(ascending=False, method="first").astype(int)


def blend(wp, wn):
    p = np.where(A[PC] > 0, 10 ** (wp * np.log10(A[PC].clip(lower=1e-9)) + (1 - wp) * np.log10(B[PC].clip(lower=1e-9))), 0.0)
    n = np.where(A[NC] > 0, 10 ** (wn * np.log10(A[NC].clip(lower=1e-9)) + (1 - wn) * np.log10(B[NC].clip(lower=1e-9))), 0.0)
    return p, n


def make(p, n):
    s = pd.DataFrame({"catchment_id": ids, "region": tpl.region, PC: np.round(p, 2), NC: np.round(n, 1)})
    pr, rk = ranked(s[PC], s[NC])
    s["priority_rank"] = rk.values
    return s, pr


E, E_pr = make(*blend(0.5, 0.5))
cand = {"A": A, "B": B, "E": E}

# ---------------------------------------------------------------- full 6, official
full = {k: score_d1(v, key) for k, v in cand.items()}
full["package_baseline"] = score_d1(BASE, key)
for k, v in full.items():
    print(f"FULL6 {k:17s} {json.dumps(v)}")

# ---------------------------------------------------------------- the two lenses
held = {k: [score_d1(v, key[key.catchment_id == c])["score"] for c in dev] for k, v in cand.items()}
drop = {k: [score_d1(v, key[key.catchment_id != c])["score"] for c in dev] for k, v in cand.items()}


def nested():
    """W: weight per nutrient chosen on the other 5 catchments, applied to the held-out one."""
    grid = np.round(np.arange(0, 1.01, 0.1), 1)
    lt = key.set_index("catchment_id")
    a, b = A.set_index("catchment_id"), B.set_index("catchment_id")
    sc, ws = [], []
    for c in dev:
        rest = [x for x in dev if x != c]
        w = []
        for col in (PC, NC):
            errs = [float(np.mean(np.abs(g * np.log10(a.loc[rest, col]) + (1 - g) * np.log10(b.loc[rest, col]) - np.log10(lt.loc[rest, col])))) for g in grid]
            w.append(float(grid[int(np.argmin(errs))]))
        s, _ = make(*blend(*w))
        sc.append(score_d1(s, key[key.catchment_id == c])["score"])
        ws.append(w)
    return sc, ws


held["W_nested"], W_weights = nested()
print("\nfold          ", "  ".join(f"{c:>6s}" for c in dev), "   mean")
for lab, d in (("HELD-OUT", held), ("DROP-ONE", drop)):
    for k, v in d.items():
        print(f"{lab} {k:9s}", "  ".join(f"{x:6.2f}" for x in v), f"  {np.mean(v):6.2f}")
print("W weights (A share of P, N) per fold:", W_weights)


def paired(x, y):
    d = np.array(x) - np.array(y)
    n = len(d)
    se = d.std(ddof=1) / np.sqrt(n)
    t = stats.t.ppf(0.975, n - 1)
    flips = [abs((d * np.array(s)).mean()) for s in itertools.product((1, -1), repeat=n)]
    p = float(np.mean([f >= abs(d.mean()) - 1e-12 for f in flips]))
    return dict(mean=round(float(d.mean()), 2), ci95=[round(float(d.mean() - t * se), 2), round(float(d.mean() + t * se), 2)],
                wins=int((d > 0).sum()), ties=int((d == 0).sum()), losses=int((d < 0).sum()), signflip_p=round(p, 4))


cmp_ = {f"{lab}_{a}_minus_{b}": paired(d[a], d[b]) for lab, d in (("held", held), ("drop", drop)) for a, b in (("E", "A"), ("E", "B"), ("A", "B"))}
cmp_["held_W_minus_E"] = paired(held["W_nested"], held["E"])
for k, v in cmp_.items():
    print(f"PAIRED {k:22s} {json.dumps(v)}")

# ---------------------------------------------------------------- pre-registered rule
mh = {k: float(np.mean(v)) for k, v in held.items()}
md = {k: float(np.mean(v)) for k, v in drop.items()}
gate = mh["E"] > max(mh["A"], mh["B"]) and md["E"] > max(md["A"], md["B"])
ship = "E" if gate else ("A" if mh["A"] >= mh["B"] else "B")
print(f"\nGATE held E {mh['E']:.3f} A {mh['A']:.3f} B {mh['B']:.3f} | drop E {md['E']:.3f} A {md['A']:.3f} B {md['B']:.3f} -> {'PASS' if gate else 'FAIL'}; SHIP {ship}")

# ---------------------------------------------------------------- review checks
lt = key.set_index("catchment_id")
sign = {}
for k, v in cand.items():
    s = v.set_index("catchment_id")
    sign[k] = {nut: [round(float(np.log10(s.loc[c, col] / lt.loc[c, col])), 3) for c in dev] for nut, col in (("P", PC), ("N", NC))}
    print(f"SIGNED log10(pred/true) {k}: P {sign[k]['P']}  N {sign[k]['N']}")
err_corr = {nut: round(float(np.corrcoef(sign["A"][nut], sign["B"][nut])[0, 1]), 3) for nut in ("P", "N")}
print("corr of A and B signed dev errors:", err_corr)

mon = cat.loc[dev, "monitoring_station"].astype(str) == "True"
subset = {}
for lab, cs in (("monitored", list(mon[mon].index)), ("unmonitored", list(mon[~mon].index)), ("FI", [c for c in dev if c.startswith("CA")]), ("SE", [c for c in dev if c.startswith("CS")])):
    subset[lab] = dict(catchments=cs, **{k: {m: score_d1(v, key[key.catchment_id.isin(cs)])[m] for m in ("mae_log10_p", "mae_log10_n")} for k, v in cand.items()})
    print("SUBSET", lab, json.dumps(subset[lab]))

la = lambda col, m: float(np.mean(np.abs(np.log10(A.loc[m, col] / B.loc[m, col]))))  # noqa: E731
act = (A[PC] > 1).values
isdev = A.catchment_id.isin(dev).values
se = (tpl.region == "SE_SKANE").values
print("\nregion counts dev:", dict(pd.Series(tpl.region[isdev]).value_counts()), "non-dev:", dict(pd.Series(tpl.region[~isdev]).value_counts()))
disagree = {}
for lab, m in (("dev", act & isdev), ("nondev_all", act & ~isdev), ("nondev_FI", act & ~isdev & ~se), ("nondev_SE", act & ~isdev & se)):
    disagree[lab] = dict(n=int(m.sum()), P=round(la(PC, m), 4), N=round(la(NC, m), 4),
                         signed_P=round(float(np.mean(np.log10(A.loc[m, PC] / B.loc[m, PC]))), 4), signed_N=round(float(np.mean(np.log10(A.loc[m, NC] / B.loc[m, NC]))), 4))
    print("A vs B |log10| disagreement", lab, json.dumps(disagree[lab]))

top = lambda s, k=5: list(s.sort_values("priority_rank").catchment_id.head(k))  # noqa: E731
tops = {"A": top(A), "B": top(B), "E": top(E), "package_baseline": top(BASE)}
print("TOP5", json.dumps(tops))
_, rA42 = ranked(A[PC], A[NC])
_, rB42 = ranked(B[PC], B[NC])
_, rEact = ranked(E[PC], E[NC], "active")
_, rAact = ranked(A[PC], A[NC], "active")
print("A file ranks reproduced by active-median formula:", bool((rAact.values == A.priority_rank.values).all()))
print("B file ranks reproduced by all-42 median formula:", bool((rB42.values == B.priority_rank.values).all()))
Ah = A.assign(priority_rank=rA42.values)
print("A re-ranked with all-42 median: dev", json.dumps(score_d1(Ah, key)), "top5", top(Ah))
print("E top5 with active median:", list(rEact.sort_values().index[:5]), "ranks changed:", int((rEact.values != E.priority_rank.values).sum()))
agree = {"spearman_A_B_all42": round(float(A.priority_rank.corr(B.priority_rank, method="spearman")), 4),
         "spearman_E_A": round(float(E.priority_rank.corr(A.priority_rank, method="spearman")), 4),
         "spearman_E_B": round(float(E.priority_rank.corr(B.priority_rank, method="spearman")), 4),
         "top5_E_in_A": len(set(tops["E"]) & set(tops["A"])), "top5_E_in_B": len(set(tops["E"]) & set(tops["B"])),
         "top5_E_in_baseline": len(set(tops["E"]) & set(tops["package_baseline"])), "top5_all_three": sorted(set(tops["A"]) & set(tops["B"]) & set(tops["E"]))}
print("AGREEMENT", json.dumps(agree))

# ---------------------------------------------------------------- write the shipped file, then score the file itself
final = cand[ship]
path = HERE / "D1_catchment_priority_submission.csv"
SRC = {"A": A_DIR / "D1_catchment_priority_submission.csv", "B": B_DIR / "D1_catchment_priority_submission.csv"}
if ship in SRC:
    shutil.copyfile(SRC[ship], path)   # byte-exact: "as submitted" means the same file, not a re-serialisation
else:
    final.to_csv(path, index=False)
E.to_csv(HERE / "alt_ensemble_not_submitted.csv", index=False)   # kept for a lead override; never the submission unless E passes
back = pd.read_csv(path)
checks = dict(rows=len(back), cols_match=list(back.columns) == list(tpl.columns), ids_match=list(back.catchment_id) == ids,
              region_match=list(back.region) == list(tpl.region), ranks_ok=sorted(back.priority_rank) == list(range(1, 43)), nulls=int(back.isna().sum().sum()))
print("FILE CHECKS", json.dumps(checks))
r = subprocess.run([sys.executable, "-m", "ccn_tools.score", "D1", "--submission", str(path), "--key", str(KEYP)], capture_output=True, text=True,
                   cwd=str(HERE), env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(TOOLS)))
cli = json.loads(r.stdout)
print("OFFICIAL CLI on shipped file:", json.dumps(cli))

fs = final.set_index("catchment_id")
order = final.sort_values("priority_rank").catchment_id.head(10)
pr_final = E_pr if ship == "E" else ranked(final[PC], final[NC], "active" if ship == "A" else "all42")[0]
top10 = [dict(rank=int(fs.loc[c, "priority_rank"]), catchment=c, region=fs.loc[c, "region"], status=cat.loc[c, "ecological_status_class"],
              p_sensitivity=float(cat.loc[c, "p_sensitivity"]), p_kg=float(fs.loc[c, PC]), n_kg=float(fs.loc[c, NC]), priority=round(float(pr_final[c]), 3)) for c in order]
for t in top10:
    print("TOP10", json.dumps(t))
tot = dict(P_kg=round(float(final[PC].sum())), N_kg=round(float(final[NC].sum())), A_P=round(float(A[PC].sum())), A_N=round(float(A[NC].sum())), B_P=round(float(B[PC].sum())), B_N=round(float(B[NC].sum())))
print("TOTALS", json.dumps(tot))
json.dump(dict(full6=full, held_out=held, drop_one=drop, W_weights=W_weights, means=dict(held=mh, drop=md), paired=cmp_, gate_pass=bool(gate), ship=ship,
               signed_errors=sign, error_corr=err_corr, subsets=subset, disagreement=disagree, top5=tops, agreement=agree, file_checks=checks,
               official_cli_on_shipped=cli, top10=top10, totals=tot, dev_catchments=dev), open(HERE / "ensemble.json", "w"), indent=1, default=str)
