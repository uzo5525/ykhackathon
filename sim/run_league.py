"""정밀 벤치마크 리그.

사용: python sim/run_league.py --main v9 --opps v8,v7,v5 --seeds 200-299 [--jobs 8] [--out sim/benchmark_results]

진영 공정성: 각 시드(같은 맵)를 main=Y, main=K 로 한 번씩 치른다(짝 대전).
  -> 시드 100개 = 매치업당 200경기, 선공 100 / 후공 100 정확히 대칭.

지표(모두 main 봇 기준, 상대 봇 값도 함께 저장)
  win_rate, 선공(Y)/후공(K) 승률, avg_score, avg_occ
  F_spawn_survival_rate   = 경기 종료 시 생존 F / 생산 F
  F_capture_survival_rate = 1회 이상 점령에 참여한 F 중 종료 시 생존 비율
  PCDR                    = 점령 성공 후 3턴 이내 사망 F / 점령 성공 F
  engagement ER mean/median = W-W 교전이 실제로 일어난 칸에서 W_our / (W_enemy + 1)
  thrash_rate             = 직전 턴 도착 칸으로 되돌아간 유닛 이동 / 전체 유닛 이동
                            (긴급 제외: 출발 칸 맨해튼 2 이내에 적 W가 있던 이동은 분모·분자 제외, TELE 제외)
  runtime p50/p95/max     = 러너 측정 응답 시간(ms, 파이프 왕복 포함, 병렬 실행 부하 포함)
  UFS (Useful F Survival) = 점령에 성공한 F 중, 이후 다시 점령했거나 경기 종료까지 생존한 F 비율
  flags_pulled            = 소유 건물 위 아군 F가 전투로 제거되어 건물이 중립화된 횟수(경기당)
  T0 (턴0 소요 시간)       = 프로세스 기동 ~ 첫 END 수신(규칙서 기준). 두 봇에 첫 턴을 동시에 보낸다.

F 가상 ID: 엔진은 (셀, 팀, 병종) 인원만 관리하므로 같은 칸의 F는 선입선출로 이동시킨다고 가정해 추적한다.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Game, TOTAL_TURNS, TEAMS  # noqa: E402
from run_match import Bot, TIMEOUT, TIMEOUT_FIRST  # noqa: E402


MAPS = []


def map_for(seed, mode):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if mode.startswith("replay:"):          # 단일 실제 맵 고정: --maps replay:replay10
        return os.path.join(root, "replay", mode.split(":", 1)[1] + ".json")
    if mode != "replay":
        return None
    import glob
    files = sorted(glob.glob(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                          "replay", "replay*.json")))
    return files[seed % len(files)]


def play(args):
    seed, main_dir, opp_dir, main_team, maps = (args + ("random",))[:5]
    g = Game(seed, map_for(seed, maps))
    opp_team = "K" if main_team == "Y" else "Y"
    dirs = {main_team: main_dir, opp_team: opp_dir}
    errdir = os.environ.get("LEAGUE_STDERR_DIR")
    errp = os.path.join(errdir, f"{seed}_{main_team}_{os.getpid()}.log") if errdir else None
    errp_opp = os.path.join(errdir, f"{seed}_{main_team}_{os.getpid()}_opp.log") if errdir else None
    bots = {t: Bot(dirs[t], errp if t == main_team else errp_opp) for t in TEAMS}
    for t in TEAMS:
        bots[t].send(g.init_text(t))
    forfeit = []
    for turn in range(1, TOTAL_TURNS + 1):
        g.turn = turn
        lim = TIMEOUT_FIRST if turn == 1 else TIMEOUT
        for t in TEAMS:
            bots[t].begin(g.turn_text(t), from_spawn=(turn == 1))
        cmds = {t: bots[t].finish(lim) for t in TEAMS}
        forfeit = [t for t in TEAMS if bots[t].timeouts or bots[t].dead]
        if forfeit:
            break
        g.step(cmds)
        if g.instant:
            break
    for b in bots.values():
        b.close()
    win, sy, sk = g.result()
    if forfeit:
        win = "D" if len(forfeit) == 2 else ("K" if forfeit[0] == "Y" else "Y")
    sc = {"Y": sy, "K": sk}

    def read_rstat(path):
        if not path or not os.path.exists(path):
            return None
        import re
        last = None
        for line in open(path, encoding="utf-8", errors="replace"):
            if line.startswith("RSTAT"):
                last = line
        return {k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", last)} if last else None

    rstat = read_rstat(errp)
    rstat_opp = read_rstat(errp_opp)

    def side(t):
        return {"score": sc[t][0], "occ": sc[t][1], "metrics": g.metrics(t),
                "times": bots[t].times, "timeouts": bots[t].timeouts,
                "rstat": rstat if t == main_team else rstat_opp}
    return {"seed": seed, "main_team": main_team, "turns": g.turn, "instant": g.instant,
            "forfeit": forfeit,
            "result": "W" if win == main_team else ("L" if win == opp_team else "D"),
            "main": side(main_team), "opp": side(opp_team)}


def pct(xs, p):
    if not xs:
        return 0.0
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p / 100 * len(xs)))]


def summarize(games, who):
    n = len(games)
    m = [g[who]["metrics"] for g in games]
    sp = sum(x["F_spawned"] for x in m)
    al = sum(x["F_alive"] for x in m)
    cp = sum(x["F_captured"] for x in m)
    ca = sum(x["F_captured_alive"] for x in m)
    pcd = sum(x["F_post_capture_dead"] for x in m)
    mv = sum(x["moves"] for x in m)
    rv = sum(x["reverse"] for x in m)
    er = [v for x in m for v in x["er"]]
    ufs_n = sum(x.get("F_useful", 0) for x in m)
    causes = {}
    for x in m:
        for k, v in x.get("death_cause", {}).items():
            causes[k] = causes.get(k, 0) + v
    pulled = sum(x.get("flags_pulled", 0) for x in m)
    times = [t for g in games for t in g[who]["times"][1:]]
    first = [g[who]["times"][0] for g in games if g[who]["times"]]
    return {
        "avg_score": sum(g[who]["score"] for g in games) / n,
        "avg_occ": sum(g[who]["occ"] for g in games) / n,
        "F_spawned_per_game": sp / n,
        "F_spawn_survival_rate": al / max(1, sp),
        "F_capture_survival_rate": ca / max(1, cp),
        "PCDR": pcd / max(1, cp),
        "UFS": ufs_n / max(1, cp),
        "death_cause": causes,
        "flags_pulled_per_game": pulled / n,
        "t0_p50": pct(first, 50), "t0_max": max(first, default=0.0),
        "engagements": len(er),
        "ER_mean": statistics.fmean(er) if er else 0.0,
        "ER_median": statistics.median(er) if er else 0.0,
        "thrash_rate": rv / max(1, mv),
        "rt_p50": pct(times, 50), "rt_p95": pct(times, 95), "rt_max": max(times, default=0.0),
        "rt_first_max": max(first, default=0.0),
        "timeouts": sum(g[who]["timeouts"] for g in games),
    }


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--main", default="v9")
    ap.add_argument("--opps", default="v8,v7,v5")
    ap.add_argument("--seeds", default="200-299")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--out", default="sim/benchmark_results")
    ap.add_argument("--maps", default="random", help="random | replay (실제 대회 맵 12종 순환)")
    ns = ap.parse_args()
    lo, hi = map(int, ns.seeds.split("-"))
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    main_dir = os.path.join(root, ns.main)
    report = {"main": ns.main, "seeds": ns.seeds, "maps": ns.maps, "matchups": {}}
    rows = []
    t0 = time.time()
    for opp in ns.opps.split(","):
        opp_dir = os.path.join(root, opp)
        opp_dir = opp_dir if os.path.isdir(opp_dir) else os.path.join(root, "bots", opp)
        tasks = [(s, main_dir, opp_dir, t, ns.maps) for s in range(lo, hi + 1) for t in TEAMS]
        with ProcessPoolExecutor(ns.jobs) as ex:
            games = list(ex.map(play, tasks))
        n = len(games)
        w = sum(g["result"] == "W" for g in games)
        l = sum(g["result"] == "L" for g in games)
        d = n - w - l
        by_side = {}
        for t in TEAMS:
            gs = [g for g in games if g["main_team"] == t]
            by_side[t] = sum(g["result"] == "W" for g in gs) / max(1, len(gs))
        # 짝 대전 결과: 같은 맵 양 진영 모두 이김 / 1승1패 / 모두 짐
        pairs = {}
        for g in games:
            pairs.setdefault(g["seed"], []).append(g["result"])
        sweep = sum(1 for v in pairs.values() if v.count("W") == 2)
        lost = sum(1 for v in pairs.values() if v.count("L") == 2)
        ms, os_ = summarize(games, "main"), summarize(games, "opp")
        entry = {"games": n, "W": w, "L": l, "D": d, "win_rate": w / n,
                 "win_rate_as_Y": by_side["Y"], "win_rate_as_K": by_side["K"],
                 "pair_sweep": sweep, "pair_split": len(pairs) - sweep - lost, "pair_lost": lost,
                 "forfeits": sum(1 for g in games if g["forfeit"]),
                 "main": ms, "opp": os_, "games_detail": games}
        report["matchups"][opp] = entry
        for who, name, sm in (("main", ns.main, ms), ("opp", opp, os_)):
            rows.append({"matchup": f"{ns.main} vs {opp}", "bot": name,
                         "win_rate": entry["win_rate"] if who == "main" else (l / n),
                         **{k: v for k, v in sm.items()}})
        print(f"[{time.time() - t0:6.0f}s] {ns.main} vs {opp}: {w}W {l}L {d}D  "
              f"win {w / n * 100:.1f}%  (Y {by_side['Y'] * 100:.1f}% / K {by_side['K'] * 100:.1f}%)", flush=True)

    # ---- 콘솔 표
    hdr = ("matchup", "bot", "win%", "score", "F_surv", "UFS", "PCDR", "pulled/g", "thrash",
           "T0_p50", "T0_max", "p50ms", "p95ms", "maxms")
    print()
    print("{:<13} {:<4} {:>6} {:>6} {:>7} {:>6} {:>6} {:>8} {:>7} {:>7} {:>7} {:>6} {:>6} {:>7}".format(*hdr))
    for r in rows:
        print("{:<13} {:<4} {:>6.1f} {:>6.2f} {:>7.1%} {:>6.1%} {:>6.1%} {:>8.2f} {:>7.1%} {:>7.0f} {:>7.0f} {:>6.1f} {:>6.1f} {:>7.1f}".format(
            r["matchup"], r["bot"], r["win_rate"] * 100, r["avg_score"], r["F_spawn_survival_rate"],
            r["UFS"], r["PCDR"], r["flags_pulled_per_game"], r["thrash_rate"],
            r["t0_p50"], r["t0_max"], r["rt_p50"], r["rt_p95"], r["rt_max"]))
    for opp, e in report["matchups"].items():
        rs = [g["main"].get("rstat") for g in e["games_detail"] if g["main"].get("rstat")]
        if rs:
            tot = {k: sum(r.get(k, 0) for r in rs) for k in ("trig", "succ", "fail", "pend", "w")}
            done = tot["succ"] + tot["fail"]
            print(f"  RESCUE {ns.main} vs {opp}: 발동 {tot['trig']}회(경기당 {tot['trig'] / len(rs):.2f}) "
                  f"성공 {tot['succ']} 실패 {tot['fail']} -> 성공률 {tot['succ'] / max(1, done):.1%}  파견 W {tot['w']}")
    for opp, e in report["matchups"].items():
        gs = e["games_detail"]
        full = [g for g in gs if g["turns"] == TOTAL_TURNS and not g["instant"] and not g["forfeit"]]
        for who, nm in (("main", ns.main), ("opp", opp)):
            late = sum(g[who]["metrics"].get("late_deaths", 0) for g in gs) / len(gs)
            uv = (sum(g[who]["metrics"].get("unit_value", 0) for g in full) / len(full)) if full else 0.0
            neut = sum(g[who]["metrics"].get("late_neut", 0) for g in gs) / len(gs)
            print(f"  ENDGAME {nm} (vs {opp if who == 'main' else ns.main}): 140턴 이후 적 건물 중립화 {neut:.2f}/경기  "
                  f"140턴 이후 F 사망 {late:.2f}/경기  "
                  f"160턴 정규 종료 {len(full)}경기 평균 유닛 환산 {uv:.1f}")
        ties = sum(1 for g in full if g["main"]["score"] == g["opp"]["score"])
        occ_ties = sum(1 for g in full if g["main"]["score"] == g["opp"]["score"] and g["main"]["occ"] == g["opp"]["occ"])
        print(f"  TIEBREAK {ns.main} vs {opp}: 점수 동점 {ties}경기, 점수+점령-턴 동점(유닛 환산으로 판정) {occ_ties}경기")
    print("  평균 누적 점령-턴(occ): " + "  ".join(f"vs {o} {e['main']['avg_occ']:.0f}:{e['opp']['avg_occ']:.0f}"
                                           for o, e in report["matchups"].items()))
    order = ["TRAVEL_DEATH_stayed", "TRAVEL_DEATH_moved", "RETREAT_DEATH", "CAPTURE_DEATH",
             "POST_CAPTURE_DEATH", "SPAWN_DEATH"]
    print("\n  F 사망 원인 (main 봇, 전체 사망 대비 %)")
    for opp, e in report["matchups"].items():
        dc = e["main"]["death_cause"]
        tot = sum(dc.values()) or 1
        print(f"  {ns.main} vs {opp}: 사망 {tot}건 / 경기당 {tot / e['games']:.2f}  " +
              "  ".join(f"{k.replace('_DEATH', '')} {dc.get(k, 0) / tot:.1%}" for k in order))
    for opp, e in report["matchups"].items():
        print(f"  {ns.main} vs {opp}: 선공(Y) {e['win_rate_as_Y']:.1%} / 후공(K) {e['win_rate_as_K']:.1%}  "
              f"짝대전 2승 {e['pair_sweep']} · 1승1패 {e['pair_split']} · 2패 {e['pair_lost']}  몰수 {e['forfeits']}")

    with open(ns.out + ".json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False)
    with open(ns.out + ".csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print(f"\nsaved {ns.out}.json / .csv")


if __name__ == "__main__":
    main()
