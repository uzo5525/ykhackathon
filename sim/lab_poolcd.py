"""광역 풀 좌표 하강 루프: SCHED 의 라운드를 차례로, 스크리닝(+1.5%p 이상이면) -> 확정(lab_pool --confirm 규칙).

python sim/lab_poolcd.py --start 0 --until "20:30"
"""
import argparse
import datetime as dt
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab_cd as L  # noqa: E402
import lab_pool as P  # noqa: E402
from lab_build import build  # noqa: E402

SCHED = [
    [("ESCORT_SLOTS", 14), ("ESCORT_RADIUS", 3), ("TAU", 1.5), ("H_MAX", 10), ("UTIL_SCORE_W", 1.3), ("BONUS_PLAZA", 3.0)],
    [("GUILLO_BONUS", 10.0), ("BONUS_DEPOT", 14.0), ("BONUS_HALL", 8.0), ("COVER_H_BONUS", 6), ("HYST_F", 0.5), ("STUCK_LIMIT", 3)],
    [("FORT_E2_R", 2), ("GAR_E2", 3), ("RI_CONF_DIST", 5), ("DEFEND_PULL_DIST", 6), ("DB_THRESHOLD", 10), ("ENEMY_SPAWN_CAP", 4)],
    [("RISK_ACCEPT", 12.0), ("PENALTY_ENEMY_FLAG", 6.0), ("BONUS_RETAKE", 1.0), ("REQUIRED_HOME_DEFENSE", 2), ("SPECIAL_SQUAD", 3), ("IDLE_RESOURCE", 10)],
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--until", default="20:30")
    ns = ap.parse_args()
    hh, mm = map(int, ns.until.split(":"))
    for r in range(ns.start, len(SCHED)):
        now = dt.datetime.now()
        if (now.hour, now.minute) >= (hh, mm):
            L.log_j(f"- 광역 CD 루프: 시간 도달({ns.until}) -> 중단")
            break
        s = L.load_state()
        champ = s["champion"]
        cands = []
        for i, (k, v) in enumerate(SCHED[r]):
            nm = f"pc{r:02d}_{i}_{k.lower()}_{str(v).replace('.', 'p')}"
            build(nm, champ, {k: v}, f"{k}={v}", parent=champ)
            cands.append((nm, f"{k}={v}"))
        try:
            res = P.run([c for c, _ in cands] + [champ], 36, 110_000_000 + r * 1_000_000, f"PC{r}")
            d = P.report(res, champ, f"광역 CD 라운드 {r} (챔피언 {champ})")
            best = max(cands, key=lambda c: d[c[0]][0])
            if d[best[0]][0] >= 0.015:
                subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "lab_pool.py"), "--confirm", best[0],
                                "--desc", "광역 CD " + best[1], "--n", "36", "--rbase", str(120_000_000 + r * 1_000_000),
                                "--tag", f"PC{r}c"], check=False)
            else:
                L.log_j(f"- 광역 CD 라운드 {r}: 채택 없음(최고 {best[1]} {d[best[0]][0]:+.1%})")
        except Exception as e:  # noqa: BLE001
            L.log_j(f"- 광역 CD 라운드 {r} 오류: {e!r}")


if __name__ == "__main__":
    main()
