"""봇 대전 러너. 각 봇을 별도 프로세스로 띄워 표준 입출력 프로토콜로 구동한다.

사용: python sim/run_match.py BOT_A_DIR BOT_B_DIR --seeds 0-9 [--jobs 6]
각 시드마다 진영을 바꿔 2경기(A=Y, A=K)를 치른다.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Game, TOTAL_TURNS, TEAMS  # noqa: E402

TIMEOUT_FIRST = 3.0
TIMEOUT = 0.3
HARD_KILL = 5.0


class Bot:
    def __init__(self, path, stderr_path=None):
        self.t_spawn = time.perf_counter()
        self._err = open(stderr_path, "w", encoding="utf-8") if stderr_path else None
        self.p = subprocess.Popen([sys.executable, "-u", "main.py"], cwd=path,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=self._err or subprocess.DEVNULL, text=True, bufsize=1,
                                  encoding="utf-8")
        self.times = []
        self.timeouts = 0
        self.dead = False

    def send(self, text):
        if self.dead:
            return
        try:
            self.p.stdin.write(text)
            self.p.stdin.flush()
        except (BrokenPipeError, OSError):
            self.dead = True

    def begin(self, text, from_spawn=False):
        """입력 전송 후 응답 수집을 시작한다(비동기). from_spawn=True 면 첫 턴: 기동 시점부터 측정."""
        self._out = []
        self._done = threading.Event()
        if self.dead:
            self._done.set()
            return
        out, done = self._out, self._done

        def reader():
            try:
                for line in self.p.stdout:
                    line = line.rstrip("\n")
                    if line == "END":
                        break
                    out.append(line)
            except Exception:
                pass
            self._t_end = time.perf_counter()
            done.set()

        self._t0 = self.t_spawn if from_spawn else time.perf_counter()
        self._t_end = None
        self.send(text)
        threading.Thread(target=reader, daemon=True).start()

    def finish(self, limit):
        if self.dead:
            return []
        if not self._done.wait(HARD_KILL):
            self.dead = True
            return []
        dt = (self._t_end or time.perf_counter()) - self._t0
        self.times.append(dt * 1000)
        if dt > limit:
            self.timeouts += 1
            return []
        return self._out

    def ask(self, text, limit):
        if self.dead:
            return []
        out = []
        done = threading.Event()

        def reader():
            try:
                for line in self.p.stdout:
                    line = line.rstrip("\n")
                    if line == "END":
                        break
                    out.append(line)
            except Exception:
                pass
            done.set()

        t0 = time.perf_counter()
        self.send(text)
        th = threading.Thread(target=reader, daemon=True)
        th.start()
        if not done.wait(HARD_KILL):
            self.dead = True
            return []
        dt = time.perf_counter() - t0
        self.times.append(dt * 1000)
        if dt > limit:
            self.timeouts += 1
            return []   # 시간 초과 턴은 명령 무효 처리
        return out

    def close(self):
        try:
            self.p.stdin.close()
        except Exception:
            pass
        try:
            self.p.wait(timeout=2)
        except Exception:
            self.p.kill()
        if self._err:
            self._err.close()


def play(args):
    seed, a_dir, b_dir, a_team = args
    g = Game(seed)
    dirs = {a_team: a_dir, ("K" if a_team == "Y" else "Y"): b_dir}
    bots = {t: Bot(dirs[t]) for t in TEAMS}
    for t in TEAMS:
        bots[t].send(g.init_text(t))
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
    b_team = "K" if a_team == "Y" else "Y"
    res = {"seed": seed, "a_team": a_team, "turns": g.turn, "forfeit": forfeit, "instant": g.instant,
           "winner": "A" if win == a_team else ("B" if win == b_team else "D"),
           "a": {"score": (sy if a_team == "Y" else sk)[0], "occ": (sy if a_team == "Y" else sk)[1],
                 "stats": g.stats[a_team], "times": bots[a_team].times, "timeouts": bots[a_team].timeouts},
           "b": {"score": (sk if a_team == "Y" else sy)[0], "occ": (sk if a_team == "Y" else sy)[1],
                 "stats": g.stats[b_team], "times": bots[b_team].times, "timeouts": bots[b_team].timeouts}}
    return res


def pct(xs, p):
    if not xs:
        return 0.0
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p / 100 * len(xs)))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--seeds", default="0-9")
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--json", default=None)
    ns = ap.parse_args()
    lo, hi = map(int, ns.seeds.split("-"))
    tasks = [(s, os.path.abspath(ns.a), os.path.abspath(ns.b), t) for s in range(lo, hi + 1) for t in TEAMS]
    with ProcessPoolExecutor(ns.jobs) as ex:
        results = list(ex.map(play, tasks))
    w = sum(r["winner"] == "A" for r in results)
    l = sum(r["winner"] == "B" for r in results)
    d = len(results) - w - l
    name_a, name_b = os.path.basename(ns.a.rstrip("/\\")), os.path.basename(ns.b.rstrip("/\\"))
    print(f"== {name_a} vs {name_b}: {w}W {l}L {d}D  ({len(results)} games, winrate {w / len(results) * 100:.1f}%)")
    for side in ("a", "b"):
        nm = name_a if side == "a" else name_b
        fs = sum(r[side]["stats"]["F_spawned"] for r in results)
        fk = sum(r[side]["stats"]["F_killed"] for r in results)
        times = [t for r in results for t in r[side]["times"][1:]]
        first = [r[side]["times"][0] for r in results if r[side]["times"]]
        print(f"  {nm:>6}: avg score {sum(r[side]['score'] for r in results) / len(results):5.2f}  "
              f"avg occ {sum(r[side]['occ'] for r in results) / len(results):7.1f}  "
              f"F survival {100 * (1 - fk / max(1, fs)):5.1f}% ({fk}/{fs} died)  "
              f"captures {sum(r[side]['stats']['captures'] for r in results) / len(results):5.1f}  "
              f"kill-neutralize {sum(r[side]['stats']['neutralized_by_kill'] for r in results) / len(results):4.1f}  "
              f"bad_cmds {sum(r[side]['stats']['bad_cmds'] for r in results)}")
        print(f"          time ms p50 {pct(times, 50):.1f}  p95 {pct(times, 95):.1f}  max {max(times, default=0):.1f}  "
              f"first-turn max {max(first, default=0):.0f}  timeouts {sum(r[side]['timeouts'] for r in results)}")
    for r in results:
        print(f"  seed {r['seed']:3d} A={r['a_team']} -> {r['winner']}  score {r['a']['score']}:{r['b']['score']}  "
              f"occ {r['a']['occ']}:{r['b']['occ']}  T{r['turns']}"
              f"{'  FORFEIT ' + str(r['forfeit']) if r['forfeit'] else ''}{'  INSTANT' if r['instant'] else ''}")
    if ns.json:
        with open(ns.json, "w") as f:
            json.dump(results, f)


if __name__ == "__main__":
    main()
