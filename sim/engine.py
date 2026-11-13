"""깃발 대항전 로컬 근사 엔진 (공식 엔진 부재로 규칙서 불변식 + BALANCE 기반 재구성).

턴 순서: 생산 -> 이동(TELE/MOVE/MOVE2) -> 전투 -> 건물효과(공개) -> 수입 -> 점령 -> 보급소 보너스.
점수: 게임 종료 시 소유 건물 점수 합. 동점 시 누적 점령-턴(턴마다 소유 건물 점수 합 누적), 유닛 가치.

주의: 맵 생성(건물 구성·배치)은 추정치다. 실제 대회 맵과 다를 수 있다.
"""
from __future__ import annotations

import random
from collections import deque

W = H = 15
TOTAL_TURNS = 160
COST = {"F": 5, "W": 3, "S": 2}
VALUE = {"F": 5, "W": 3, "S": 2}
DIRS = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}
START_RES, BASE_INC, HALL_BONUS, RES_CAP = 10, 10, 2, 40
DEPOT_BONUS = 15
TEAMS = ("Y", "K")

HOME_TYPES = ["HALL", "ENG", "LIBRARY", "STATION", "HOSPITAL"]
CENTER_PAIR_TYPES = ["DEPOT", "WATCH", "STATION"]


def mirror(x, y):
    return W - 1 - x, H - 1 - y


class Game:
    def __init__(self, seed, map_path=None):
        self.rng = random.Random(seed)
        self.seed = seed
        if map_path:
            self._load_map(map_path)
        else:
            self._gen_map()
        self.turn = 0
        self.res = {"Y": START_RES, "K": START_RES}
        self.units = {}  # (x, y, team, kind) -> count
        self.owner = {b["id"]: "N" for b in self.buildings}
        self.revealed = {"Y": set(), "K": set()}
        self.depot_paid = {"Y": set(), "K": set()}
        self.occ = {"Y": 0, "K": 0}
        self.just_neutral = set()   # 이번 턴 소유 -> 중립이 된 건물(다음 턴 입력에 단계 1로 표시)
        self.shown_neutral = set()
        self.total_score = sum(b["score"] for b in self.buildings)
        self.instant = None
        self.cap_turn = {"Y": {}, "K": {}}   # 계측 전용: 팀별 건물 최근 점령 턴
        # ---- 계측(결과 무관): F 가상 ID 추적, 역방향 이동, 교전 비율
        self.ftok = {"Y": [], "K": []}
        self.last_arr = {"Y": {}, "K": {}}   # (도착셀, 병종) -> {출발셀: 수}
        self.mv = {t: {"moves": 0, "reverse": 0, "excluded": 0} for t in TEAMS}
        self.er = {"Y": [], "K": []}
        self.stats = {t: {"F_spawned": 0, "F_killed": 0, "W_spawned": 0, "W_killed": 0,
                          "captures": 0, "neutralized_by_kill": 0, "bad_cmds": 0} for t in TEAMS}

    # ---------------------------------------------------------------- map
    def _gen_map(self):
        rng = self.rng
        while True:
            terrain = [["." for _ in range(W)] for _ in range(H)]
            by = (rng.randint(0, 4), rng.randint(0, 14))
            bk = mirror(*by)
            if abs(by[0] - bk[0]) + abs(by[1] - bk[1]) < 12:
                continue
            used = {by, bk}
            blds = []

            def place(xlo, xhi, ylo, yhi, btype, score_rng):
                for _ in range(400):
                    x, y = rng.randint(xlo, xhi), rng.randint(ylo, yhi)
                    m = mirror(x, y)
                    if (x, y) in used or m in used or (x, y) == m:
                        continue
                    if any(abs(x - ux) + abs(y - uy) < 2 for ux, uy in used):
                        continue
                    used.add((x, y)); used.add(m)
                    s = rng.randint(*score_rng)
                    blds.append(((x, y), btype, s))
                    blds.append((m, btype, s))
                    return True
                return False

            ok = True
            for t in HOME_TYPES:
                ok &= place(0, 4, 0, 14, t, (1, 2))
            used.add((7, 7))
            for t in CENTER_PAIR_TYPES:
                ok &= place(5, 9, 2, 12, t, (2, 4))
            if not ok:
                continue
            blds.append(((7, 7), "PLAZA", 3))
            # 장애물 10쌍
            n = 0
            tries = 0
            while n < 10 and tries < 4000:
                tries += 1
                x, y = rng.randrange(W), rng.randrange(H)
                m = mirror(x, y)
                if (x, y) in used or m in used or (x, y) == m or terrain[y][x] == "#":
                    continue
                terrain[y][x] = "#"; terrain[m[1]][m[0]] = "#"
                if self._connected(terrain, [by, bk] + [p for p, _, _ in blds]):
                    n += 1
                else:
                    terrain[y][x] = "."; terrain[m[1]][m[0]] = "."
            break
        for (x, y), _, _ in blds:
            terrain[y][x] = "B"
        terrain[by[1]][by[0]] = "H"
        terrain[bk[1]][bk[0]] = "H"
        self.terrain = terrain
        self.bases = {"Y": by, "K": bk}
        blds.sort(key=lambda b: (b[0][1], b[0][0]))
        self.buildings = [{"id": i + 1, "x": p[0], "y": p[1], "type": t, "score": s}
                          for i, (p, t, s) in enumerate(blds)]
        self.bat = {(b["x"], b["y"]): b for b in self.buildings}

    def _load_map(self, path):
        """리플레이의 실제 맵. 점수는 리플레이에서 공개된 값 + 대칭 짝, 나머지는 지역 범위에서 시드로 생성."""
        import json
        d = json.load(open(path, encoding="utf-8"))
        o = d["turns"][0]["observation"]
        self.terrain = [list(row) for row in o["map"]]
        hs = [(x, y) for y, row in enumerate(self.terrain) for x, ch in enumerate(row) if ch == "H"]
        hs.sort()
        self.bases = {"Y": hs[0], "K": hs[1]}
        known = {}
        for t in d["turns"]:
            for k, v in t.get("revealed", {}).get("buildingScores", {}).items():
                known[int(k)] = v
        blds = o["buildings"]
        pos = {(b["x"], b["y"]): b["id"] for b in blds}
        for b in blds:
            m = pos.get(mirror(b["x"], b["y"]))
            if b["id"] in known and m is not None and m not in known:
                known[m] = known[b["id"]]
        scores = {}
        for b in sorted(blds, key=lambda b: b["id"]):
            if b["id"] in scores:
                continue
            if b["type"] == "PLAZA":
                s_ = 3
            elif b["id"] in known:
                s_ = known[b["id"]]
            else:
                s_ = self.rng.randint(2, 4) if 5 <= b["x"] <= 9 else self.rng.randint(1, 2)
            scores[b["id"]] = s_
            m = pos.get(mirror(b["x"], b["y"]))
            if m is not None and m not in scores:
                scores[m] = known.get(m, s_)
        self.buildings = [{"id": b["id"], "x": b["x"], "y": b["y"], "type": b["type"], "score": scores[b["id"]]}
                          for b in sorted(blds, key=lambda b: b["id"])]
        self.bat = {(b["x"], b["y"]): b for b in self.buildings}
        self.map_name = path

    @staticmethod
    def _connected(terrain, pts):
        s = pts[0]
        seen = {s}
        q = deque([s])
        while q:
            x, y = q.popleft()
            for dx, dy in DIRS.values():
                nx, ny = x + dx, y + dy
                if 0 <= nx < W and 0 <= ny < H and (nx, ny) not in seen and terrain[ny][nx] != "#":
                    seen.add((nx, ny)); q.append((nx, ny))
        return all(p in seen for p in pts)

    def passable(self, x, y):
        return 0 <= x < W and 0 <= y < H and self.terrain[y][x] != "#"

    # ---------------------------------------------------------------- protocol
    def init_text(self, team):
        lines = [f"INIT {W} {H}", f"TEAM {team}"]
        for y in range(H):
            lines.append(f"MAP {''.join(self.terrain[y])}")
        lines.append(f"BUILDINGS {len(self.buildings)}")
        for b in self.buildings:
            lines.append(f"{b['id']} {b['x']} {b['y']} {b['type']}")
        for t in TEAMS:
            lines.append(f"BASE {t} {self.bases[t][0]} {self.bases[t][1]}")
        lines.append("END")
        return "\n".join(lines) + "\n"

    def turn_text(self, team):
        opp = "K" if team == "Y" else "Y"
        lines = [f"TURN {self.turn}", f"RESOURCE {self.res[team]} {self.res[opp]}"]
        us = [(k, c) for k, c in sorted(self.units.items()) if c > 0]
        lines.append(f"UNITS {len(us)}")
        for (x, y, t, kind), c in us:
            lines.append(f"{t} {kind} {x} {y} {c}")
        lines.append(f"BUILDINGS {len(self.buildings)}")
        for b in self.buildings:
            s = b["score"] if (b["type"] == "PLAZA" or b["id"] in self.revealed[team]
                               or self.owner[b["id"]] == team) else -1
            o = self.owner[b['id']]
            stage = 2 if o != "N" else (1 if b["id"] in self.shown_neutral else 0)
            lines.append(f"{b['id']} {b['x']} {b['y']} {b['type']} {o} {stage} {s}")
        lines.append("END")
        return "\n".join(lines) + "\n"

    # ---------------------------------------------------------------- helpers
    def owned(self, team, btype=None):
        return [b for b in self.buildings if self.owner[b["id"]] == team
                and (btype is None or b["type"] == btype)]

    def add(self, x, y, team, kind, c):
        k = (x, y, team, kind)
        self.units[k] = self.units.get(k, 0) + c
        if self.units[k] <= 0:
            del self.units[k]

    def score(self, team):
        return sum(b["score"] for b in self.owned(team))

    def unit_value(self, team):
        return sum(VALUE[k[3]] * c for k, c in self.units.items() if k[2] == team)

    # ---------------------------------------------------------------- step
    def step(self, cmds):
        """cmds: {team: [str]} -> 한 턴 처리."""
        # 0) 턴 시작 소유 상태 스냅샷(생산/TELE 판정 기준)
        start_owner = dict(self.owner)
        parsed = {t: [c.split() for c in cmds.get(t, []) if c.strip()] for t in TEAMS}

        # 1) 생산
        for t in TEAMS:
            n_eng = sum(1 for b in self.buildings if start_owner[b["id"]] == t and b["type"] == "ENG")
            wc = max(2, 3 - n_eng)
            for tok in parsed[t]:
                if tok[0] != "SPAWN":
                    continue
                try:
                    kind, cnt = tok[1], int(tok[2])
                    if kind not in COST or cnt <= 0:
                        raise ValueError
                    if len(tok) == 5:
                        x, y = int(tok[3]), int(tok[4])
                        b = self.bat.get((x, y))
                        if b is None or b["type"] != "HOSPITAL" or start_owner[b["id"]] != t:
                            raise ValueError
                    elif len(tok) == 3:
                        x, y = self.bases[t]
                    else:
                        raise ValueError
                    unit = wc if kind == "W" else COST[kind]
                    cnt = min(cnt, self.res[t] // unit)
                    if cnt <= 0:
                        raise ValueError
                    self.res[t] -= unit * cnt
                    self.add(x, y, t, kind, cnt)
                    if kind == "F":
                        for _ in range(cnt):
                            self.ftok[t].append({"pos": (x, y), "spawn": self.turn, "caps": [],
                                                 "death": None, "moved": False})
                    if kind in ("F", "W"):
                        self.stats[t][f"{kind}_spawned"] += cnt
                except (ValueError, IndexError):
                    self.stats[t]["bad_cmds"] += 1

        # 2) 이동 (시작 위치 기준 가용 수량에서 차감, 도착은 동시 적용)
        avail = dict(self.units)
        for t in TEAMS:
            for tk in self.ftok[t]:
                tk["moved"] = False
                tk["prev"] = tk["pos"]
        self._ew_start = enemy_w_start = {
            t: [(k[0], k[1]) for k in self.units if k[2] != t and k[3] == "W"] for t in TEAMS}
        # 긴급 판정(계측 전용): 출발 칸 맨해튼 2 이내에 적 W가 있으면 역방향 통계에서 제외
        enemy_w = {t: [(k[0], k[1]) for k in self.units if k[2] != t and k[3] == "W"] for t in TEAMS}
        new_arr = {"Y": {}, "K": {}}
        arrivals = []
        for t in TEAMS:
            stations = {(b["x"], b["y"]) for b in self.buildings
                        if start_owner[b["id"]] == t and b["type"] == "STATION"}
            tele_used = 0
            for tok in parsed[t]:
                op = tok[0]
                if op in ("SPAWN", "PRIORITY"):
                    continue
                try:
                    x, y, kind, cnt = int(tok[1]), int(tok[2]), tok[3], int(tok[4])
                    key = (x, y, t, kind)
                    if kind not in COST or cnt <= 0:
                        raise ValueError
                    cnt = min(cnt, avail.get(key, 0))
                    if cnt <= 0:
                        raise ValueError
                    if op == "MOVE":
                        dx, dy = DIRS[tok[5]]
                        nx, ny = x + dx, y + dy
                        if len(tok) != 6 or not self.passable(nx, ny):
                            raise ValueError
                    elif op == "MOVE2":
                        if kind != "S" or len(tok) != 7:
                            raise ValueError
                        dx, dy = DIRS[tok[5]]
                        mx, my = x + dx, y + dy
                        dx2, dy2 = DIRS[tok[6]]
                        nx, ny = mx + dx2, my + dy2
                        if not (self.passable(mx, my) and self.passable(nx, ny)):
                            raise ValueError
                    elif op == "TELE":
                        nx, ny = int(tok[5]), int(tok[6])
                        if (tele_used >= 1 or len(stations) < 2 or cnt > 5
                                or (x, y) not in stations or (nx, ny) not in stations or (x, y) == (nx, ny)):
                            raise ValueError
                        tele_used += 1
                    else:
                        raise ValueError
                    avail[key] -= cnt
                    self.add(x, y, t, kind, -cnt)
                    arrivals.append((nx, ny, t, kind, cnt))
                    self._track_move(t, kind, (x, y), (nx, ny), cnt, op, enemy_w[t], new_arr[t])
                except (ValueError, IndexError, KeyError):
                    self.stats[t]["bad_cmds"] += 1
        for nx, ny, t, kind, cnt in arrivals:
            self.add(nx, ny, t, kind, cnt)
        self.last_arr = new_arr

        # 3) 전투
        cells = {}
        for (x, y, t, kind), c in self.units.items():
            cells.setdefault((x, y), {}).setdefault(t, {})[kind] = c
        for (x, y), side in cells.items():
            if len(side) < 2:
                continue
            wy, wk = side["Y"].get("W", 0), side["K"].get("W", 0)
            if wy and wk:
                self.er["Y"].append(wy / (wk + 1))
                self.er["K"].append(wk / (wy + 1))
            m = min(wy, wk)
            if m:
                self.add(x, y, "Y", "W", -m); self.add(x, y, "K", "W", -m)
                self.stats["Y"]["W_killed"] += m; self.stats["K"]["W_killed"] += m
            wy -= m; wk -= m
            loser = "K" if wy > 0 else ("Y" if wk > 0 else None)
            if loser:
                for kind in ("F", "S"):
                    c = side[loser].get(kind, 0)
                    if c:
                        self.add(x, y, loser, kind, -c)
                        if kind == "F":
                            self.stats[loser]["F_killed"] += c
                            b0 = self.bat.get((x, y))
                            ctx = ("field" if b0 is None else
                                   ("own_bld" if start_owner[b0["id"]] == loser else "target_bld"))
                            for tk in self.ftok[loser]:
                                if tk["death"] is None and tk["pos"] == (x, y):
                                    tk["death"] = self.turn
                                    tk["ctx"] = ctx + ("_moved" if tk["moved"] else "_stayed")
                                    tk["cause"] = self._cause(tk, ctx, loser)
                                    tk["wdiff"] = (side[loser].get("W", 0), side["K" if loser == "Y" else "Y"].get("W", 0))
                            b = self.bat.get((x, y))
                            if b and self.owner[b["id"]] == loser:
                                self._quick_lost(b, loser)
                                self._home_econ_lost(b, loser)
                                self.owner[b["id"]] = "N"
                                self.just_neutral.add(b["id"])
                                self.stats["K" if loser == "Y" else "Y"]["neutralized_by_kill"] += 1
                                if self.turn > 140:
                                    w_ = "K" if loser == "Y" else "Y"
                                    self.stats[w_]["late_neut"] = self.stats[w_].get("late_neut", 0) + 1
                                self.stats[loser]["flags_pulled"] = self.stats[loser].get("flags_pulled", 0) + 1

        # 5) 수입 (전투 이후·점령 이전 소유권)
        for t in TEAMS:
            self.res[t] = min(RES_CAP, self.res[t] + BASE_INC + HALL_BONUS * len(self.owned(t, "HALL")))

        # 7) 점령: 살아남은 깃발병 기준. 상대 소유는 1단계(중립화), 중립은 즉시 소유.
        flag_cells = {}
        for (x, y, t, kind), c in self.units.items():
            if kind == "F" and c > 0:
                flag_cells.setdefault((x, y), set()).add(t)
        lib_at_start = {t: bool(self.owned(t, "LIBRARY")) for t in TEAMS}
        new_depots = {"Y": [], "K": []}
        for t in TEAMS:
            prio = []
            for tok in parsed[t]:
                if tok[0] == "PRIORITY":
                    try:
                        vals = list(map(int, tok[1:]))
                        if len(vals) % 2 or not vals:
                            raise ValueError
                        prio = [(vals[i], vals[i + 1]) for i in range(0, len(vals), 2)]
                    except ValueError:
                        self.stats[t]["bad_cmds"] += 1
            order = {}
            for p in prio:
                order.setdefault(p, len(order))
            cands = [b for b in self.buildings
                     if flag_cells.get((b["x"], b["y"])) == {t} and self.owner[b["id"]] != t]

            def norm(b):
                return (b["y"], b["x"]) if t == "Y" else (14 - b["y"], 14 - b["x"])

            def known(b):
                return b["score"] if (b["type"] == "PLAZA" or b["id"] in self.revealed[t]) else 0
            cands.sort(key=lambda b: (order.get((b["x"], b["y"]), 999), -known(b), norm(b)))
            for b in cands:
                cost = 2 * (2 if b["type"] == "PLAZA" else 1) - (1 if lib_at_start[t] else 0)
                cost = max(1, cost)
                if self.res[t] >= cost:
                    self.res[t] -= cost
                    if self.owner[b["id"]] == "N":
                        self.owner[b["id"]] = t
                        self.stats[t]["captures"] += 1
                        self.cap_turn[t][b["id"]] = self.turn
                        if self.turn <= 40:
                            self.stats[t]["caps40"] = self.stats[t].get("caps40", 0) + 1
                        for tk in self.ftok[t]:
                            if tk["death"] is None and tk["pos"] == (b["x"], b["y"]):
                                tk["caps"].append(self.turn)
                        if b["type"] == "DEPOT" and b["id"] not in self.depot_paid[t]:
                            new_depots[t].append(b["id"])
                    else:
                        self._quick_lost(b, self.owner[b["id"]])
                        self._home_econ_lost(b, self.owner[b["id"]])
                        self.owner[b["id"]] = "N"
                        self.just_neutral.add(b["id"])
                        self.stats[t]["neutralize_cap"] = self.stats[t].get("neutralize_cap", 0) + 1
                        if self.turn > 140:
                            self.stats[t]["late_neut"] = self.stats[t].get("late_neut", 0) + 1
        # 보급소 보너스: 모든 점령 처리 후
        for t in TEAMS:
            for bid in new_depots[t]:
                self.depot_paid[t].add(bid)
                self.res[t] = min(RES_CAP, self.res[t] + DEPOT_BONUS)
            self.occ[t] += self.score(t)
            if "t_own5" not in self.stats[t] and len(self.owned(t)) >= 5:
                self.stats[t]["t_own5"] = self.turn

        # 8) 정보 공개: 건물 위 유닛, 정찰병 2, 방송국 3 (체비셰프)
        for t in TEAMS:
            eyes = [(k[0], k[1], 0) for k in self.units if k[2] == t]
            eyes += [(k[0], k[1], 2) for k in self.units if k[2] == t and k[3] == "S"]
            eyes += [(b["x"], b["y"], 3) for b in self.owned(t, "WATCH")]
            for b in self.buildings:
                for ex, ey, r in eyes:
                    if max(abs(ex - b["x"]), abs(ey - b["y"])) <= r:
                        self.revealed[t].add(b["id"])
                        break
        self.shown_neutral = {bid for bid in self.just_neutral if self.owner[bid] == "N"}
        self.just_neutral = set()

        # 9) 즉시 승리
        for t in TEAMS:
            o = "K" if t == "Y" else "Y"
            if self.score(o) == 0 and self.score(t) * 2 > self.total_score:
                self.instant = t

    def _quick_lost(self, b, team):
        """계측: team 이 점령한 지 5턴 이내 건물을 잃음(적 F 중립화 또는 F 전사)."""
        ct = self.cap_turn[team].get(b["id"])
        if ct is not None and self.turn - ct <= 5:
            self.stats[team]["quick_lost"] = self.stats[team].get("quick_lost", 0) + 1
            if b["type"] == "DEPOT":
                self.stats[team]["quick_lost_depot"] = self.stats[team].get("quick_lost_depot", 0) + 1

    def _home_econ_lost(self, b, team):
        """team 소유였던 b 가 중립화될 때 호출. 홈 경제 건물이면 계측."""
        if b["type"] not in ("ENG", "HALL"):
            return
        home = b["x"] <= 4 if team == "Y" else b["x"] >= 10
        if home:
            k = "home_%s_lost" % b["type"].lower()
            self.stats[team][k] = self.stats[team].get(k, 0) + 1

    def _cause(self, tk, ctx, team):
        if self.turn - tk["spawn"] <= 1:
            return "SPAWN_DEATH"
        if ctx == "own_bld":
            return "POST_CAPTURE_DEATH"
        if ctx == "target_bld":
            return "CAPTURE_DEATH"
        ew = self._ew_start.get(team) or []
        if tk["moved"] and ew:
            def near(p):
                return min(abs(p[0] - ex) + abs(p[1] - ey) for ex, ey in ew)
            if near(tk["pos"]) > near(tk["prev"]):
                return "RETREAT_DEATH"
        return "TRAVEL_DEATH_moved" if tk["moved"] else "TRAVEL_DEATH_stayed"

    def _track_move(self, t, kind, src, dst, cnt, op, enemy_w, new_arr):
        if kind == "F":
            n = cnt
            for tk in self.ftok[t]:
                if n <= 0:
                    break
                if tk["death"] is None and not tk["moved"] and tk["pos"] == src:
                    tk["pos"] = dst
                    tk["moved"] = True
                    n -= 1
        slot = new_arr.setdefault((dst, kind), {})
        slot[src] = slot.get(src, 0) + cnt
        if op == "TELE":
            return
        if any(abs(ex - src[0]) + abs(ey - src[1]) <= 2 for ex, ey in enemy_w):
            self.mv[t]["excluded"] += cnt
            return
        self.mv[t]["moves"] += cnt
        came = self.last_arr[t].get((src, kind), {})
        r = min(cnt, came.get(dst, 0))
        if r:
            came[dst] -= r
            self.mv[t]["reverse"] += r

    def metrics(self, t, window=3):
        toks = self.ftok[t]
        spawned = len(toks)
        alive = sum(1 for tk in toks if tk["death"] is None)
        capd = [tk for tk in toks if tk["caps"]]
        pcd = 0
        for tk in capd:
            if tk["death"] is not None and any(0 < tk["death"] - c <= window for c in tk["caps"]):
                pcd += 1
        useful = sum(1 for tk in capd if tk["death"] is None or len(tk["caps"]) >= 2)
        return {"F_spawned": spawned, "F_alive": alive, "F_captured": len(capd), "F_useful": useful,
                "flags_pulled": self.stats[t].get("flags_pulled", 0),
                "F_captured_alive": sum(1 for tk in capd if tk["death"] is None),
                "F_post_capture_dead": pcd,
                "moves": self.mv[t]["moves"], "reverse": self.mv[t]["reverse"],
                "er": list(self.er[t]),
                "death_ctx": {k: sum(1 for tk in toks if tk.get("ctx") == k)
                              for k in {tk.get("ctx") for tk in toks if tk.get("ctx")}},
                "death_escorted": sum(1 for tk in toks if tk.get("wdiff") and tk["wdiff"][0] > 0),
                "late_neut": self.stats[t].get("late_neut", 0),
                "home_eng_lost": self.stats[t].get("home_eng_lost", 0),
                "quick_lost": self.stats[t].get("quick_lost", 0),
                "quick_lost_depot": self.stats[t].get("quick_lost_depot", 0),
                "captures": self.stats[t].get("captures", 0),
                "caps40": self.stats[t].get("caps40", 0),
                "t_own5": self.stats[t].get("t_own5", 161),
                "home_hall_lost": self.stats[t].get("home_hall_lost", 0),
                "W_killed": self.stats[t].get("W_killed", 0),
                "late_deaths": sum(1 for tk in toks if tk["death"] is not None and tk["death"] > 140),
                "unit_value": self.unit_value(t),
                "death_cause": {k: sum(1 for tk in toks if tk.get("cause") == k)
                                for k in {tk.get("cause") for tk in toks if tk.get("cause")}}}

    def result(self):
        if self.instant:
            t = self.instant
            ky, kk = (self.score("Y"), self.occ["Y"], 0), (self.score("K"), self.occ["K"], 0)
            return t, ky, kk
        ky = (self.score("Y"), self.occ["Y"], self.unit_value("Y"))
        kk = (self.score("K"), self.occ["K"], self.unit_value("K"))
        return "Y" if ky > kk else ("K" if kk > ky else "D"), ky, kk
