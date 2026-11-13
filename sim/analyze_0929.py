"""0929_2 리더보드 리플레이(우리 봇 POV) 분석. python sim/analyze_0929.py ["replay/0929_2 replay"]"""
import glob
import json
import os
import statistics
import sys

DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "replay", "0929_2 replay")
CK = (20, 40, 60, 80, 100, 120, 140, 160)


def units(o, team, kind):
    return sum(u[4] for u in o["units"] if u[0] == team and u[1] == kind)


def analyze(path):
    d = json.load(open(path, encoding="utf-8"))
    me = d["side"]
    op = "K" if me == "Y" else "Y"
    name = os.path.basename(path)[:-5]
    T = d["turns"]
    o0 = T[0]["observation"]
    base = {}
    for y, row in enumerate(o0["map"]):
        for x, ch in enumerate(row):
            if ch == "H":
                base.setdefault("H", []).append((x, y))
    # 본진: 첫 턴 F 위치
    b_me = next((u[2], u[3]) for u in T[1]["observation"]["units"] if u[0] == me and u[1] == "F")
    b_op = next(((u[2], u[3]) for u in T[1]["observation"]["units"] if u[0] == op and u[1] == "F"), None)
    blds = {b["id"]: b for b in o0["buildings"]}
    dist = lambda a, b: abs(a[0] - b[0]) + abs(a[1] - b[1])  # noqa: E731
    home = {i for i, b in blds.items() if b_op and dist((b["x"], b["y"]), b_me) < dist((b["x"], b["y"]), b_op)}
    last = T[-1]["observation"]
    bsc = {b["id"]: b.get("score", 0) or 0 for b in last["buildings"]}

    def score_of(o):     # 적 점수는 경기 중 숨김 -> 최종 공개 점수 x 소유로 재구성
        out = {me: 0, op: 0}
        for b in o["buildings"]:
            if b["owner"] in out:
                out[b["owner"]] += bsc.get(b["id"], 0)
        return out
    sc = score_of(last)
    occ_acc = {me: 0, op: 0}
    rt = [t["observation"].get("myResponseMs", 0) for t in T[2:]]
    cap = {me: 0, op: 0}
    neut = {me: 0, op: 0}
    pulled = 0
    home_lost = []           # (턴, 건물 종류) 우리 홈 쪽 건물이 적에게 중립화/점령
    first_lead = None
    lead_turn_op = None
    timeline = []
    peak = {"opW": 0, "opF": 0, "myW": 0, "myF": 0}
    myF_prev = None
    f_drop = 0
    type_loss = {}
    for t in T[1:]:
        o = t["observation"]
        for e in o["events"]:
            k = e["kind"]
            if k == "capture":
                cap[e["team"]] = cap.get(e["team"], 0) + 1
            elif k == "neutral":
                neut[e["team"]] = neut.get(e["team"], 0) + 1
                if e["team"] == op:
                    bt = blds[e["buildingId"]]["type"]
                    type_loss[bt] = type_loss.get(bt, 0) + 1
                    if e["buildingId"] in home:
                        home_lost.append((o["turn"], bt))
            elif k == "pulled":
                pulled += 1
        s = score_of(o)
        occ_acc[me] += s[me]
        occ_acc[op] += s[op]
        if lead_turn_op is None and s[op] > s[me] and o["turn"] > 10:
            lead_turn_op = o["turn"]
        for key, tm, kd in (("opW", op, "W"), ("opF", op, "F"), ("myW", me, "W"), ("myF", me, "F")):
            peak[key] = max(peak[key], units(o, tm, kd))
        mf = units(o, me, "F")
        if myF_prev is not None and mf < myF_prev:
            f_drop += myF_prev - mf
        myF_prev = mf
        if o["turn"] in CK:
            timeline.append((o["turn"], s[me], s[op], units(o, me, "F"), units(o, me, "W"), units(o, op, "F"), units(o, op, "W"),
                             o["resources"][me], o["resources"][op]))
    return {"name": name, "side": me, "win": d["result"]["winner"] == me, "reason": d["result"]["reason"], "turns": last["turn"],
            "sc": (sc[me], sc[op]), "occ": (occ_acc[me], occ_acc[op]), "cap": (cap[me], cap[op]), "neut": (neut[me], neut[op]),
            "pulled": pulled, "home_lost": home_lost, "lead_op": lead_turn_op, "tl": timeline, "peak": peak, "f_drop": f_drop,
            "rt_max": max(rt) if rt else 0, "rt_p95": sorted(rt)[int(0.95 * (len(rt) - 1))] if rt else 0, "t0": T[1]["observation"].get("myResponseMs"),
            "type_loss": type_loss, "n_blds": len(blds),
            "final_own": {k: sum(1 for b in last["buildings"] if b["owner"] == k) for k in (me, op)}}


def main():
    rows = [analyze(p) for p in sorted(glob.glob(os.path.join(DIR, "*.json")))]
    print(f"{'상대':18} {'결과':3} {'사유':7} {'턴':>3} {'점수':>7} {'점령-턴':>11} {'점령(우/적)':>9} {'중립화(우/적)':>11} {'홈 피탈':>5} {'적 역전턴':>7} {'적W최대':>6} {'우W최대':>6} {'우F감소':>6} {'응답max':>6} {'첫턴':>5}")
    for r in rows:
        print(f"{r['name'][:17]:18} {'승' if r['win'] else '패':3} {r['reason']:7} {r['turns']:>3} {r['sc'][0]:>3}:{r['sc'][1]:<3} "
              f"{r['occ'][0]:>5}:{r['occ'][1]:<5} {r['cap'][0]:>4}/{r['cap'][1]:<4} {r['neut'][0]:>5}/{r['neut'][1]:<5} {len(r['home_lost']):>5} "
              f"{str(r['lead_op'] or '-'):>7} {r['peak']['opW']:>6} {r['peak']['myW']:>6} {r['f_drop']:>6} {r['rt_max']:>6} {r['t0']:>5}")
    for grp, sel in (("승리", [r for r in rows if r["win"]]), ("패배", [r for r in rows if not r["win"]])):
        if not sel:
            continue
        m = lambda f: statistics.fmean(f(r) for r in sel)  # noqa: E731
        print(f"\n[{grp} {len(sel)}경기 평균] 점수 {m(lambda r: r['sc'][0]):.1f}:{m(lambda r: r['sc'][1]):.1f}, 점령-턴 {m(lambda r: r['occ'][0]):.0f}:{m(lambda r: r['occ'][1]):.0f}, "
              f"적의 우리 건물 중립화 {m(lambda r: r['neut'][1]):.1f}, 홈 피탈 {m(lambda r: len(r['home_lost'])):.1f}, 적 W 최대 {m(lambda r: r['peak']['opW']):.1f} vs 우리 {m(lambda r: r['peak']['myW']):.1f}, "
              f"우리 F 감소 {m(lambda r: r['f_drop']):.1f}")
    for r in rows:
        if r["win"]:
            continue
        print(f"\n=== 패배: {r['name']} ({r['side']} 진영, {r['reason']}, {r['turns']}턴) ===")
        print("  턴 | 점수 우:적 | 우 F/W | 적 F/W | 자원 우:적")
        for tl in r["tl"]:
            print(f"  {tl[0]:>3} | {tl[1]:>3}:{tl[2]:<3} | {tl[3]:>2}/{tl[4]:<3} | {tl[5]:>2}/{tl[6]:<3} | {tl[7]:>3}:{tl[8]}")
        print(f"  적에게 중립화된 우리 건물 종류: {r['type_loss']}")
        print(f"  홈 쪽 피탈(턴, 종류): {r['home_lost'][:15]}{' ...' if len(r['home_lost']) > 15 else ''}")
        print(f"  종료 보유 건물 우:적 = {r['final_own']}")


if __name__ == "__main__":
    main()
