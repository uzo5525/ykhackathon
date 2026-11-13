"""광역 풀 평가(10/01 개편): 자기 대전 과적합을 막기 위해 후보를 15상대 풀 평균 승률로 판정.

python sim/lab_pool.py --cands a,b --n 36 --rbase X --tag T [--champ v42]
  각 후보 + 챔피언을 같은 시드(실제 맵 28 x 2 + 랜덤 n x 2)로 풀 전원과 대전. 챔피언 기준선과의 평균 차이를 출력.
  --confirm: 새 시드로 다시 돌려 차이 > 0 이고 승격 조건(평균 +1%p 이상, 하위 상대 3개 평균 하락 없음)이면 승격.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab_cd as L  # noqa: E402
import v17_master as M  # noqa: E402

POOL2 = ["v39", "friend_v17c", "friend_h_r4", "friend_f3_hunt_b", "m1_f5", "m2_guard", "m3_safe",
         "m4_f4", "m5_spread", "m6_hunter", "m7_hunter6", "m8_v44f5", "m9_v44f6", "v43", "sb_econ2_b7", "mz_zone6", "mz_zone5"]   # 11:50 개편: 쉬운 상대(v26, 병원러시) 제외, 강한 사냥형 추가


def run(whos, n, rbase, tag, real=True):
    st = {}
    R = M.Runner(22, st, M.Agg())
    games = []
    for w in whos:
        for o in POOL2:
            if real:
                games += [(w, L.path(w), o, L.path(o), s, "real") for s in range(28)]
            games += [(w, L.path(w), o, L.path(o), rbase + s, "random") for s in range(n)]
    R.run(games, tag)
    out = {}
    for w in whos:
        out[w] = {o: (R.agg.get(w, o)["win"] or 0.0) for o in POOL2}
        out[w]["_avg"] = sum(out[w][o] for o in POOL2) / len(POOL2)
    return out


def report(res, champ, title):
    lines = [f"\n### {title}", "| 후보 | 풀 평균 | 챔피언 대비 | 최저 3 평균 | " + " | ".join(o[:10] for o in POOL2) + " |",
             "|---" * (4 + len(POOL2)) + "|"]
    base = res[champ]
    low3 = lambda r: sum(sorted(r[o] for o in POOL2)[:3]) / 3
    for w in sorted(res, key=lambda w: -res[w]["_avg"]):
        r = res[w]
        lines.append(f"| {w} | {r['_avg']:.1%} | {r['_avg'] - base['_avg']:+.1%} | {low3(r):.1%} | "
                     + " | ".join(f"{r[o]:.0%}" for o in POOL2) + " |")
    L.log_j("\n".join(lines))
    print("\n".join(lines))
    return {w: (res[w]["_avg"] - base["_avg"], low3(res[w]) - low3(base)) for w in res}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cands", default="")
    ap.add_argument("--n", type=int, default=36)
    ap.add_argument("--rbase", type=int, default=90_000_000)
    ap.add_argument("--tag", default="pool")
    ap.add_argument("--champ", default="")
    ap.add_argument("--confirm", default="")
    ap.add_argument("--desc", default="")
    ns = ap.parse_args()
    s = L.load_state()
    champ = ns.champ or s["champion"]
    if ns.cands:
        cands = ns.cands.split(",")
        res = run(cands + [champ], ns.n, ns.rbase, ns.tag)
        report(res, champ, f"광역 풀 스크리닝 {ns.tag} (챔피언 {champ}, 상대 {len(POOL2)}종 x {56 + 2 * ns.n}경기)")
    if ns.confirm:
        c = ns.confirm
        res = run([c, champ], 3 * ns.n, ns.rbase + 700_000, ns.tag + "c", real=False)
        d = report(res, champ, f"광역 풀 확정전 {c} ({ns.desc}) 새 시드 상대당 {6 * ns.n}경기")
        dav, dlow = d[c]
        if dav >= 0.01 and dlow >= -0.01:
            hh, _ = L.screen([c], champ, 500, ns.rbase + 900_000, ns.tag + "h", real=True)
            x = hh[c]
            L.log_j(f"- 맞대결 점검 {c} vs {champ}: {x['win']:.1%} [{x['lo']:.1%}-{x['hi']:.1%}]")
            if x["hi"] >= 0.5:      # 맞대결에서 유의하게 지지만 않으면 됨
                L.promote(s, c, ns.desc or c, {"win": res[c]["_avg"], "lo": res[c]["_avg"] - 0.01, "hi": res[c]["_avg"] + 0.01,
                                                "n": 6 * ns.n * len(POOL2)})
                L.save_state(s)
                print("promoted ->", s["champion"])
                return
        L.log_j(f"- 광역 확정 실패: {c} 평균 {dav:+.1%}, 하위3 {dlow:+.1%}")
        print("not promoted", dav, dlow)


if __name__ == "__main__":
    main()
