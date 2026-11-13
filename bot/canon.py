"""v10.2 진영 정규화(Canonical Side).

K 진영으로 배정되면 모든 입력을 180° 회전 + 팀 문자 교환(K<->Y)해 봇이 항상 'Y(신촌) 관점'에서 판단하게 하고,
출력 명령의 좌표·방향을 다시 회전해 돌려준다. 맵이 점대칭이므로 K 진영의 판단이 Y 진영의 판단과 정확히 거울상이 된다.
(기존 봇은 낮은 셀 인덱스·건물 id 순의 동점 처리 때문에 같은 맵에서 Y/K 진영의 행동이 달랐다.)

건물 id 도 거울 짝의 id 로 바꿔, 'id 오름차순' 순회·동점 처리까지 Y 진영과 동일하게 만든다.
"""
from campus_bot import Init, View

SWAP = {"Y": "K", "K": "Y", "N": "N"}
FLIP = {"U": "D", "D": "U", "L": "R", "R": "L"}
KIND_ORDER = {"F": 0, "W": 1, "S": 2}


class Canon:
    def __init__(self, init):
        self.w, self.h = init.width, init.height
        pos = {(b["x"], b["y"]): b["id"] for b in init.buildings}
        # 정규 id: 이 건물의 거울 위치에 있는 건물의 원래 id
        self.to_c = {}
        for b in init.buildings:
            m = pos.get(self.rot(b["x"], b["y"]))
            self.to_c[b["id"]] = m if m is not None else b["id"]
        if len(set(self.to_c.values())) != len(self.to_c):   # 비대칭 맵 방어: id 유지
            self.to_c = {b["id"]: b["id"] for b in init.buildings}
        terrain = [[init.terrain[self.h - 1 - y][self.w - 1 - x] for x in range(self.w)] for y in range(self.h)]
        blds = []
        for b in init.buildings:
            x, y = self.rot(b["x"], b["y"])
            blds.append({"id": self.to_c[b["id"]], "x": x, "y": y, "type": b["type"]})
        blds.sort(key=lambda b: b["id"])
        bases = {SWAP[t]: self.rot(*p) for t, p in init.bases.items()}
        self.init = Init(init.width, init.height, SWAP[init.team], terrain, blds, bases)

    def rot(self, x, y):
        return self.w - 1 - x, self.h - 1 - y

    def view(self, v):
        units = []
        for u in v.units:
            x, y = self.rot(u["x"], u["y"])
            units.append({"team": SWAP[u["team"]], "kind": u["kind"], "x": x, "y": y, "count": u["count"]})
        units.sort(key=lambda u: (u["team"] != "Y", KIND_ORDER.get(u["kind"], 9), u["y"], u["x"]))
        blds = []
        for b in v.buildings:
            x, y = self.rot(b["x"], b["y"])
            blds.append({"id": self.to_c.get(b["id"], b["id"]), "x": x, "y": y, "type": b["type"],
                         "owner": SWAP.get(b["owner"], b["owner"]), "stage": b["stage"], "score": b["score"]})
        blds.sort(key=lambda b: b["id"])
        return View(v.turn, self.init, v.my_resource, v.opp_resource, units, blds)

    def out(self, cmd):
        t = cmd.split()
        if not t:
            return cmd
        op = t[0]
        try:
            if op == "SPAWN" and len(t) == 5:
                x, y = self.rot(int(t[3]), int(t[4]))
                t[3], t[4] = str(x), str(y)
            elif op == "MOVE" and len(t) == 6:
                x, y = self.rot(int(t[1]), int(t[2]))
                t[1], t[2], t[5] = str(x), str(y), FLIP.get(t[5], t[5])
            elif op == "MOVE2" and len(t) == 7:
                x, y = self.rot(int(t[1]), int(t[2]))
                t[1], t[2], t[5], t[6] = str(x), str(y), FLIP.get(t[5], t[5]), FLIP.get(t[6], t[6])
            elif op == "TELE" and len(t) == 7:
                x, y = self.rot(int(t[1]), int(t[2]))
                tx, ty = self.rot(int(t[5]), int(t[6]))
                t[1], t[2], t[5], t[6] = str(x), str(y), str(tx), str(ty)
            elif op == "PRIORITY":
                vals = t[1:]
                for i in range(0, len(vals) - 1, 2):
                    x, y = self.rot(int(vals[i]), int(vals[i + 1]))
                    vals[i], vals[i + 1] = str(x), str(y)
                t = [op] + vals
        except ValueError:
            return cmd
        return " ".join(t)
