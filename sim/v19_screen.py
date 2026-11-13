"""v19 자율 실험: 후보들 vs 상대(기본 v17b1) 스크리닝.

python sim/v19_screen.py --cands v19_anchor,v19_anchor2 [--opp v17_B1] [--rand 472] [--rbase 11000000] [--tag s1]
  후보마다 실제 맵 56 전수 + 랜덤 시드 rbase..rbase+rand-1 x 2진영. 결과: sim/v19/<tag>.md (+ 콘솔)
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v17_master as M  # noqa: E402

ROOT = M.ROOT
M.OUT = os.path.join(ROOT, "sim", "v19")
TOP = {"v16f2", "v16f", "v12_1", "v16_Dx", "v16_AC", "v19", "v20", "v21", "v22", "v23", "v24", "v25", "v26", "v27", "v28", "v29", "v30", "v31", "v32", "v33", "v34", "v35", "v36", "v37", "v38", "v39", "v40", "v41", "v42", "v43", "v44", "v45", "v46", "v47", "v48"}


def path(n):
    return n if n in TOP else f"bots/{n}"


class Agg(M.Agg):
    def add(self, r):
        super().add(r)
        if r["ff_a"] or r["ff_b"]:
            return
        k = f"{os.path.basename(r['a'])}|{os.path.basename(r['b'])}"
        x = self.d.setdefault("_x", {}).setdefault(k, {"n": 0, "ql": 0, "ql_b": 0, "caps40": 0, "p95": [], "rt": 0})
        x["n"] += 1
        x["ql"] += r["A"].get("ql", 0)
        x["ql_b"] += r["B"].get("ql", 0)
        x["caps40"] += r["A"].get("caps40", 0)
        if len(x["p95"]) < 3000:
            x["p95"].append(r["A"].get("p95", 0))
        x["rt"] = max(x["rt"], r["A"].get("rt", 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cands", required=True)
    ap.add_argument("--opp", default="v17_B1")
    ap.add_argument("--rand", type=int, default=472)
    ap.add_argument("--rbase", type=int, default=11_000_000)
    ap.add_argument("--no-real", action="store_true")
    ap.add_argument("--tag", default="screen")
    ap.add_argument("--jobs", type=int, default=22)
    ns = ap.parse_args()
    os.makedirs(M.OUT, exist_ok=True)
    st = {}
    R = M.Runner(ns.jobs, st, Agg())
    cands = ns.cands.split(",")
    opps = ns.opp.split(",")
    games = []
    for c in cands:
        for o in opps:
            if not ns.no_real:
                games += [(c, path(c), o, path(o), s, "real") for s in range(28)]
            games += [(c, path(c), o, path(o), ns.rbase + s, "random") for s in range(ns.rand)]
    M.log(f"[{ns.tag}] {len(games) * 2} games")
    R.run(games, ns.tag)
    ag = R.agg
    L = [f"# v19 {ns.tag}\n", f"- 유효 {st.get('games', 0)}, 오류 {st.get('errors', 0)}, 몰수 {st.get('forfeits', 0)}\n",
         "| 후보 | 상대 | 경기 | 승률 [95% CI] | 실제 56 / 랜덤 | 5턴 내 피탈 (나/상대) | F 사망 (나/상대) | 40턴 점령 | 점령 몫 | p95 중앙 / 응답 max |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for c in cands:
        for o in opps:
            g = ag.get(c, o)
            if not g["n"]:
                continue
            x = ag.d["_x"][f"{c}|{o}"]
            n = max(1, x["n"])
            re_ = ag.get(c, o, ("real",))["win"]
            ra = ag.get(c, o, ("random",))["win"]
            p95 = sorted(x["p95"])[len(x["p95"]) // 2] if x["p95"] else 0
            line = (f"| {c} | {o} | {g['n']} | **{g['win']:.1%}** [{g['ci'][0]:.1%}-{g['ci'][1]:.1%}] | "
                    f"{'-' if re_ is None else f'{re_:.1%}'} / {'-' if ra is None else f'{ra:.1%}'} | {x['ql'] / n:.2f} / {x['ql_b'] / n:.2f} | "
                    f"{(g['fsp'] - g['fal']) / n:.2f} / {(g['fsp_b'] - g['fal_b']) / n:.2f} | {x['caps40'] / n:.1f} | {g['occ_share']:.1%} | {p95} / {x['rt']} |")
            L.append(line)
            rs = {k: round(v / max(1, g["rs_n"]), 1) for k, v in g["rs"].items() if k.startswith(("anchor", "guard"))}
            M.log(f"{c} vs {o}: {g['win']:.1%} [{g['ci'][0]:.1%}-{g['ci'][1]:.1%}] n={g['n']} ql {x['ql'] / n:.2f}/{x['ql_b'] / n:.2f} {rs}")
    with open(os.path.join(M.OUT, f"{ns.tag}.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
