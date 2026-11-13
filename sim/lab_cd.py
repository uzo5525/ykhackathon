"""연구실 좌표 하강(coordinate descent) — 호출 1회 = 라운드 1회.

python sim/lab_cd.py            # 다음 라운드 실행(상태: sim/lab/cd_state.json)
python sim/lab_cd.py --round 3  # 특정 라운드
  라운드마다 SCHEDULE[r] 의 (파라미터, 값) 변종을 현재 챔피언 위에 만들고 챔피언과 1,056경기(실제 56 + 랜덤 500)씩 스크리닝.
  최고 변종이 승률 >= 53% 이고 95% 하한 > 50% 면 새 시드 2,000경기 확정전. 확정전 하한 > 50% 면 챔피언 승격:
  v{N+1}/ 폴더 + submission_v{N+1}.zip, 저널(sim/lab/journal.md) 기록. 모든 단계 예외는 기록 후 계속.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
import traceback
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v17_master as M  # noqa: E402
from lab_build import build  # noqa: E402

ROOT = M.ROOT
M.OUT = os.path.join(ROOT, "sim", "lab")
STATE = os.path.join(ROOT, "sim", "lab", "cd_state.json")
JOURNAL = os.path.join(ROOT, "sim", "lab", "journal.md")

SCHEDULE = [
    [("ESCORT_SLOTS", 3), ("ESCORT_SLOTS", 5), ("ESCORT_TRIGGER_ETA", 2), ("ESCORT_TRIGGER_ETA", 4),
     ("UTIL_SCORE_W", 1.3), ("UTIL_SCORE_W", 1.7), ("ENDGAME_TURNS", 0), ("ENDGAME_TURNS", 15),
     ("HOME_ECON_RETAKE", True)],
    [("ESCORT_SLOTS", 5), ("ESCORT_SLOTS", 6), ("MAX_INTERCEPT_W", 2), ("MAX_INTERCEPT_W", 6), ("HYST_F", 1.0), ("HYST_F", 3.0),
     ("HYST_F_AGE", 1), ("HYST_F_AGE", 3), ("TAU", 0.5), ("TAU", 2.0)],
    [("MAX_INTERCEPT_W", 6), ("MAX_INTERCEPT_W", 8), ("ESCORT_SLOTS", 7), ("ESCORT_SLOTS", 8),
     ("R_ENTER", 1.2), ("R_ENTER", 2.0), ("BONUS_CONTEST", 0.0), ("BONUS_CONTEST", 6.0),
     ("PENALTY_THREAT", 0.5), ("PENALTY_THREAT", 2.0), ("RISK_ACCEPT", 3.0), ("RISK_ACCEPT", 10.0)],
    [("BONUS_CONTEST", 0.0), ("ESCORT_SLOTS", 7), ("MAX_INTERCEPT_W", 10), ("RISK_ACCEPT", 10.0),
     ("IDLE_RESOURCE", 10), ("IDLE_RESOURCE", 20), ("COVER_H_BONUS", 2), ("COVER_H_BONUS", 6),
     ("BONUS_DEPOT", 5.0), ("BONUS_DEPOT", 15.0), ("BONUS_PLAZA", 2.0), ("BONUS_PLAZA", 8.0)],
    [("combo3", {"RISK_ACCEPT": 10.0, "BONUS_PLAZA": 2.0, "BONUS_CONTEST": 0.0}), ("ESCORT_SLOTS", 8),
     ("RISK_ACCEPT", 10.0), ("BONUS_CONTEST", 0.0),
     ("SWEEPER_MIN_FLAGS", 3), ("ENDGAME_FLAG_CAP", 8), ("H_MAX", 8), ("H_MAX", 16),
     ("BONUS_RETAKE", 0.0), ("BONUS_RETAKE", 6.0), ("PENALTY_ENEMY_FLAG", 0.0), ("PENALTY_ENEMY_FLAG", 6.0)],
    [("GUILLO_BONUS", 3.0), ("GUILLO_BONUS", 10.0), ("TELE_DEFICIT_MIN", 2), ("TELE_DEFICIT_MIN", 4),
     ("FORT_ALERT_DIST", 3), ("ECON_ALERT_DIST", 2), ("ECON_ALERT_DIST", 6), ("HOME_ECON_SLOT_BONUS", 4.0)],
    [("fcap9", {"BASE_FLAG_CAP": 8, "MAX_FLAGS": 9}), ("BASE_FLAG_CAP", 8), ("combo_rp", {"RISK_ACCEPT": 10.0, "BONUS_PLAZA": 2.0}),
     ("ESCORT_RADIUS", 3), ("ESCORT_RADIUS", 1), ("RI_CONF_DIST", 4), ("RI_CONF_DIST", 2),
     ("RI_MAX_ETA", 6), ("RI_MAX_ETA", 10), ("RI_HOLD", 1), ("RI_HOLD", 3), ("ESCORT_TRIGGER_ETA", 99)],
    # --- 2차 패스: 구조 / 수비 배분 / 핵심 재스윕 (새 체제: F 8기, 호위 7, 인터셉트 8)
    [("OPENING_ENABLED", False), ("OPENING_SOFT_TURNS", 3), ("OPENING_SOFT_TURNS", 8), ("SNIPE_ENABLED", False),
     ("UTIL_DIST_POW", 0.7), ("UTIL_DIST_POW", 1.3), ("CENTER_DEFENSE_MIN", 1), ("CENTER_DEFENSE_MIN", 3)],
    [("DEFEND_ALERT_DIST", 1), ("DEFEND_ALERT_DIST", 3), ("DEFEND_PULL_DIST", 3), ("DEFEND_PULL_DIST", 6),
     ("SPECIAL_SQUAD", 1), ("SPECIAL_SQUAD", 4), ("HOME_ALERT_DIST", 3), ("HOME_ALERT_DIST", 5),
     ("REQUIRED_HOME_DEFENSE", 0), ("REQUIRED_HOME_DEFENSE", 2)],
    [("UTIL_SCORE_W", 1.3), ("UTIL_SCORE_W", 1.7), ("HYST_F", 1.0), ("HYST_F", 3.0), ("TAU", 0.5), ("TAU", 2.0),
     ("PENALTY_THREAT", 0.7), ("PENALTY_THREAT", 1.5), ("ECON_ALERT_DIST", 6), ("RI_HOLD", 3), ("UTIL_DIST_POW", 0.7), ("UTIL_DIST_POW", 1.3)],
    # --- 3차 패스: 52~54% 신호 재검증 + 승격 파라미터 미세 조정
    [("H_MAX", 16), ("DEFEND_PULL_DIST", 3), ("BONUS_RETAKE", 0.0), ("TELE_DEFICIT_MIN", 2), ("GUILLO_BONUS", 3.0),
     ("sig_combo", {"H_MAX": 16, "DEFEND_PULL_DIST": 3, "BONUS_RETAKE": 0.0}), ("fcap9b", {"BASE_FLAG_CAP": 8, "MAX_FLAGS": 9})],
    [("ESCORT_SLOTS", 8), ("ESCORT_SLOTS", 6), ("MAX_INTERCEPT_W", 7), ("MAX_INTERCEPT_W", 10), ("RISK_ACCEPT", 8.0),
     ("RISK_ACCEPT", 14.0), ("BONUS_PLAZA", 0.0), ("BONUS_PLAZA", 3.0), ("BONUS_DEPOT", 7.0), ("BONUS_HALL", 3.0), ("BONUS_HALL", 8.0)],
    # --- 4차: 호위 10 체제 재점검
    [("ESCORT_RADIUS", 3), ("ESCORT_TRIGGER_ETA", 4), ("ESCORT_TRIGGER_ETA", 2), ("MAX_FLAGS", 10),
     ("MAX_INTERCEPT_W", 10), ("RISK_ACCEPT", 14.0), ("H_MAX", 16), ("GUILLO_BONUS", 3.0), ("HYST_F", 1.0), ("UTIL_SCORE_W", 1.7)],
    [("HYST_F", 1.0), ("MAX_INTERCEPT_W", 12), ("MAX_INTERCEPT_W", 14), ("ESCORT_SLOTS", 9), ("ESCORT_SLOTS", 11),
     ("RI_HOLD", 3), ("RI_CONF_DIST", 4), ("HYST_F_AGE", 1), ("combo_h", {"HYST_F": 1.0, "HYST_F_AGE": 1})],
    # --- 5차: 미탐색 파라미터
    [("STUCK_LIMIT", 1), ("STUCK_LIMIT", 3), ("BAN_TURNS", 3), ("BAN_TURNS", 10), ("TRAP_AVOID", False),
     ("DB_THRESHOLD", 12), ("DB_THRESHOLD", 30), ("LOAD_WEIGHT", 1), ("LOAD_WEIGHT", 5), ("SWEEPER_STICKY", 1.0),
     ("ENEMY_SPAWN_CAP", 3), ("ENEMY_SPAWN_CAP", 9)],
    # --- 6차: 과거 기각 모듈 새 체제 재검증
    [("MOD_HOSP", True), ("MOD_AMBUSH", True), ("MOD_ANCHOR", True), ("MOD_FLANK", True), ("MOD_CHECKMATE", True),
     ("MOD_DINT", True), ("MOD_META", True), ("MOD_GARRISON", True), ("HOME_ECON_RETAKE", True), ("MOD_ESCAPE", True)],
    # --- 7차: v32 체제 핵심 축 재점검
    [("ESCORT_SLOTS", 9), ("ESCORT_SLOTS", 11), ("MAX_INTERCEPT_W", 12), ("MAX_INTERCEPT_W", 16), ("GARRISON_W", 2),
     ("fcap10", {"BASE_FLAG_CAP": 9, "MAX_FLAGS": 10}), ("MAX_FLAGS", 8), ("DB_THRESHOLD", 8), ("DB_THRESHOLD", 16),
     ("C7", {"H_MAX": 16, "GUILLO_BONUS": 3.0, "RISK_ACCEPT": 14.0})],
    # --- 8차 (v32 기준, 풀 관문 적용)
    [("C7", {"H_MAX": 16, "GUILLO_BONUS": 3.0, "RISK_ACCEPT": 14.0}), ("RISK_ACCEPT", 12.0), ("STUCK_LIMIT", 3),
     ("ESCORT_SLOTS", 9), ("RI_HOLD", 3), ("BONUS_PLAZA", 1.0), ("COVER_H_BONUS", 6), ("PENALTY_THREAT", 1.5)],
    # --- 18차 (10/01, 성채 E2 구조 변경 후 재조정)
    [("ESCORT_SLOTS", 8), ("ESCORT_SLOTS", 12), ("MAX_INTERCEPT_W", 10), ("MAX_INTERCEPT_W", 18),
     ("BASE_FLAG_CAP", 7), ("fcap10", {"BASE_FLAG_CAP": 9, "MAX_FLAGS": 10}), ("GARRISON_W", 2), ("GARRISON_PULL", 5),
     ("FORT_ALERT_DIST", 4), ("FORT_PULL_DIST", 6)],
    # --- 19~20차 (미탐색 축)
    [("ENG_BONUS", 3.0), ("ENG_BONUS", 10.0), ("EOV_W", 3.0), ("EOV_W", 9.0), ("FLAG_ESCORT_W_MIN", 2),
     ("FLAG_ESCORT_W_MIN", 5), ("PENALTY_RESERVED", 15.0), ("COORD_AUCTION_K", 4.0), ("COORD_AUCTION_K", 16.0),
     ("ECON_PULL_DIST", 8)],
    [("MACRO_BONUS", 0.0), ("MACRO_BONUS", 3.0), ("EARLY_CENTER_BONUS", 0.0), ("EARLY_CENTER_BONUS", 5.0),
     ("DB_F_PENALTY", 3.0), ("DB_F_PENALTY", 10.0), ("DEPOT_CONTESTED_FACTOR", 0.7), ("SNIPE_VALUE", 20.0),
     ("W_GOAL_BAN", 3), ("NO_ESCORT_TURNS", 6)],
    # --- 21차 (v37, 약한 신호 결합 + 미사용 모듈)
    [("wk3", {"GARRISON_PULL": 5, "ESCORT_SLOTS": 12, "ENG_BONUS": 10.0}), ("wk2", {"GARRISON_PULL": 5, "ESCORT_SLOTS": 12}),
     ("GARRISON_PULL", 5), ("FORT_FLAG_HOLD", True), ("SCOUT_EVAC", True), ("GAR_E2", 3), ("GAR_E2", 0),
     ("ftlib", {"FORT_TYPES": ("HALL", "ENG", "LIBRARY")}), ("ENG_BONUS", 8.0), ("FORT_E2_R", 2)],
    # --- 22차 (v38)
    [("FORT_FLAG_HOLD", True), ("fhse", {"FORT_FLAG_HOLD": True, "SCOUT_EVAC": True}), ("ESCORT_SLOTS", 14),
     ("GARRISON_PULL", 7), ("ENG_BONUS", 14.0), ("MAX_INTERCEPT_W", 12), ("FORT_E2_R", 4), ("GAR_E2", 0)],
    # --- 23차 (v38, 마무리)
    [("ENG_BONUS", 14.0), ("GARRISON_W", 2), ("RISK_ACCEPT", 12.0), ("BONUS_RETAKE", 6.0), ("FORT_ALERT_DIST", 2),
     ("fh_eng", {"FORT_FLAG_HOLD": True, "ENG_BONUS": 14.0})],
    # --- 24차 (v39, 확장 사냥 이후 재조정)
    [("HUNT_MARGIN", 3), ("ESCORT_SLOTS", 10), ("ESCORT_SLOTS", 14), ("MAX_INTERCEPT_W", 10), ("GARRISON_PULL", 4),
     ("ESCORT_TRIGGER_ETA", 4), ("ESCORT_RADIUS", 3), ("fcap10", {"BASE_FLAG_CAP": 9, "MAX_FLAGS": 10}),
     ("RISK_ACCEPT", 8.0), ("BASE_FLAG_CAP", 7)],
    # --- 25차 (v41, 과거 모듈 재검증: 구조가 바뀌어 상성이 달라졌을 수 있음)
    [("MOD_HOSP", True), ("MOD_AMBUSH", True), ("MOD_FLANK", True), ("MOD_CHECKMATE", True), ("MOD_SURGE", True),
     ("INTERCEPT_ENABLED", True), ("SURPLUS_PUSH", True), ("MOD_ANCHOR", True), ("HOME_ECON_RETAKE", True),
     ("MOD_TRADE", True)],
    # --- 26차 (v41+, 재조정)
    [("FORT_PULL_DIST", 5), ("GAR_E2", 1), ("ESCORT_SLOTS", 11), ("MAX_INTERCEPT_W", 12), ("H_MAX", 16),
     ("TAU", 0.7), ("UTIL_SCORE_W", 1.7), ("HYST_F", 1.5), ("DB_THRESHOLD", 14), ("PENALTY_THREAT", 0.5)],
    # --- 27차 (v42 SURGE 이후 F/W 비율 재조정)
    [("BASE_FLAG_CAP", 6), ("BASE_FLAG_CAP", 8), ("MAX_FLAGS", 8), ("MAX_FLAGS", 10), ("fc68", {"BASE_FLAG_CAP": 6, "MAX_FLAGS": 8}),
     ("IDLE_RESOURCE", 10), ("IDLE_RESOURCE", 20), ("FLAG_ESCORT_W_MIN", 4), ("MOD_TRADE", True), ("MOD_ANCHOR", True)],
]


def log_j(text):
    try:
        with open(JOURNAL, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except Exception:
        pass


def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"champion": "v20", "version": 20, "round": 0, "history": []}


def save_state(s):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)


def path(n):
    return n if os.path.isdir(os.path.join(ROOT, n)) and not n.startswith("cd_") else f"bots/{n}"


def screen(cands, champ, rand, rbase, tag, real=True):
    st = {}
    R = M.Runner(22, st, M.Agg())
    games = []
    for c in cands:
        if real:
            games += [(c, path(c), champ, path(champ), s, "real") for s in range(28)]
        games += [(c, path(c), champ, path(champ), rbase + s, "random") for s in range(rand)]
    R.run(games, tag)
    out = {}
    for c in cands:
        g = R.agg.get(c, champ)
        out[c] = {"win": g["win"] or 0.0, "n": g["n"], "lo": g["ci"][0], "hi": g["ci"][1],
                  "fd": (g["fsp"] - g["fal"]) / max(1, g["n"]), "fd_opp": (g["fsp_b"] - g["fal_b"]) / max(1, g["n"])}
    return out, st


def promote(s, cand, desc, conf):
    ver = s["version"] + 1
    name = f"v{ver}"
    dst = os.path.join(ROOT, name)
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(os.path.join(ROOT, "bots", cand), dst, ignore=shutil.ignore_patterns("__pycache__"))
    files = sorted(f for f in os.listdir(dst) if (f.endswith(".py") or f.endswith(".json")) and os.path.isfile(os.path.join(dst, f)))
    zp = os.path.join(ROOT, f"submission_{name}.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(os.path.join(dst, f), arcname=f)
    with zipfile.ZipFile(zp) as z:
        ok = z.testzip() is None and len(z.namelist()) == 9
    s["history"].append({"version": ver, "from": s["champion"], "change": desc, "confirm": conf, "zip_ok": ok,
                         "time": dt.datetime.now().isoformat(timespec="minutes")})
    s["champion"], s["version"] = name, ver
    log_j(f"- ★ 승격: **{name}** = {s['history'][-1]['from']} + {desc} (확정전 {conf['win']:.1%} [{conf['lo']:.1%}-{conf['hi']:.1%}], "
          f"n={conf['n']}) -> submission_{name}.zip {'OK' if ok else 'ZIP 오류'}")


POOL = ["v17_B1", "v19", "v26", "sb_econ2_b7", "hy2", "sb_hosprush", "v16f2", "friend_h_r4", "friend_v17c"]


def pool_gate(cand, champ, r):
    """외부 풀 회귀 관문: 후보·챔피언을 같은 시드로 풀 7상대 각 250경기. 후보 평균이 챔피언 평균 - 1%p 이상이어야 통과."""
    st = {}
    R = M.Runner(22, st, M.Agg())
    games = []
    for who in (cand, champ):
        for o in POOL:
            games += [(who, path(who), o, path(o), s_, "real") for s_ in range(28)]
            games += [(who, path(who), o, path(o), 60_000_000 + r * 1000 + s_, "random") for s_ in range(97)]
    R.run(games, f"cd{r}pool")
    avg = {}
    for who in (cand, champ):
        ws = [R.agg.get(who, o)["win"] or 0.0 for o in POOL]
        avg[who] = sum(ws) / len(ws)
    ok = avg[cand] >= avg[champ] - 0.01
    log_j(f"- 풀 관문: {cand} 평균 {avg[cand]:.1%} vs 챔피언 {avg[champ]:.1%} -> {'통과' if ok else '탈락(외부 회귀)'}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, default=None)
    ns = ap.parse_args()
    s = load_state()
    r = ns.round if ns.round is not None else s["round"]
    if r >= len(SCHEDULE):
        print("schedule done")
        return
    champ = s["champion"]
    t0 = dt.datetime.now()
    try:
        cands, desc = [], {}
        for i, (k, v) in enumerate(SCHEDULE[r]):
            if isinstance(v, dict):
                nm = f"cd{r:02d}_{i}_{k.lower()}"
                build(nm, champ, v, f"{k}: {v}", parent=champ)
                desc[nm] = f"{k} {v}"
            else:
                nm = f"cd{r:02d}_{i}_{k.lower()}_{str(v).replace('.', 'p')}"
                build(nm, champ, {k: v}, f"{k}={v}", parent=champ)
                desc[nm] = f"{k}={v}"
            cands.append(nm)
        res, st = screen(cands, champ, 500, 30_000_000 + r * 100_000, f"cd{r}")
        lines = [f"\n### 좌표 하강 라운드 {r} (챔피언 {champ}, {t0:%H:%M}~{dt.datetime.now():%H:%M}, 각 {res[cands[0]]['n']}경기)",
                 "| 변경 | 승률 [95% CI] | F 사망 (나/챔피언) |", "|---|---|---|"]
        for c in sorted(cands, key=lambda c: -res[c]["win"]):
            x = res[c]
            lines.append(f"| {desc[c]} | {x['win']:.1%} [{x['lo']:.1%}-{x['hi']:.1%}] | {x['fd']:.2f} / {x['fd_opp']:.2f} |")
        log_j("\n".join(lines))
        best = max(cands, key=lambda c: res[c]["win"])
        if res[best]["win"] >= 0.53 and res[best]["lo"] > 0.5:
            conf, _ = screen([best], champ, 1000, 31_000_000 + r * 100_000, f"cd{r}c", real=False)
            c = conf[best]
            log_j(f"- 확정전 {desc[best]}: {c['win']:.1%} [{c['lo']:.1%}-{c['hi']:.1%}] n={c['n']}")
            if c["lo"] > 0.5 and pool_gate(best, champ, r):
                promote(s, best, desc[best], c)
            elif c["lo"] <= 0.5:
                log_j("- 확정 실패(하한 <= 50%) -> 챔피언 유지")
        else:
            log_j(f"- 채택 없음(최고 {desc[best]} {res[best]['win']:.1%}) -> 챔피언 {champ} 유지")
    except Exception:
        log_j(f"- 라운드 {r} 오류:\n```\n{traceback.format_exc()[-1500:]}\n```")
    s["round"] = r + 1
    save_state(s)
    print(f"round {r} done; champion {s['champion']}")


if __name__ == "__main__":
    main()
