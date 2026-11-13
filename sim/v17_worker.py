"""v17 무인 파이프라인 워커: 배치 1개(<= 1000경기)를 돌리고 경기당 요약 1줄(JSONL)만 남긴 뒤 종료한다.

python sim/v17_worker.py <tasks.json> <out.jsonl> [--jobs 22]
  tasks.json = [[seed, a, b, a_team, map, pool], ...]  (a, b 는 ROOT 기준 봇 폴더 상대 경로)
  - 마스터가 배치마다 이 프로세스를 새로 띄우고 끝나면 OS 가 메모리를 회수(프로세스 재활용).
  - 풀 자식도 max_tasks_per_child 로 주기 교체.
  - 봇 응답 하드 킬 3초(run_match.HARD_KILL), 300ms 초과 = 몰수(엔진 규칙).
  - 몰수·타임아웃·예외 경기만 재현 인자와 봇 stderr 로그를 sim/v17/failures/ 에 보존.
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import sys
import tempfile
import traceback
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAIL = os.path.join(ROOT, "sim", "v17", "failures")


def _init(errdir):
    import run_match
    run_match.HARD_KILL = 3.0
    os.environ["LEAGUE_STDERR_DIR"] = errdir


def one(task):
    seed, a, b, team, mp, pool = task
    from run_league import play
    try:
        r = play((seed, os.path.join(ROOT, a), os.path.join(ROOT, b), team, mp))
    except Exception:
        r = {"error": traceback.format_exc()[-1500:]}
    errdir = os.environ.get("LEAGUE_STDERR_DIR", "")
    logs = glob.glob(os.path.join(errdir, f"{seed}_{team}_{os.getpid()}*.log")) if errdir else []
    try:
        if "error" in r or r.get("forfeit"):
            os.makedirs(FAIL, exist_ok=True)
            tag = f"{os.path.basename(a)}_vs_{os.path.basename(b)}_{seed}_{team}"
            with open(os.path.join(FAIL, "failures.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps({"task": task, "error": r.get("error"), "forfeit": r.get("forfeit"),
                                    "turns": r.get("turns")}, ensure_ascii=False) + "\n")
            for lg in logs:
                shutil.copy(lg, os.path.join(FAIL, tag + ("_opp" if lg.endswith("_opp.log") else "") + ".log"))
    except Exception:
        pass
    for lg in logs:
        try:
            os.remove(lg)
        except OSError:
            pass
    if "error" in r:
        return {"task": task, "error": r["error"][-300:]}
    ateam = team
    bteam = "K" if team == "Y" else "Y"
    ff = r.get("forfeit") or []

    def side(k):
        s = r[k]
        m = s.get("metrics") or {}
        ts = s.get("times") or []
        return {"occ": s["occ"], "sc": s["score"], "fsp": m.get("F_spawned", 0), "fal": m.get("F_alive", 0),
                "econ": m.get("home_eng_lost", 0) + m.get("home_hall_lost", 0),
                "t0": round(ts[0]) if ts else 0, "rt": round(max(ts[1:], default=0)), "rs": s.get("rstat") or {},
                "sd": sum(v for k, v in (m.get("death_ctx") or {}).items() if k.endswith("_stayed")),
                "p95": round(sorted(ts[1:])[int(0.95 * (len(ts) - 2))], 1) if len(ts) > 2 else 0,
                "ql": m.get("quick_lost", 0), "qld": m.get("quick_lost_depot", 0), "caps": m.get("captures", 0),
                "caps40": m.get("caps40", 0), "t5": m.get("t_own5", 161)}
    return {"a": a, "b": b, "pool": pool, "seed": seed, "team": team, "res": r["result"], "turns": r["turns"],
            "inst": bool(r.get("instant")), "ff_a": ateam in ff, "ff_b": bteam in ff, "A": side("main"), "B": side("opp")}


def main():
    tasks_path, out_path = sys.argv[1], sys.argv[2]
    jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 22
    with open(tasks_path, encoding="utf-8") as f:
        tasks = json.load(f)
    errdir = tempfile.mkdtemp(prefix="v17w_")
    try:
        with ProcessPoolExecutor(jobs, initializer=_init, initargs=(errdir,), max_tasks_per_child=100) as ex, \
                open(out_path, "w", encoding="utf-8") as out:
            for res in ex.map(one, [tuple(t) for t in tasks], chunksize=2):
                out.write(json.dumps(res, ensure_ascii=False, separators=(",", ":")) + "\n")
                out.flush()
    finally:
        shutil.rmtree(errdir, ignore_errors=True)


if __name__ == "__main__":
    main()
