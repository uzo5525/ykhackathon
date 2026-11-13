"""v10 턴0 오프닝 빔 서치 엔진.

상대의 5대 아키타입(W_RUSH / F_RUSH / DEPOT_RACE / BALANCED / TURTLE_EXPAND)에 대해 1~DEPTH 턴을
매크로 액션 단위로 가상 플레이(롤아웃)하고, 빔 서치(폭 BEAM_W)로 최선의 매크로 수순을 찾는다.
시간 가드: 매 깊이마다 deadline 을 확인하고, 넘으면 그 시점의 최선 빔으로 정책을 고정한다.
남는 시간은 적 모델의 무작위 변형(타이브레이크·생산 지연)으로 탐색을 반복해 턴별 다수결로 정책을 안정화한다.

롤아웃 모델은 공식 규칙의 단순화다(공학관 할인·역 순간이동·정찰병 제외, 점수는 사전 기대값).
"""
from __future__ import annotations

import random
import time

MACROS = ("OPEN_HALL_F2", "OPEN_DEPOT_FAST", "OPEN_CENTER_CONTEST", "OPEN_STATION_TELE", "OPEN_SAFE_DEFENSIVE")
ARCHETYPES = ("W_RUSH", "F_RUSH", "DEPOT_RACE", "BALANCED", "TURTLE_EXPAND")

BEAM_W = 32
DEPTH = 12
F_COST, W_COST = 5, 3
INCOME, HALL_BONUS, CAP, DEPOT_BONUS = 10, 2, 40, 15

# 평가 가중치: Score = a*BuildingScore + b*OccupationTempo + g*Resource + d*UsefulF - l*HomeThreat
EV_A, EV_B, EV_G, EV_D, EV_L = 1.0, 0.08, 0.05, 0.6, 1.2


class Board:
    """롤아웃용 정적 보드. side 0 = 아군, side 1 = 상대."""

    def __init__(self, cache, team, prior, home_of):
        c = cache
        self.c = c
        opp = "K" if team == "Y" else "Y"
        self.base = (c.base[team], c.base[opp])
        self.bids = sorted(c.bpos)
        self.pos = [c.bpos[b] for b in self.bids]
        self.type = [c.btype[b] for b in self.bids]
        self.score = [prior(b) for b in self.bids]
        self.at = {p: k for k, p in enumerate(self.pos)}
        # home_of[k] = 0(아군 진영) / 1(상대 진영) / None(중앙)
        self.home = [home_of(b) for b in self.bids]
        self.cost = [4 if t == "PLAZA" else 2 for t in self.type]
        nb = len(self.bids)
        self.pref = {}
        for m in MACROS + ARCHETYPES:
            for side in (0, 1):
                self.pref[(m, side)] = [self._pref(m, side, k) for k in range(nb)]

    def _pref(self, m, side, k):
        t, h = self.type[k], self.home[k]
        if m in ("OPEN_HALL_F2",):
            return 6.0 if t == "HALL" and h == side else (2.0 if h == side else 0.0)
        if m in ("OPEN_DEPOT_FAST", "DEPOT_RACE"):
            return 8.0 if t == "DEPOT" else 0.0
        if m == "OPEN_CENTER_CONTEST":
            return 5.0 if h is None else 0.0
        if m == "OPEN_STATION_TELE":
            return 5.0 if t == "STATION" else 0.0
        if m in ("OPEN_SAFE_DEFENSIVE", "TURTLE_EXPAND"):
            return 6.0 if h == side else -4.0
        if m == "F_RUSH":
            return 3.0 if h == 1 - side else 1.0
        return 1.0   # BALANCED, W_RUSH


class State:
    __slots__ = ("res", "owner", "F", "W", "paid", "occ", "fdead", "threat")

    def clone(self):
        s = State()
        s.res = self.res[:]
        s.owner = self.owner[:]
        s.F = [[f[:] for f in self.F[0]], [f[:] for f in self.F[1]]]
        s.W = [dict(self.W[0]), dict(self.W[1])]
        s.paid = [set(self.paid[0]), set(self.paid[1])]
        s.occ = self.occ[:]
        s.fdead = self.fdead[:]
        s.threat = self.threat
        return s


def initial_state(nb):
    s = State()
    s.res = [10, 10]
    s.owner = [-1] * nb
    s.F = [[], []]          # [pos, target_k]
    s.W = [{}, {}]
    s.paid = [set(), set()]
    s.occ = [0.0, 0.0]
    s.fdead = [0, 0]
    s.threat = 0.0
    return s


def _spawn(bd, s, side, policy, turn, rng):
    r = s.res[side]
    nf = nw = 0
    fcount = len(s.F[side])
    if policy == "OPEN_HALL_F2":
        nf = min(2, r // F_COST)
    elif policy in ("OPEN_DEPOT_FAST", "OPEN_CENTER_CONTEST", "OPEN_STATION_TELE", "BALANCED", "DEPOT_RACE"):
        nf = 1 if (r >= F_COST and fcount < 5) else 0
        if turn == 1:
            nf = min(2, r // F_COST)
    elif policy == "F_RUSH":
        nf = r // F_COST
    elif policy == "W_RUSH":
        nf = 1 if (turn == 1 and fcount == 0) else 0
    elif policy in ("OPEN_SAFE_DEFENSIVE", "TURTLE_EXPAND"):
        nf = 1 if fcount < 2 and r >= F_COST else 0
    if rng is not None and side == 1 and nf and rng.random() < 0.15:
        nf -= 1   # 적 모델 변형: 생산 지연
    r -= nf * F_COST
    nw = r // W_COST if policy != "F_RUSH" else max(0, (r - 2) // W_COST)
    r -= nw * W_COST
    s.res[side] = r
    base = bd.base[side]
    for _ in range(nf):
        s.F[side].append([base, -1])
    if nw:
        s.W[side][base] = s.W[side].get(base, 0) + nw


def _assign(bd, s, side, policy, rng):
    c = bd.c
    pref = bd.pref[(policy, side)]
    taken = {f[1] for f in s.F[side] if f[1] >= 0 and s.owner[f[1]] != side}
    for f in s.F[side]:
        if f[1] >= 0 and s.owner[f[1]] != side:
            continue
        row = c.dist[f[0]]
        best, bu = -1, -1e9
        for k, p in enumerate(bd.pos):
            if s.owner[k] == side or k in taken:
                continue
            d = row[p]
            u = pref[k] + bd.score[k] * 2.0 / (d + 1) - 0.25 * d
            if rng is not None and side == 1:
                u += rng.random() * 0.5
            if u > bu:
                best, bu = k, u
        f[1] = best
        if best >= 0:
            taken.add(best)


def _step_to(c, a, b):
    if a == b:
        return a
    d = c.step[a][b] if c.step[a] is not None else None
    if d is None:
        return a
    for dd, j in c.nbrs[a]:
        if dd == d:
            return j
    return a


def _move(bd, s, side, policy):
    c = bd.c
    for f in s.F[side]:
        if f[1] >= 0:
            f[0] = _step_to(c, f[0], bd.pos[f[1]])
    goals = [bd.pos[f[1]] for f in s.F[side] if f[1] >= 0]
    if policy == "W_RUSH":
        goals = [bd.base[1 - side]]
    elif policy in ("OPEN_SAFE_DEFENSIVE", "TURTLE_EXPAND"):
        homes = [bd.pos[k] for k in range(len(bd.pos)) if bd.home[k] == side and s.owner[k] == side]
        goals = homes or [bd.base[side]]
    if not goals:
        return
    nw = {}
    for p, k in s.W[side].items():
        g = min(goals, key=lambda x: c.dist[p][x])
        q = _step_to(c, p, g)
        nw[q] = nw.get(q, 0) + k
    s.W[side] = nw


def _combat(bd, s):
    W0, W1 = s.W
    cells = set(W0) | set(W1) | {f[0] for f in s.F[0]} | {f[0] for f in s.F[1]}
    f0 = {}
    f1 = {}
    for f in s.F[0]:
        f0[f[0]] = f0.get(f[0], 0) + 1
    for f in s.F[1]:
        f1[f[0]] = f1.get(f[0], 0) + 1
    for p in cells:
        a, b = W0.get(p, 0), W1.get(p, 0)
        if not ((a or f0.get(p)) and (b or f1.get(p))):
            continue
        m = min(a, b)
        a -= m
        b -= m
        if a:
            W0[p] = a
        else:
            W0.pop(p, None)
        if b:
            W1[p] = b
        else:
            W1.pop(p, None)
        loser = 1 if a > 0 else (0 if b > 0 else None)
        if loser is None:
            continue
        keep = [f for f in s.F[loser] if f[0] != p]
        dead = len(s.F[loser]) - len(keep)
        if dead:
            s.F[loser] = keep
            s.fdead[loser] += dead
            k = bd.at.get(p)
            if k is not None and s.owner[k] == loser:
                s.owner[k] = -1


def _capture(bd, s):
    for side in (0, 1):
        s.res[side] = min(CAP, s.res[side] + INCOME + HALL_BONUS * sum(
            1 for k, t in enumerate(bd.type) if t == "HALL" and s.owner[k] == side))
    occ_f = [set(), set()]
    for side in (0, 1):
        for f in s.F[side]:
            occ_f[side].add(f[0])
    for side in (0, 1):
        bonus = 0
        for p in occ_f[side]:
            k = bd.at.get(p)
            if k is None or s.owner[k] == side or p in occ_f[1 - side]:
                continue
            if s.res[side] >= bd.cost[k]:
                s.res[side] -= bd.cost[k]
                if s.owner[k] == 1 - side:
                    s.owner[k] = -1
                else:
                    s.owner[k] = side
                    if bd.type[k] == "DEPOT" and k not in s.paid[side]:
                        s.paid[side].add(k)
                        bonus += DEPOT_BONUS
        s.res[side] = min(CAP, s.res[side] + bonus)
    for side in (0, 1):
        s.occ[side] += sum(bd.score[k] for k in range(len(bd.pos)) if s.owner[k] == side)


def step(bd, s, macro, arch, turn, rng=None):
    _spawn(bd, s, 0, macro, turn, None)
    _spawn(bd, s, 1, arch, turn, rng)
    _assign(bd, s, 0, macro, None)
    _assign(bd, s, 1, arch, rng)
    _move(bd, s, 0, macro)
    _move(bd, s, 1, arch)
    _combat(bd, s)
    _capture(bd, s)
    # 홈 위협: 아군 소유 홈 건물(또는 본진) 2칸 이내 적 유닛 수
    c = bd.c
    anchors = [bd.pos[k] for k in range(len(bd.pos)) if bd.home[k] == 0 and s.owner[k] == 0] or [bd.base[0]]
    th = 0
    for p, k in s.W[1].items():
        if min(c.dist[p][a] for a in anchors) <= 2:
            th += k
    for f in s.F[1]:
        if min(c.dist[f[0]][a] for a in anchors) <= 2:
            th += 1
    s.threat += th


def evaluate(bd, s):
    bs = sum(bd.score[k] for k in range(len(bd.pos)) if s.owner[k] == 0) - \
        sum(bd.score[k] for k in range(len(bd.pos)) if s.owner[k] == 1)
    useful = sum(1 for f in s.F[0] if f[1] >= 0) - s.fdead[0]
    return (EV_A * bs + EV_B * (s.occ[0] - s.occ[1]) + EV_G * (s.res[0] - s.res[1])
            + EV_D * useful - EV_L * s.threat)


class OpeningPolicy:
    def __init__(self):
        self.per_arch = {}     # arch -> [macro per turn 1..]
        self.hard = []         # 아키타입 무관 강건 수순(최악 경우 최대화)
        self.stats = {"passes": 0, "rollouts": 0, "depth": 0, "ms": 0.0, "complete": False}
        self.robust = {}

    def macro(self, turn, arch=None):
        seq = self.per_arch.get(arch) if arch else None
        if not seq:
            seq = self.hard
        if 1 <= turn <= len(seq):
            return seq[turn - 1]
        return None


def _beam_all(bd, archs, deadline, rng_seed):
    """모든 아키타입 빔을 깊이 단위로 나란히 전개(시간 초과 시 모든 아키타입이 같은 깊이에서 멈춤)."""
    rngs = {a: (random.Random(rng_seed * 31 + i) if rng_seed else None) for i, a in enumerate(archs)}
    beams = {a: [(0.0, initial_state(len(bd.pos)), [])] for a in archs}
    rollouts = 0
    depth = 0
    for dep in range(1, DEPTH + 1):
        if time.perf_counter() > deadline:
            break
        nxt = {}
        for a in archs:
            cand = []
            for _, st, seq in beams[a]:
                for m in MACROS:
                    ns = st.clone()
                    r = rngs[a]
                    step(bd, ns, m, a, dep, random.Random(r.random()) if r else None)
                    rollouts += 1
                    cand.append((evaluate(bd, ns), ns, seq + [m]))
            cand.sort(key=lambda x: -x[0])
            nxt[a] = cand[:BEAM_W]
            if time.perf_counter() > deadline and a != archs[-1]:
                pass   # 한 깊이는 모든 아키타입을 끝까지 전개한다(균형)
        beams = nxt
        depth = dep
    return {a: beams[a][0] for a in archs}, rollouts, depth


def _play(bd, seq, arch, depth):
    s = initial_state(len(bd.pos))
    for t in range(1, depth + 1):
        m = seq[t - 1] if t - 1 < len(seq) else seq[-1]
        step(bd, s, m, arch, t, None)
    return evaluate(bd, s)


def build_policy(bd, deadline):
    t0 = time.perf_counter()
    pol = OpeningPolicy()
    # 1) 결정론 패스: 아키타입별 최선 수순
    best, n, depth = _beam_all(bd, ARCHETYPES, deadline, 0)
    pol.stats["rollouts"] += n
    pol.stats["depth"] = depth
    pol.stats["passes"] = 1
    if depth == 0:
        pol.stats["ms"] = (time.perf_counter() - t0) * 1000
        return pol
    for a, (_, _, seq) in best.items():
        pol.per_arch[a] = seq
    # 2) 강건 수순: 각 아키타입 최선 수순을 모든 아키타입 상대로 교차 평가, 최악값 최대
    worst = {}
    for a, seq in pol.per_arch.items():
        vals = []
        for b in ARCHETYPES:
            vals.append(_play(bd, seq, b, depth))
            pol.stats["rollouts"] += depth
        worst[a] = min(vals)
    pol.robust = worst
    pol.hard = pol.per_arch[max(worst, key=lambda a: (worst[a], a))]
    # 3) 남는 시간: 적 모델 무작위 변형으로 반복 탐색, 턴별 다수결(첫 패스 포함)
    votes = {a: [{s: 1} for s in pol.per_arch[a]] for a in ARCHETYPES}
    k = 1
    while time.perf_counter() < deadline:
        res, n, dp = _beam_all(bd, ARCHETYPES, deadline, k)
        pol.stats["rollouts"] += n
        if dp < depth:
            break   # 시간 초과로 불완전한 패스는 버린다
        pol.stats["passes"] += 1
        for a, (_, _, seq) in res.items():
            for t, m in enumerate(seq):
                votes[a][t][m] = votes[a][t].get(m, 0) + 1
        k += 1
    for a in ARCHETYPES:
        pol.per_arch[a] = [max(v, key=lambda m: (v[m], m == pol.per_arch[a][t]))
                           for t, v in enumerate(votes[a])]
    pol.stats["complete"] = True
    pol.stats["ms"] = (time.perf_counter() - t0) * 1000
    return pol


def classify(view_units, team, cache, turn):
    """관측 유닛 분포로 적 아키타입 판별(턴 3~5 SOFT 단계)."""
    c = cache
    opp = "K" if team == "Y" else "Y"
    ef, ew = [], 0
    ew_cells = []
    for u in view_units:
        if u["team"] != opp:
            continue
        i = u["y"] * c.w + u["x"]
        if u["kind"] == "F":
            ef.extend([i] * u["count"])
        elif u["kind"] == "W":
            ew += u["count"]
            ew_cells.append((i, u["count"]))
    nf = len(ef)
    mb, ob = c.base[team], c.base[opp]
    if ew >= 2 * nf + 3:
        return "W_RUSH"
    if nf >= 3 and nf >= ew:
        return "F_RUSH"
    depots = [p for b, p in c.bpos.items() if c.btype[b] == "DEPOT"]
    if ef and depots and min(c.d(e, p) for e in ef for p in depots) <= 2 and turn <= 5:
        return "DEPOT_RACE"
    if ef and all(c.d(e, ob) < c.d(e, mb) - 4 for e in ef) and all(c.d(i, ob) < c.d(i, mb) for i, _ in ew_cells):
        return "TURTLE_EXPAND"
    return "BALANCED"
