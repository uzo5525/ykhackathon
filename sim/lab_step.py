"""연구실 수동 단계: 후보 스크리닝 + (선택) 확정전·승격. lab_cd 의 screen/promote 재사용.

python sim/lab_step.py --screen a,b,c [--rand 500] --confirm best --tag X
  --screen: 챔피언과 각 1,056경기. --confirm-name: 지정 후보를 새 시드 2,000경기로 확정, 하한 > 50% 면 승격.
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab_cd as L

ap = argparse.ArgumentParser()
ap.add_argument("--screen", default="")
ap.add_argument("--confirm-name", default="")
ap.add_argument("--desc", default="")
ap.add_argument("--rbase", type=int, default=40_000_000)
ap.add_argument("--tag", default="step")
ns = ap.parse_args()
s = L.load_state()
champ = s["champion"]
if ns.screen:
    cands = ns.screen.split(",")
    res, _ = L.screen(cands, champ, 500, ns.rbase, ns.tag)
    lines = [f"\n### 수동 스크리닝 {ns.tag} (챔피언 {champ})", "| 후보 | 승률 [95% CI] | F 사망 (나/챔피언) |", "|---|---|---|"]
    for c in sorted(cands, key=lambda c: -res[c]["win"]):
        x = res[c]
        lines.append(f"| {c} | {x['win']:.1%} [{x['lo']:.1%}-{x['hi']:.1%}] | {x['fd']:.2f} / {x['fd_opp']:.2f} |")
        print(c, f"{x['win']:.1%} [{x['lo']:.1%}-{x['hi']:.1%}]")
    L.log_j("\n".join(lines))
if ns.confirm_name:
    c = ns.confirm_name
    conf, _ = L.screen([c], champ, 1000, ns.rbase + 500_000, ns.tag + "c", real=False)
    x = conf[c]
    L.log_j(f"- 확정전 {c} ({ns.desc}): {x['win']:.1%} [{x['lo']:.1%}-{x['hi']:.1%}] n={x['n']}")
    print("confirm", c, f"{x['win']:.1%} [{x['lo']:.1%}-{x['hi']:.1%}]")
    if x["lo"] > 0.5 and L.pool_gate(c, champ, 99):
        L.promote(s, c, ns.desc or c, x)
        L.save_state(s)
        print("promoted ->", s["champion"])
