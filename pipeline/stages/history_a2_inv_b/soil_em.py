"""Unsupervised posterior P(true soil = organic) per parcel from the soil-map class and clay %.

Model: true class k with prior pi_k; the map reports k with probability ACC (0.88, DATA_DICTIONARY)
and any other class uniformly otherwise; clay % depends on the true class (histogram, 3-point bins).
Fitted by EM on parcels.csv only (no labels).  Run as a script to print the fit and a label check.
"""
from ccn_paths import PACKAGE, stage_dir
import collections, csv, os, json
import inv

CLASSES = ["clay", "silt", "fine_sand", "sand", "organic"]
ACC = 0.88
BIN = 3


def fit(iters=200):
    par = inv.rd("01_master/parcels.csv")
    obs = [(r["parcel_id"], r["soil_class_soilmap"], min(int(float(r["clay_pct_soilmap"]) // BIN), 100 // BIN)) for r in par]
    nb = 100 // BIN + 1
    K = len(CLASSES)
    pi = {k: 1 / K for k in CLASSES}
    # init clay histograms from the map classes themselves
    h = {k: [1.0] * nb for k in CLASSES}
    for _, j, b in obs:
        h[j][b] += 1
    for k in CLASSES:
        s = sum(h[k]); h[k] = [v / s for v in h[k]]
    conf = lambda j, k: ACC if j == k else (1 - ACC) / (K - 1)
    for it in range(iters):
        npi = {k: 1e-9 for k in CLASSES}
        nh = {k: [1e-6] * nb for k in CLASSES}
        post = {}
        for pid, j, b in obs:
            w = {k: pi[k] * conf(j, k) * h[k][b] for k in CLASSES}
            s = sum(w.values())
            for k in CLASSES:
                w[k] /= s
                npi[k] += w[k]
                nh[k][b] += w[k]
            post[pid] = w["organic"]
        tot = sum(npi.values())
        pi = {k: v / tot for k, v in npi.items()}
        for k in CLASSES:
            s = sum(nh[k]); h[k] = [v / s for v in nh[k]]
    return post, pi, h


_CACHE = os.path.join(str(stage_dir("history_a2_inv_b")), "soil_posterior.json")


def posterior():
    if os.path.exists(_CACHE):
        return json.load(open(_CACHE))
    post, pi, h = fit()
    json.dump(post, open(_CACHE, "w"))
    return post


if __name__ == "__main__":
    post, pi, h = fit()
    json.dump(post, open(_CACHE, "w"))
    print("priors", {k: round(v, 4) for k, v in pi.items()})
    for k in CLASSES:
        print("clay%% hist %-9s" % k, " ".join("%.2f" % v for v in h[k][:20]))
    par = {r["parcel_id"]: r for r in inv.rd("01_master/parcels.csv")}
    mapped = sum(float(r["area_ha"]) for r in par.values() if r["soil_class_soilmap"] == "organic")
    expct = sum(post[p] * float(r["area_ha"]) for p, r in par.items())
    print("organic area: soil map %.0f ha, EM expected %.0f ha (all parcels)" % (mapped, expct))
    for cls in CLASSES:
        ps = [post[p] for p, r in par.items() if r["soil_class_soilmap"] == cls]
        print("  mapped %-9s n=%5d mean P(org)=%.3f" % (cls, len(ps), sum(ps) / len(ps)))
