"""v17 무인 진화 파이프라인 마스터 (v16f2 기반, 8시간 시간 분할).

python sim/v17_master.py [--hours 8] [--jobs 22] [--smoke]
  Phase A (0~2.5h)   단일 모듈 Ablation: A0(대조=v16f2 복제) + A1..A6 각각 vs v16f2
  Phase B (~6.0h)    Phase A 상위 모듈 조합 4~6개 vs v16f2 (+ v16f, pr_07 보조)
  Phase C (~7.75h)   결승 후보 vs 보스 4종(v16f2, v16f, pr_07, v12_1), 4대 지표 파레토
  Phase D (~8.0h)    v17_Champion/ + submission_v17.zip + sim/v17_overnight_final.md
안전: 배치(<= 1000경기)마다 워커 프로세스(sim/v17_worker.py)를 새로 띄우고 종료(메모리 회수),
      배치 벽시계 타임아웃 시 프로세스 트리 강제 종료 후 다음 배치 진행, 경기별 요약만 집계,
      집계 상태 sim/v17/state.json 체크포인트(재실행 시 이어서).
실제 맵은 결정적이므로 쌍마다 28맵 x 2진영 = 56경기 전수 1회, 표본 확대는 랜덤 맵.
"""
from __future__ import annotations

import argparse
import datetime as dt
import itertools
import json
import math
import os
import shutil
import subprocess
import sys
import time
import traceback
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.environ.get("V17_OUT") or os.path.join(ROOT, "sim", "v17")
BASE = "v17_base"
BASE_OV = {'ECON_FORTRESS': True, 'FORT_ALERT_DIST': 2, 'ROUTE_INTERCEPT': True, 'RI_STRICT': True, 'RI_CONF_DIST': 3,
           'ESCORT_SLOTS': 4, 'MAX_FLAGS': 8, 'BASE_FLAG_CAP': 5, 'ENDGAME_TURNS': 5, 'ESCORT_TRIGGER_ETA': 3,
           'MAX_INTERCEPT_W': 4, 'UTIL_SCORE_W': 1.5, 'EARLY_DEPOT_BONUS': 0.0, 'COORD_MODE': 'auction'}
MODS = {
    "A1": ("HOSPITAL_SPAWN", {"MOD_HOSP": True}),
    "A2": ("CONDITIONAL_TELE", {"MOD_TELE_COND": True}),
    "A3": ("CHOKE_AMBUSH", {"MOD_AMBUSH": True}),
    "A4": ("ENG_SURGE", {"MOD_SURGE": True}),
    "A5": ("GUILLOTINE", {"MOD_GUILLO": True}),
    "A6": ("MINOR_FLANK(1F)", {"MOD_FLANK": True}),
}
PTS = {"W": 1.0, "D": 0.5, "L": 0.0}
BOSS_DIR = {"v16f2": "v16f2", "v16f": "v16f", "pr_07": "bots/pr_07", "v12_1": "v12_1"}


def now():
    return dt.datetime.now()


def log(msg):
    line = f"[{now():%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    try:
        with open(os.path.join(OUT, "progress.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def wilson(p, n, z=1.96):
    if n <= 0:
        return 0.0, 1.0
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(max(0.0, p * (1 - p) / n + z * z / (4 * n * n))) / den
    return c - h, c + h


def real_maps():
    import glob
    files = sorted(glob.glob(os.path.join(ROOT, "replay", "replay*.json"))) + \
        sorted(glob.glob(os.path.join(ROOT, "replay", "r0928_*.json")))
    return ["replay:" + os.path.splitext(os.path.basename(f))[0] for f in files]


# ------------------------------------------------------------------ 봇 생성

def build_bot(name, mods):
    dst = os.path.join(ROOT, "bots", name)
    if os.path.exists(dst):
        shutil.rmtree(dst)
    os.makedirs(dst)
    src = os.path.join(ROOT, BASE)
    for f in os.listdir(src):
        if (f.endswith(".py") or f.endswith(".json")) and f != "persona_cfg.py":
            shutil.copy(os.path.join(src, f), os.path.join(dst, f))
    ov = dict(BASE_OV)
    for m in mods:
        ov.update(MODS[m][1])
    label = "+".join(MODS[m][0] for m in mods) or "대조군(v16f2 동일)"
    with open(os.path.join(dst, "persona_cfg.py"), "w", encoding="utf-8", newline="\n") as f:
        f.write(f'"""{name}: v16f2 + {label} (sim/v17_master.py 생성)."""\nOVERRIDES = {ov!r}\n')
    return "bots/" + name


# ------------------------------------------------------------------ 집계

class Agg:
    def __init__(self, d=None):
        self.d = d or {}

    def add(self, r):
        a, b = os.path.basename(r["a"]), os.path.basename(r["b"])
        k = f"{a}|{b}|{r['pool']}"
        c = self.d.setdefault(k, {"n": 0, "pts": 0.0, "W": 0, "D": 0, "L": 0, "occ_a": 0, "occ_b": 0, "fsp": 0, "fal": 0,
                                  "fsp_b": 0, "fal_b": 0, "econ": 0, "econ_b": 0, "ff_a": 0, "ff_b": 0, "inst": 0,
                                  "t0": 0, "rt": 0, "turns": 0, "rs": {}, "rs_n": 0, "void": 0})
        if r["ff_a"] or r["ff_b"]:   # 몰수 경기는 승률에서 제외(부하 스파이크 시 양쪽 모두 발생) — 별도 집계
            c["void"] = c.get("void", 0) + 1
            c["ff_a"] += int(r["ff_a"])
            c["ff_b"] += int(r["ff_b"])
            return
        c["n"] += 1
        c["pts"] += PTS[r["res"]]
        c[r["res"]] += 1
        A, B = r["A"], r["B"]
        c["occ_a"] += A["occ"]
        c["occ_b"] += B["occ"]
        c["fsp"] += A["fsp"]
        c["fal"] += A["fal"]
        c["fsp_b"] += B["fsp"]
        c["fal_b"] += B["fal"]
        c["econ"] += A["econ"]
        c["econ_b"] += B["econ"]
        c["inst"] += int(r["inst"] and r["res"] == "W")
        c["turns"] += r["turns"]
        c["t0"] = max(c["t0"], A["t0"])
        c["rt"] = max(c["rt"], A["rt"])
        if A["rs"]:
            c["rs_n"] += 1
            for kk, v in A["rs"].items():
                c["rs"][kk] = c["rs"].get(kk, 0) + v

    def get(self, a, b, pools=("real", "random")):
        o = {"n": 0, "pts": 0.0, "W": 0, "D": 0, "L": 0, "occ_a": 0, "occ_b": 0, "fsp": 0, "fal": 0, "fsp_b": 0,
             "fal_b": 0, "econ": 0, "econ_b": 0, "ff_a": 0, "ff_b": 0, "inst": 0, "t0": 0, "rt": 0, "turns": 0,
             "rs": {}, "rs_n": 0, "void": 0}
        for p in pools:
            c = self.d.get(f"{a}|{b}|{p}")
            if not c:
                continue
            for k in o:
                if k in ("t0", "rt"):
                    o[k] = max(o[k], c[k])
                elif k == "rs":
                    for kk, v in c["rs"].items():
                        o["rs"][kk] = o["rs"].get(kk, 0) + v
                else:
                    o[k] += c.get(k, 0)
        n = max(1, o["n"])
        o["win"] = o["pts"] / n if o["n"] else None
        o["ci"] = wilson(o["win"] or 0, o["n"])
        o["occ_share"] = o["occ_a"] / max(1, o["occ_a"] + o["occ_b"])
        o["f_surv"] = o["fal"] / max(1, o["fsp"])
        wt = o["rs"].get("w_turns", 0)
        o["w_eff"] = (o["rs"].get("w_moved", 0) / wt) if wt else None   # W 가동률(이동한 W-턴 / 보유 W-턴)
        return o

    def win2(self, a, b):
        """상대별 종합 = 0.5 x 실제 전수 + 0.5 x 랜덤 (한쪽만 있으면 그쪽)."""
        re_, ra = self.get(a, b, ("real",))["win"], self.get(a, b, ("random",))["win"]
        if re_ is None:
            return ra
        if ra is None:
            return re_
        return 0.5 * re_ + 0.5 * ra


# ------------------------------------------------------------------ 배치 실행 (워커 프로세스)

class Runner:
    def __init__(self, jobs, st, agg):
        self.jobs, self.st, self.agg = jobs, st, agg
        self.reals = real_maps()

    def kill_tree(self, p):
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True, timeout=60)
                # 부모가 먼저 죽어 트리에서 떨어진 풀 자식까지 정리
                subprocess.run(["powershell", "-NoProfile", "-Command",
                                f"Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                                f"Where-Object {{ $_.ParentProcessId -eq {p.pid} }} | "
                                f"ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}"],
                               capture_output=True, timeout=120)
            else:
                p.kill()
        except Exception:
            pass

    def run(self, games, label):
        """games: [(a_name, a_dir, b_name, b_dir, seed, pool)] -> 양 진영 2경기씩, 1000경기 단위 워커 배치."""
        tasks = []
        for a, ad, b, bd, seed, pool in games:
            mp = "random" if pool == "random" else self.reals[seed % len(self.reals)]
            for t in ("Y", "K"):
                tasks.append([seed, ad, bd, t, mp, pool])
        os.makedirs(os.path.join(OUT, "batches"), exist_ok=True)
        done = 0
        for k in range(0, len(tasks), 1000):
            chunk = tasks[k:k + 1000]
            bid = self.st["batch_id"] = self.st.get("batch_id", 0) + 1
            tp = os.path.join(OUT, "batches", f"b{bid:05d}.json")
            op = os.path.join(OUT, "batches", f"b{bid:05d}.jsonl")
            with open(tp, "w", encoding="utf-8") as f:
                json.dump(chunk, f)
            t0 = time.time()
            limit = max(900, len(chunk) * 1.5)
            p = subprocess.Popen([sys.executable, os.path.join(ROOT, "sim", "v17_worker.py"), tp, op, "--jobs", str(self.jobs)],
                                 cwd=ROOT, stdout=subprocess.DEVNULL, stderr=open(os.path.join(OUT, "worker_stderr.log"), "a"))
            try:
                p.wait(timeout=limit)
            except subprocess.TimeoutExpired:
                log(f"  batch {bid}: {limit:.0f}s 초과 -> 워커 트리 강제 종료")
                self.kill_tree(p)
                self.st["killed_batches"] = self.st.get("killed_batches", 0) + 1
            ok = err = 0
            try:
                with open(op, encoding="utf-8") as f:
                    for line in f:
                        try:
                            r = json.loads(line)
                        except Exception:
                            continue
                        if "error" in r:
                            err += 1
                            continue
                        self.agg.add(r)
                        ok += 1
                        if r["ff_a"] or r["ff_b"]:
                            self.st["forfeits"] = self.st.get("forfeits", 0) + 1
            except FileNotFoundError:
                pass
            self.st["games"] = self.st.get("games", 0) + ok
            self.st["errors"] = self.st.get("errors", 0) + err + (len(chunk) - ok - err)
            for pth in (tp, op):
                try:
                    os.remove(pth)
                except OSError:
                    pass
            done += ok
            log(f"  {label} batch {bid}: {ok}/{len(chunk)} ok, err {err}, {time.time() - t0:.0f}s "
                f"(누적 {self.st['games']}, 오류 {self.st['errors']}, 몰수 {self.st.get('forfeits', 0)})")
            save_state(self.st, self.agg)
        return done


def save_state(st, agg):
    st["agg"] = agg.d
    tmp = os.path.join(OUT, "state.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False)
    os.replace(tmp, os.path.join(OUT, "state.json"))


def pair_rounds(R, cands, opps, until, label, seeds_per_round, rbase, st, key):
    """cands x opps 쌍마다 실제 56 전수(1회) + 시간 한도까지 랜덤 시드 라운드 반복."""
    if not st.get(key + "_census"):
        g = [(c, cd, o, od, s, "real") for c, cd in cands for o, od, _ in opps for s in range(28)]
        log(f"{label}: 실제 맵 전수 {len(g) * 2}경기")
        R.run(g, label + "-real")
        st[key + "_census"] = True
    rnd = st.get(key + "_round", 0)
    while now() < until:
        g = []
        for c, cd in cands:
            for o, od, w in opps:
                n = max(1, int(seeds_per_round * w))
                g += [(c, cd, o, od, rbase + rnd * 1000 + i, "random") for i in range(n)]
        R.run(g, f"{label}-r{rnd}")
        rnd += 1
        st[key + "_round"] = rnd
    return rnd


# ------------------------------------------------------------------ 보고서 / 패키징

def pc(x):
    return "-" if x is None else f"{x:.1%}"


def row_vs(agg, a, b):
    g = agg.get(a, b)
    re_, ra = agg.get(a, b, ("real",)), agg.get(a, b, ("random",))
    lo, hi = g["ci"]
    return g, re_, ra, lo, hi


def package(name, mods):
    src = os.path.join(ROOT, "v16f2") if name == "v16f2" else os.path.join(ROOT, "bots", name)
    dst = os.path.join(ROOT, "v17_Champion")
    if os.path.exists(dst):
        shutil.rmtree(dst)
    os.makedirs(dst)
    files = sorted(f for f in os.listdir(src) if (f.endswith(".py") or f.endswith(".json"))
                   and os.path.isfile(os.path.join(src, f)))
    for f in files:
        shutil.copy(os.path.join(src, f), os.path.join(dst, f))
    zp = os.path.join(ROOT, "submission_v17.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(os.path.join(dst, f), arcname=f)
    with zipfile.ZipFile(zp) as z:
        names, bad = z.namelist(), z.testzip()
    return {"files": names, "size": os.path.getsize(zp), "ok": bad is None and "main.py" in names}


def mods_label(mods):
    return " + ".join(f"{m} {MODS[m][0]}" for m in mods) if mods else "(없음 = v16f2)"


def report(st, agg, t_start):
    L = ["# v17 무인 진화 파이프라인 최종 보고서 (v16f2 기반)\n"]
    L.append(f"- 기간 {t_start:%Y-%m-%d %H:%M} ~ {now():%Y-%m-%d %H:%M}, 유효 경기 {st.get('games', 0):,}, "
             f"오류 {st.get('errors', 0)}, 몰수 경기 {st.get('forfeits', 0)}, 강제 종료 배치 {st.get('killed_batches', 0)}")
    L.append("- 안전 구조: 배치(<=1000경기)마다 워커 프로세스 신규 기동·종료(메모리 회수), 풀 자식 100경기마다 교체, "
             "봇 응답 하드 킬 3s, 배치 벽시계 타임아웃 시 프로세스 트리 강제 종료, 경기별 요약만 집계, 실패 경기만 sim/v17/failures/ 보존")
    L.append("- 실제 맵은 결정적 -> 쌍마다 56경기 전수 1회, 표본 확대는 랜덤 맵. 상대별 종합 승률 = 0.5 x 실제 + 0.5 x 랜덤\n")
    ch = st.get("champion")
    L.append(f"## 최종 챔피언: **{ch['name'] if ch else '미정'}** — {mods_label(ch['mods']) if ch else ''}\n")
    if ch:
        L.append(f"- 선정 근거: {ch.get('why', '')}")
        pkg = st.get("package")
        if pkg:
            L.append(f"- 패키지: `v17_Champion/`, `submission_v17.zip` ({pkg['size']} B, {len(pkg['files'])} 파일, 검증 {'OK' if pkg['ok'] else 'FAIL'})")
        L.append("")
    # Phase C
    fin = st.get("finalists") or []
    if fin:
        L.append("## Phase C: 결승 — 보스 4종 스트레스 리그\n")
        L.append("| 후보 | 모듈 | 상대 | 경기 | 종합 승률 | 실제 56 | 랜덤 [95% CI] | 점령 몫 | F 생존율 | W 가동률 | 홈 경제 피탈/경기 | 몰수 | 첫 턴 max | 응답 max |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for f in fin:
            for o in BOSS_DIR:
                g, re_, ra, lo, hi = row_vs(agg, f["name"], o)
                if not g["n"]:
                    continue
                rlo, rhi = ra["ci"]
                L.append(f"| {f['name']} | {mods_label(f['mods'])} | {o} | {g['n']} | **{pc(agg.win2(f['name'], o))}** | {pc(re_['win'])} | "
                         f"{pc(ra['win'])} [{rlo:.1%}-{rhi:.1%}] | {g['occ_share']:.1%} | {g['f_surv']:.1%} | {pc(g['w_eff'])} | "
                         f"{g['econ'] / max(1, g['n']):.2f} | {g['ff_a']} | {g['t0']} | {g['rt']} |")
        par = st.get("pareto")
        if par:
            L.append("\n### 파레토 평가 (보스 4종 합산: 승률, 점령 몫, F 생존율, W 가동률)\n")
            L.append("| 후보 | 승률 | 점령 몫 | F 생존율 | W 가동률 | 비지배 |")
            L.append("|---|---|---|---|---|---|")
            for p in par:
                L.append(f"| {p['name']} | {pc(p['win'])} | {p['occ']:.1%} | {p['fs']:.1%} | {pc(p['weff'])} | {'O' if p['nd'] else 'X'} |")
        L.append("")
    # Phase B
    combos = st.get("combos") or []
    if combos:
        L.append("## Phase B: 상위 모듈 조합 토너먼트\n")
        L.append("| 조합 | 모듈 | vs v16f2 경기 | vs v16f2 종합 | 랜덤 [95% CI] | 실제 56 | vs v16f | vs pr_07 | 점령 몫 | F 생존율 | W 가동률 | 몰수 |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for cb in combos:
            n = cb["name"]
            g, re_, ra, lo, hi = row_vs(agg, n, "v16f2")
            rlo, rhi = ra["ci"]
            L.append(f"| {n} | {mods_label(cb['mods'])} | {g['n']} | **{pc(agg.win2(n, 'v16f2'))}** | {pc(ra['win'])} [{rlo:.1%}-{rhi:.1%}] | "
                     f"{pc(re_['win'])} | {pc(agg.win2(n, 'v16f'))} | {pc(agg.win2(n, 'pr_07'))} | {g['occ_share']:.1%} | "
                     f"{g['f_surv']:.1%} | {pc(g['w_eff'])} | {g['ff_a']} |")
        L.append("")
    # Phase A
    L.append("## Phase A: 단일 모듈 Ablation (각 변종 vs v16f2)\n")
    L.append(f"- 선발 결과: {st.get('selected_note', '-')}\n")
    L.append("| 변종 | 모듈 | 경기(무효) | 종합 승률 | 랜덤 [95% CI] | 실제 56 | 점령 몫 | F 생존율 (v16f2) | W 가동률 | 홈 경제 피탈/경기 | 즉시승 | 몰수 | 첫 턴 max | 응답 max | 발동 통계(경기당) |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for m in ["A0"] + list(MODS):
        n = f"v17_{m}"
        g, re_, ra, lo, hi = row_vs(agg, n, "v16f2")
        if not g["n"]:
            continue
        rlo, rhi = ra["ci"]
        keys = ("hosp_w", "hosp_home", "tele_w", "tele_skip", "ri_fire", "ri_w", "surge", "guillo_tgt", "flank_turns")
        rs = ", ".join(f"{k} {g['rs'].get(k, 0) / max(1, g['rs_n']):.1f}" for k in keys if g["rs"].get(k))
        L.append(f"| {n} | {MODS[m][0] if m in MODS else '대조군'} | {g['n']} ({g['void']}) | **{pc(agg.win2(n, 'v16f2'))}** | {pc(ra['win'])} [{rlo:.1%}-{rhi:.1%}] | "
                 f"{pc(re_['win'])} | {g['occ_share']:.1%} | {g['f_surv']:.1%} ({g['fal_b'] / max(1, g['fsp_b']):.1%}) | {pc(g['w_eff'])} | "
                 f"{g['econ'] / max(1, g['n']):.2f} | {g['inst']} | {g['ff_a']} | {g['t0']} | {g['rt']} | {rs or '-'} |")
    L.append("\n- W 가동률 = RSTAT w_moved / w_turns (보유 W-턴 중 실제 이동한 비율; 'W 전선 도달 효율' 대리 지표)")
    notes = st.get("notes") or []
    if notes:
        L.append("\n## 구현 메모\n")
        L += [f"- {x}" for x in notes]
    with open(os.path.join(ROOT, "sim", "v17_overnight_final.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=8.0)
    ap.add_argument("--jobs", type=int, default=22)
    ap.add_argument("--smoke", action="store_true")
    ns = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    try:
        with open(os.path.join(OUT, "state.json"), encoding="utf-8") as f:
            st = json.load(f)
        t_start = dt.datetime.fromisoformat(st["t_start"])
        log(f"resume (start {t_start})")
    except Exception:
        st = {"t_start": now().isoformat()}
        t_start = now()
    agg = Agg(st.get("agg"))
    H = ns.hours
    A_end = t_start + dt.timedelta(hours=H * 2.5 / 8)
    B_end = t_start + dt.timedelta(hours=H * 6.0 / 8)
    C_end = t_start + dt.timedelta(hours=H * 7.75 / 8)
    log(f"=== v17 start {t_start:%H:%M}, A~{A_end:%H:%M}, B~{B_end:%H:%M}, C~{C_end:%H:%M}, D~{t_start + dt.timedelta(hours=H):%H:%M} ===")
    st["notes"] = [
        "A1: v16f2 는 이미 소유 병원에서 생산(조건: 병원 칸 적 위협 0). A1 은 명세 안전 조건(적 F 거리·적 W ETA > 3)과 전선 = 공격 F 목표 기준으로 W 생산지를 고른다.",
        "A2: v16f2 는 W 순간이동을 필요 최소 수로 상시 사용. A2 는 목표 칸 결손(필요 W - 도착 예정 W) >= 3 일 때만 허용.",
        "A3: v16f2 의 엄격 길목 요격(W_ally >= W_enemy+1, 여유 W 한도)은 경제 건물(ENG/HALL/DEPOT)로 향하는 적 F 만 대상. A3 은 모든 비적 소유 건물로 확장.",
        "A4: v16f2 생산은 이미 '점령 예약 자원 차감 후 남는 예산 전부 W' 구조라 명세 그대로면 무변화. A4 는 공학관 보유 중 F 상한을 max(현재 F, 5)로 묶어 추가 F 대신 W 를 사는 형태로 구현.",
        "A5: 적 소유 ENG 중 (적 재점령 ETA - 우리 도착 ETA) >= 3 인 곳에 가점 6 (거리 6 이내).",
        "A6: F >= 4 일 때 F 1기(유지형 지정)에 적 진영 + 적 W ETA >= 4 건물 가점 6. 성능 입증(Phase A 하한 > 50%) 전엔 조합 금지.",
        "보스 경로: v16f2, v16f(제출 백업 해제본), pr_07(bots/pr_07), v12_1.",
    ]
    R = Runner(ns.jobs, st, agg)
    sp = 4 if ns.smoke else 100   # 라운드당 쌍별 랜덤 시드 수

    # ---------------- Phase A
    try:
        cands = st.get("A_cands")
        if not cands:
            cands = [["v17_A0", build_bot("v17_A0", [])]] + [[f"v17_{m}", build_bot(f"v17_{m}", [m])] for m in MODS]
            st["A_cands"] = cands
        if not st.get("A_done"):
            pair_rounds(R, cands, [("v16f2", "v16f2", 1.0)], A_end, "PhaseA", sp, 5_000_000, st, "A")
            st["A_done"] = True
            save_state(st, agg)
    except Exception:
        log("Phase A 오류:\n" + traceback.format_exc())
    # 선발
    try:
        if "selected" not in st:
            rows = []
            for m in MODS:
                n = f"v17_{m}"
                g = agg.get(n, "v16f2")
                ra = agg.get(n, "v16f2", ("random",))
                rows.append((m, agg.win2(n, "v16f2") or 0, ra["ci"][0], g["ff_a"]))
            rows.sort(key=lambda r: -r[1])
            prom = [m for m, w, lo, ff in rows if w > 0.5 and lo > 0.49 and ff == 0 and (m != "A6" or lo > 0.5)]
            sel = prom[:4]
            note = f"유의 모듈 {prom or '없음'}"
            if len(sel) < 3:
                fill = [m for m, w, lo, ff in rows if m not in sel and m != "A6" and ff == 0]
                sel += fill[:3 - len(sel)]
                note += f", 조합 탐색을 위해 승률 순 보충 -> {sel}"
            st["selected"] = sel
            st["selected_note"] = note + " | 승률순: " + ", ".join(f"{m} {w:.1%}(하한 {lo:.1%})" for m, w, lo, ff in rows)
            log("Phase A 선발: " + st["selected_note"])
            save_state(st, agg)
    except Exception:
        log("선발 오류:\n" + traceback.format_exc())
        st.setdefault("selected", ["A1", "A3", "A4"])

    # ---------------- Phase B
    try:
        if not st.get("combos"):
            sel = st["selected"]
            cs = [list(p) for p in itertools.combinations(sel[:3], 2)]
            if len(sel) >= 3:
                cs.append(sel[:3])
            if len(sel) >= 4:
                cs += [[sel[0], sel[3]], sel[:4]]
            cs = cs[:6]
            if len(cs) < 4:
                cs.append([sel[0]])
            combos = []
            for i, mods in enumerate(cs, 1):
                name = f"v17_B{i}"
                combos.append({"name": name, "dir": build_bot(name, mods), "mods": mods})
            combos.append({"name": f"v17_{sel[0]}", "dir": f"bots/v17_{sel[0]}", "mods": [sel[0]]})   # 최고 단일 모듈도 동행
            st["combos"] = combos
            save_state(st, agg)
        if not st.get("B_done"):
            cands = [[c["name"], c["dir"]] for c in st["combos"]]
            opps = [("v16f2", "v16f2", 1.0), ("v16f", "v16f", 0.25), ("pr_07", "bots/pr_07", 0.25)]
            pair_rounds(R, cands, opps, B_end, "PhaseB", sp, 6_000_000, st, "B")
            st["B_done"] = True
            save_state(st, agg)
    except Exception:
        log("Phase B 오류:\n" + traceback.format_exc())

    # ---------------- Phase C
    try:
        if not st.get("finalists"):
            pool = []
            for c in st.get("combos") or []:
                ra = agg.get(c["name"], "v16f2", ("random",))
                pool.append((agg.win2(c["name"], "v16f2") or 0, ra["ci"][0], c))
            pool.sort(key=lambda x: (-x[0]))
            st["finalists"] = [x[2] for x in pool[:2]]
            log("Phase C 결승: " + ", ".join(f"{x[2]['name']} {x[0]:.1%}" for x in pool[:2]))
            save_state(st, agg)
        if not st.get("C_done"):
            cands = [[f["name"], f["dir"]] for f in st["finalists"]]
            opps = [(o, d, 1.0 if o == "v16f2" else 0.5) for o, d in BOSS_DIR.items()]
            pair_rounds(R, cands, opps, C_end, "PhaseC", sp, 7_000_000, st, "C")
            st["C_done"] = True
            save_state(st, agg)
    except Exception:
        log("Phase C 오류:\n" + traceback.format_exc())

    # ---------------- Phase D: 파레토 + 챔피언
    try:
        par = []
        for f in st.get("finalists") or []:
            n = f["name"]
            tot = {"pts": 0.0, "n": 0, "occ_a": 0, "occ_b": 0, "fal": 0, "fsp": 0, "wm": 0, "wt": 0}
            for o in BOSS_DIR:
                g = agg.get(n, o)
                tot["pts"] += g["pts"]
                tot["n"] += g["n"]
                tot["occ_a"] += g["occ_a"]
                tot["occ_b"] += g["occ_b"]
                tot["fal"] += g["fal"]
                tot["fsp"] += g["fsp"]
                tot["wm"] += g["rs"].get("w_moved", 0)
                tot["wt"] += g["rs"].get("w_turns", 0)
            par.append({"name": n, "mods": f["mods"], "win": tot["pts"] / max(1, tot["n"]),
                        "occ": tot["occ_a"] / max(1, tot["occ_a"] + tot["occ_b"]), "fs": tot["fal"] / max(1, tot["fsp"]),
                        "weff": tot["wm"] / tot["wt"] if tot["wt"] else None,
                        "vs_f2": agg.win2(n, "v16f2") or 0, "lo_f2": agg.get(n, "v16f2", ("random",))["ci"][0]})
        for p in par:
            p["nd"] = not any(all((q[k] or 0) >= (p[k] or 0) for k in ("win", "occ", "fs", "weff"))
                              and any((q[k] or 0) > (p[k] or 0) for k in ("win", "occ", "fs", "weff")) for q in par if q is not p)
        st["pareto"] = par
        ok = [p for p in par if p["nd"] and p["vs_f2"] > 0.5 and p["lo_f2"] > 0.5]
        if ok:
            best = max(ok, key=lambda p: (p["vs_f2"], p["win"]))
            st["champion"] = {"name": best["name"], "mods": best["mods"],
                              "why": f"v16f2 상대 종합 {best['vs_f2']:.1%} (랜덤 95% 하한 {best['lo_f2']:.1%} > 50%), 보스 4종 파레토 비지배"}
        else:
            st["champion"] = {"name": "v16f2", "mods": [],
                              "why": "v16f2 를 통계적으로 넘는(랜덤 95% 하한 > 50%) 파레토 비지배 후보 없음 -> v16f2 유지(v17 = v16f2)"}
        log(f"champion: {st['champion']}")
        st["package"] = package(st["champion"]["name"], st["champion"]["mods"])
        log(f"package: {st['package']}")
    except Exception:
        log("Phase D 오류:\n" + traceback.format_exc())
    save_state(st, agg)
    try:
        report(st, agg, t_start)
        log("report: sim/v17_overnight_final.md")
    except Exception:
        log("report 오류:\n" + traceback.format_exc())
    with open(os.path.join(OUT, "DONE"), "w") as f:
        f.write(f"{now()} champion={st.get('champion')}\n")
    log("=== v17 done ===")


if __name__ == "__main__":
    main()
