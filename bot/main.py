"""깃발 대항전 메인 봇 (제출 진입 파일).

v12 채택: 호위 슬롯 1기만(ESCORT_SLOTS=1). 전선 집중(SURPLUS_PUSH)은 v10.4 상대 2%로 기각,
      말기 공격 조기·확대(20턴·5곳)는 48%로 중립이라 기존 15턴·3곳 유지.
v12 — (1) 호위 슬롯 선점 ESCORT_SLOTS: 적 W 가 ESCORT_TRIGGER_ETA 안인 F 에게 반경 2 이내 W 를 최대 N 기 동행
      (2) 여유 병력 전선 집중 SURPLUS_PUSH: F 목표당 호위 몫(SURPLUS_ESCORT_PER_F)을 채운 나머지 W 를 단일 전선 목표로
      (3) 말기 공격 조기·확대: ENDGAME_TURNS 15 -> 20, ENDGAME_TARGETS 3 -> 5

v10.4 — 2턴 함정 회피(TRAP_AVOID) + EOV(예상 점유 가치): hold = max(0, 적 F 도착 ETA - 아군 점령 ETA) 턴 동안의 점수를 목표 가치에 반영,
        적 소유 건물은 디나이얼 가치(상대 점수 박탈) 가산. 가중치는 EOV_W, EOV_CAP, DENIAL_W.

v10.3 — 경제 건물(HALL/ENG) 조기 수비: 적 F ETA<=4 경보, W 6칸 내 소집(일반 건물은 2/4 유지).
        원인(리플레이 10 맵): 양 진영 경제 건물이 본진에서 5~6칸 떨어진 구석 -> 기존 경보 2/소집 4로는 도착 전 탈취,
        후반 W 단가 3 vs 2로 생산 격차 붕괴. 탈환 가점(HOME_ECON_RETAKE)·수비 순서(ECON_FIRST)는 효과 없어 기본 꺼짐.

v10.2 — (1) 학생회관(HALL) 확보·탈환 가점 HALL_EXTRA_BONUS  (2) K 진영 정규화(canon.py): 180° 회전 + 팀 교환으로
        K 진영에서도 Y 진영과 정확히 같은 거울상 판단(낮은 인덱스 우선 동점 처리의 진영 편향 제거)

v10.1 — 공학관(ENG) 군사 경제: 미보유 시 확보 가점 ENG_BONUS, 수비 대상에 ENG 추가, 적 W 우세 시 F 생산 봉쇄 해제
        (리플레이 2: T15~20 공학관 상실 후 W 단가 3 vs 2 -> 생산량 격차로 붕괴. 새 시드 v9 상대 52.5% -> 76.5%)

v10 — 턴0 대규모 오프닝 빔 서치 · 동적 호위 계약 · 점령 후 연계 전환
  [1-A] 정적 보로노이 델타 D(x)=ETA_enemy-ETA_our, 건물별 점령 후 전환 타일 best_exit(Top3), F/W/F+W 레이스 표
  [1-B] opening.py: 5대 적 아키타입 x 5대 매크로, 빔 폭 32 · 깊이 12 롤아웃. 모듈 import 시점부터 soft 2100ms 가드,
        남는 시간은 적 모델 무작위 변형 반복 탐색 + 턴별 다수결. 결과 = OpeningPolicy(아키타입별 수순 + 강건 수순)
  [2]   오프닝 실행: 1~2턴 HARD(강건 수순) / 3~5턴 SOFT(관측 아키타입 수순) / 6턴~ 일반 AI.
        이탈 감지(적 W 본진 ETA<=3, 적 F 홈 학생회관 ETA<=4, 아군 F 목표에 적 W 우세)시 즉시 일반 AI
  [3-A] 호위 계약: 적 W 도달 칸은 W_req = 적 도달 W + ESCORT_EXTRA 가 커밋될 때만 진입. 경합 구역(D<2) 선택적 최소 호위
  [3-B] 점령 후 전환: 소유 건물 위 F는 best_exit(다음 목표 쪽·안전 타일)를 우선해 즉시 출발

v9 — F 생존율(RETREAT) · 교전 비율 기반 집결 · 핑퐁 억제 · 본진 방어 히스테리시스
  [B] 턴0 정적 전처리(soft 450ms / hard 550ms): APSP·첫 방향, 건물 경주 메타(F/W/S ETA, 보급소 WIN/CONTEST/LOSS),
      병목 코리더 빈도, 건물별 집결 타일(S1, S2)
  [C] W 전진은 이동 후 예상 병력비 R = W_our/(W_enemy+1) 로 결정: <1 진입 금지, 1~1.5 집결 대기, >=1.5 진입.
      집결 4턴 초과 시 목표 포기(RETARGET), 집결 칸이 열세로 위협받으면 후퇴
  [D] F: 전진 칸이 모두 위험하고 제자리도 위험하면 안전 칸(뒤쪽 포함)으로 RETREAT. 점령 후 목표가 없으면 건물에서 이탈
  [E] 본진 방어: capture_threat(적 F ETA<=2) / combat_threat(적 W ETA<=1 & 수비 F) 분리, 진입 2 / 해제 4 + 1턴 확인
  [F] 역방향 이동 감점(F 2.0 / W 1.2, 비상 시 0), A-B-A-B 왕복 2회 감지 시 목표 강제 해제, W TELE 최소 투입

v8 — 전술 기회 평가기(Tactical Opportunity Evaluator)
  Step 1) 캐시 계승(StateCache: 전 셀 BFS 거리/첫 방향, 점대칭 점수 복원) + 매 턴 위협 지도
          threat.enemy(1턴 내 적 W 도달 수) · enemy_w_eta / my_w_eta(다중 출발 BFS, O(N))
  Step 2) 후보 행동: CAPTURE · UNIVERSAL_SNIPE · DEFEND · INTERCEPT/HUNT_F · RETREAT
          고정 W 쿼터 폐지(홈 비상 쿼터만 유지), 홈 전담 F 폐지(SWEEPER_ENABLED=False)
  Step 3) 공통 점수 = 가치 x S(H) + 템포 - 이동 - 위험.  S(H)=H/(H+3), H=점령 후 버틸 턴(<=12)
          확정 사망(적 W 도달 가능 & 아군 W 0) 칸 진입은 거부, 부분 열세는 가치가 크면 감수
  Step 4) 히스테리시스: F는 새 점수 > 현재 + 2.0 이고 목표 유지 2턴 이상일 때만 교체
          (홈 비상·목표 소멸 시 즉시 교체), W는 지난 목표 유지
  Step 5) 점령 지불 불변식 R - P + I >= C (I=보장 수입, 보급소 보너스 제외) 안에서만 생산

v7 변경점 (로컬 공식 엔진으로 s5 상대 검증, 시드 10~49 양 진영)
  적용  1) 말기 공격: 남은 15턴부터 깃발병 상한 확대, 닿을 수 있는 상대 고득점 건물 3곳에 전투병 집중
  적용  2) 말기 수비: 적 깃발병이 도달 가능한 우리 2점 이상 건물에 (적 도달 W + 1)기 배치
  적용  4) 미래 생산: 홈 침투가 생산 거점 근처면 이번 턴 생산분으로 대응, 상시 홈 쿼터 해제
  비활성 3) 점령 후 유지 검사(HOLD_ENABLED): 켜면 승률 하락
  비활성 5) 경합 가산 비례화(CONTEST_SCALED): 효과 없음
  비활성 6) 적 경제 건물 습격(ECON_RAID_ENABLED): 켜면 승률 하락
  발동 드묾 7) 전투병 순간이동·병원 기습, 9) 정찰병 조건: 결과 변화 없음

v6 변경점
  1) 목표 도달 가능 조건 수정: 마지막 2턴에도 깃발병이 목표로 진입(d <= turns_left + 1)
  2) 보급소 보너스를 건물별로 추적(두 번째 보급소 +15, 요격도 건물별)
  3) 기본 수입으로 충당되는 점령비는 예약하지 않음
  4) 초반 안전할 때 깃발병 호위 조건 해제
  5) 상대 생산 위협 상한 6 → 실제 자원 기준
  6) 상대 역 순간이동(TELE) 위협과 도착 거리 반영
  7) 병원 수비 추가, 수비 병력 수를 위협만큼 모음, 홈 병원·역 탈환 최우선
  8) 경합 건물(광장 포함) 가산점
  9) 말기 모드: 상대 건물 중립화 가산점, 넓은 수비

구성
  StateCache       전 셀 쌍 BFS 거리/첫 방향 캐시, 건물 인덱스, 점수 기록·점대칭 복원
  ReservationBook  건물 ↔ 깃발병 uid 1:1 예약 (assign / unassign / reassign)
  ThreatAnalyzer   적·아군 전투병 도달 수와 NetCombat
  WarriorPool      턴 내 전투병 가용 수와 커밋(호위·사냥·방어·전진)
  ResourceManager  점령 예약금 → 생산 예산 → 생산 구성
  CommandBook      명령 검증(토큰·수량·지형·TELE 제약)과 병합 출력
  Brain            한 턴의 단계 실행
  decide           시간 예산과 예외 폴백

좌표는 내부적으로 셀 인덱스 idx = y * width + x 로 다룬다.
디버깅 stderr는 게임당 1 MiB 이내로 제한한다(LOG_LIMIT).
미공개 점수 -1은 실제 음수 점수가 아니다.
"""
from __future__ import annotations

import gc
import sys
import time
import traceback

T_IMPORT = time.perf_counter()   # v10: 턴0 시간 가드 기준(프로세스 기동 직후에 가장 가까운 관측 시점)


def _proc_age():
    """v16 Prime: import 시점의 프로세스 나이(초). 부하로 인터프리터 기동이 늦어진 시간을 턴0 예산에서 뺀다.
    Linux: /proc, Windows: GetProcessTimes. 실패하면 0(기존 동작)."""
    try:
        with open("/proc/self/stat") as f:
            start = int(f.read().rsplit(")", 1)[1].split()[19])      # starttime(부팅 후 clock tick)
        with open("/proc/uptime") as f:
            up = float(f.read().split()[0])
        import os
        return up - start / os.sysconf("SC_CLK_TCK")
    except Exception:
        pass
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.windll.kernel32
        c, e, kt, ut, now = (wintypes.FILETIME() for _ in range(5))
        if not k32.GetProcessTimes(ctypes.c_void_p(-1), ctypes.byref(c), ctypes.byref(e),   # -1 = 현재 프로세스
                                   ctypes.byref(kt), ctypes.byref(ut)):
            return 0.0
        k32.GetSystemTimePreciseAsFileTime(ctypes.byref(now))
        ft = lambda x: (x.dwHighDateTime << 32) | x.dwLowDateTime  # noqa: E731
        return (ft(now) - ft(c)) / 1e7
    except Exception:
        return 0.0


try:
    _AGE = min(1.2, max(0.0, _proc_age()))
except Exception:
    _AGE = 0.0
T_START = T_IMPORT - _AGE        # 프로세스 기동 시각(perf_counter 기준 추정)

from protocol import BALANCE, DIRS, spawn, move, move2, tele, priority, run
from protocol import parse_init, parse_turn, read_block
from search import directions
import opening
from canon import Canon

CFG = BALANCE
UNITS = CFG["units"]
CAP = CFG["capture"]
BLD = CFG["buildings"]
RES = CFG["resource"]
TELE_CFG = CFG["tele"]
TOTAL_TURNS = CFG["total_turns"]

INF = 10 ** 6
NEUTRAL = "N"
OPPOSITE = {"U": "D", "D": "U", "L": "R", "R": "L"}

# 시간 예산(초). 일반 턴 300ms 제한에 대해 180ms 안전 마진.
TURN_BUDGET = 0.200
FIRST_TURN_BUDGET = 0.550   # v9: 턴0 hard deadline

# True면 이번 턴 수입으로 충당 가능한 점령비는 예약하지 않는다(수입이 점령보다 먼저 들어오므로).
# 불변조건 1을 글자 그대로 지키기 위해 기본값은 False(보수적 예약).
RESERVE_NET_OF_INCOME = True   # v6: 기본 수입(10)만큼은 예약하지 않음(학생회관 수입은 전투로 잃을 수 있어 제외)

# Utility(B) = score * UTIL_SCORE_W / (dist + 1) + Bonus(B) - Penalty(B)
UTIL_DIST_POW = 1.0             # v27 실험: 효용 거리 할인 지수 score*W/(d+1)^p (1.0 = 기존과 동일)
UTIL_SCORE_W = 1.5             # v12.1: Phase A 튜닝(TUNE-A 60%, TUNE-B 55.5%, FINAL 랜덤 60.0% / 실제 47.5%)
BONUS_DEPOT = 10.0
BONUS_HALL = 5.0
BONUS_PLAZA = 4.0
BONUS_RETAKE = 3.0
PENALTY_RESERVED = 30.0
COORD_MODE = ""                 # v16 F-F 조율 실험: "" (pr_07), hard, soft, split, auction
COORD_SOFT_K = 40.0            #   soft: 선점 건물 감점 K/(d+1), PLAZA/DEPOT 면제(백업 진입 허용)
COORD_AUCTION_K = 8.0          #   auction: 늦은 F 감점 = K x (지연 턴 + 1)
PENALTY_ENEMY_FLAG = 3.0
PENALTY_THREAT = 1.0
STICKY_BONUS = 0.0   # v8: 히스테리시스로 대체

STUCK_LIMIT = 2
BAN_TURNS = 6
MAX_SCOUTS_BUILT = 2

# 깃발병 동시 운용 상한: 기본 3, 목표가 충분하면 4, 유휴 자원까지 있으면 최대 5.
MAX_FLAGS = 7                # v8: 5 -> 7 (로컬 대전 v5 상대 67% -> 84%)
BASE_FLAG_CAP = 5
IDLE_RESOURCE = 15
FLAG_ESCORT_W_MIN = 3        # F 추가 생산 전 필요한 W 수 = min(F 수, 이 값)

# 상위 병력 예산
REQUIRED_HOME_DEFENSE = 1
CENTER_DEFENSE_MIN = 2
CENTER_DEFENSE_RATIO = 0.5
SPECIAL_SQUAD = 2            # free_W 가 이 이상일 때만 특수 전술에 배정
INTERCEPT_MAX_ETA = 8        # 적 F가 보급소에서 이보다 멀면 "접근 중"으로 보지 않는다

# 홈 경제 슬롯 / 도서관 가치
HOME_ECON_TYPES = ("HALL", "LIBRARY")
HOME_ECON_SLOT_BONUS = 8.0
HALL_DECAY_TURNS = 60
LIB_PER_CAPTURE = 0.5        # 도서관 1회 할인 가치
LIB_TURNS_PER_CAPTURE = 8    # 예상 점령 주기
LIB_BONUS_CAP = 6.0
DEPOT_CONTESTED_FACTOR = 0.3  # 적 F가 먼저 도착하면 보급소 보너스 감쇄

# 병원 기습(기본 비활성)
HOSPITAL_RAID_ENABLED = False   # v4: 사용하지 않음(발동 빈도 낮음)

# 초반 홈 방어 해제: T <= EARLY_TURNS 동안 home 쿼터 0(전원 전선).
# 적 유닛(F/W/S)이 홈 구역 건물에서 HOME_ALERT_DIST 칸 안에 들어오면 비상 방어(침투 W 수, 1~HOME_ALERT_MAX_W).
EARLY_TURNS = 25
HOME_ALERT_DIST = 4
HOME_ALERT_MAX_W = 3

# 전투병 목표 유지: 지난 턴 전진 목표가 여전히 유효하면 재분배 없이 그대로 유지한다(advance 참고).

# 홈 전담 F(Home Sweeper): 홈 구역에 미점령 건물이 있으면 F 1기를 홈 순회 전용으로 고정한다.
# 목표 비용 = 거리 - 유형 가중치(HALL > ENG > LIBRARY > 기타) - 현재 목표 유지 가점.
SWEEPER_TYPE_WEIGHT = {"HALL": 6.0, "ENG": 4.0, "LIBRARY": 2.0}
SWEEPER_STICKY = 3.0
SWEEPER_MIN_FLAGS = 2        # F가 이 수 이상일 때만 새로 지정(최소 1기는 전선)
RAID_STATION_RANGE = 3
RAID_DEFENSE_RANGE = 2
RAID_MIN_FREE_W = 2
RAID_BONUS = 6.0
SCOUT_MIN_TURNS_LEFT = 30
SCOUT_START_TURN = 20          # v16f2: 오프닝 S 미생산 — 이 턴 이후에만 정찰병 생산(v16f: 2)
SCOUT_MIN_RES = 8              # v16f2: 생산 가능 자원이 이 이상일 때만 S 생산(생존 S 0기일 때 1기)
# ---- v17 모듈 스위치(기본 꺼짐 = v16f2 와 동일). persona_cfg.py 가 켠다.
MOD_HOSP = False               # A1 전진 병원 W 생산: 병원 안전(적 F 거리·적 W ETA > HOSP_SAFE_ETA) + 병원->전선 < 본진->전선
HOSP_SAFE_ETA = 3              #   전선 = 공격 F 목표(없으면 점령 가능 건물)
MOD_TELE_COND = False          # A2 조건부 W 순간이동: 목표 칸 결손(필요 W - 도착 예정 W) >= TELE_DEFICIT_MIN 일 때만
TELE_DEFICIT_MIN = 3
MOD_AMBUSH = False             # A3 길목 요격 확장: 경제 건물뿐 아니라 모든 비적 소유 건물로 향하는 적 F 를 엄격 조건으로 요격
MOD_SURGE = False              # A4 ENG W 집중: 공학관 보유 중엔 F 상한을 max(현재 F, BASE_FLAG_CAP)로 묶고 남는 예산을 W 로
MOD_GUILLO = False             # A5 적 경제 차단: 적 재점령 ETA >= GUILLO_MIN_ETA 인 고립 적 ENG 에 가점
GUILLO_MIN_ETA = 3
GUILLO_MAX_D = 6
GUILLO_BONUS = 6.0
MOD_FLANK = False              # A6 소규모 측면: F >= FLANK_MIN_F 일 때 F FLANK_N 기를 적 진영·적 W 먼 건물 쪽으로
FLANK_N = 1
FLANK_MIN_F = 4
FLANK_EW_ETA = 4
FLANK_BONUS = 6.0
# ---- v18 모듈 스위치(기본 꺼짐 = v17_B1 과 동일)
MOD_META = False               # [A] 상대 압력 H/E/C(0~1) 소프트 가산 + 히스테리시스(ON >= 0.5 / OFF <= 0.2) + 중앙 결손 감점
META_K = 3.0                   #   ON 일 때 가점 = META_K x 압력
META_LAMBDA = 2.0              #   병원/홈 목표 감점 = LAMBDA x C (중앙 압력 ON 일 때)
MOD_DYN_ECON = False           # [A] HALL = max(1, 6(160-t)/160), ENG = 4 + min(5, 0.5 max(0, W-4))
MOD_ESCAPE = False             # [B] F 3단계: GREEN 진입 / YELLOW(동시 도달) 탈출 칸 있으면 진입 / RED 후퇴 -> 측면 -> 스테이징
MOD_RADAR = False              # [C] 거점 반경 5 적 W >= RADAR_MIN 접근 시 경보 + 스크린 선집결
RADAR_MIN = 4
MOD_TRADE = False              # [C] 방어 불가(여유 W < 적+1) 거점은 포기, 반대편(경보 중심에서 7+) 적/중립 건물 가점
TRADE_BONUS = 4.0
MOD_CHECKMATE = False          # [D] 적 보유 건물 <= CM_MAX 이고 우리 점수 >= 총점 x CM_SCORE 면 적 건물 전부 표적(즉시 승리 가속)
CM_MAX = 3
CM_SCORE = 0.35
CM_BONUS = 12.0
MOD_HOSP_RUSH = False          # 샌드백(KtAIger형): 병원 최우선 + 병원 전진 생산(안전 무시)
HR_BONUS = 12.0
# ---- v17c 핀셋 모듈(기본 꺼짐 = v17_B1)
MOD_DINT = False               # [TEST_1] T1~T5 시그니처 확정 후, 적 F 가 1턴 뒤 밟을 건물 칸에 W 1(호위 1기면 2)기를 같은 턴에 겹쳐 즉사시킴
DINT_TYPES = ("HOSPITAL", "ENG", "HALL", "STATION", "DEPOT")
DINT_SIG_TURNS = 5
MOD_CTRADE = False             # [TEST_2] 시그니처 = HOSPITAL_RUSH 면 병원에서 먼 빈 고가 건물(점수 >= 3, 적 F ETA >= 3) F 가점
CTRADE_BONUS = 5.0
# ---- v17b2 점령 후 이탈 1턴 Veto (기본 꺼짐 = v17_B1)
MOD_VETO = False               # 아군 소유 건물 위 F 가 떠나려 할 때: 적 F 2칸 내 & 칸 도달 적 W <= 아군 W(인접 W 로 보충 가능) 면 1턴 잔류
VETO_F_DIST = 2
VETO_DEPOT_DIST = 3            #   적이 아직 +15 를 받지 않은(한 번도 보유한 적 없는) DEPOT 은 적 F 3칸까지 경계
# ---- 샌드백: 하이에나(점령 직후 빈집털이)
MOD_HYENA = 0                  # 1 순수 / 2 F+W 동반 / 3 페이크(1턴 대기 후 선회) / 4 양동(탐지 반경 확대)
HY_BONUS = 15.0
# ---- v17b3 W 1기 알박기 (기본 꺼짐 = v17_B1)
MOD_ANCHOR = False             # 아군 소유 건물을 떠나는 F: 적 F 2칸 내면 그 칸에 W 1기만 1턴 잔류(F 는 그대로 전진)
ANCHOR_F_DIST = 2
ANCHOR_W_MAX = 1               # v19: 알박기 W 상한(칸 도달 적 W 가 1기면 2기까지 허용하려면 2)
MOD_GUARD_ALL = False          # v19: F 이탈과 무관하게, 적 F 가 ANCHOR_F_DIST 이내인 '비어 있는' 아군 건물 전부에 W 1기(인접 W 만)
MOD_GARRISON = False           # v20: 소유 홈 HALL/ENG 마다 W GARRISON_W 기 상주(적 유무 무관, 반경 GARRISON_PULL 의 W 로 채움)
GARRISON_W = 1
GARRISON_PULL = 3
GARRISON_TYPES = ("HALL", "ENG")
COORD_STEAL_MARGIN = 0         # v19: 경매 탈취 조건 d + margin < d_holder (0 = v17b1, -1 = 동률도 탈취, 1 = 2칸 이상 가까울 때만)
# ---- v18 6대 전술 모드 라우터 (MOD_MODES=False 면 v17b1 과 동일)
MOD_MODES = False
P1_DEPOT_RACE_WEIGHT = 4.0     # [1 OPENING_RACE] T1~T12 미수령 DEPOT 가점(PLAZA 는 절반)
P2_ANCHOR_W_MAX = 1            # [3 LOCAL_GUARD] 알박기 W 상한(칸 도달 적 W 가 이보다 많으면 알박기 안 함)
P3_DEATHBALL_TRIGGER_W = 12    # [4 COUNTER_DEATHBALL] 3x3 적 W 합 임계
P4_EMERGENCY_DIST = 2          # [5 BASE_EMERGENCY] 적 유닛 -> 아군 홈 HALL/ENG 거리 임계(성채 경보 거리로도 사용)
P5_ENDGAME_TRIGGER_TURN = 150  # [6 ENDGAME_LOCK] 이 턴 이후 + 점수 리드면 굳히기
P6_UTIL_SCORE_W = 1.5          # 전체 거점 가중치(UTIL_SCORE_W 로 적용)
OPENING_RACE_TURNS = 12
DB_AVOID_DIST = 3              # [4] 집결 중심 3칸 이내 목표 감점, 7칸 이상 비아군 건물 가점
DB_AVOID_PEN = 6.0
DB_RAID_DIST = 7
DB_RAID_BONUS = 6.0
LOCK_FAR = 4                   # [6] 굳히기: 거리 4 초과 비아군 목표 감점 1.5 x (d-4)
LOCK_PEN = 1.5
DB_DWELL = 2                   # [4] 집결 경보 유지 턴
DEBUG_MODES = False           # True 면 LOCAL_GUARD 발동도 stderr 로그
RUSH_MIN_ENEMY_W = 3
RUSH_MARGIN = 99              # v10: 적 W 우세 시 F 생산 봉쇄 해제(데스볼 mock 91%->96%, v9 상대 중립)
RUSH_F_FLOOR = 1               # 적 W 우세(러시) 중에도 이 수 미만이면 F 보충. v5~v10 기본 1(=F 0일 때만)
ENEMY_SPAWN_CAP = 6
DEFEND_ALERT_DIST = 2
DEFEND_PULL_DIST = 4
LOAD_WEIGHT = 3
KEY_DEFEND = ("HALL", "STATION", "PLAZA", "HOSPITAL")
# v6 추가 파라미터
NO_ESCORT_TURNS = 12          # 이 턴까지는 적 W가 멀면 F 호위 조건 해제
NO_ESCORT_SAFE_DIST = 5       # 아군 본진·F에서 적 W까지 최소 거리
BONUS_CONTEST = 3.0           # 양측 도착 턴 차이 <= 1 인 비홈 건물(광장 포함)
BONUS_HOME_CRITICAL = 15.0    # 상대가 소유한 우리 진영 병원·역 탈환
HOME_CRITICAL_TYPES = ("HOSPITAL", "STATION")
ECON_TYPES = ("HALL", "ENG")    # v10.2: 군사 경제 건물(수입 +2 / W 단가 -1)
ECON_ALERT_DIST = 4           # v10.3: 경제 건물 수비 조기 경보(적 F ETA). 기존 2 (점령 2단계라 2턴 여유 활용)
ECON_PULL_DIST = 6            # v10.3: 경제 건물 수비에 끌어올 W 거리. 기존 4
ECON_FIRST = False            # v10.2: 수비 순서에서 경제 건물 우선
HOME_ECON_RETAKE = False      # v10.2: 우리 진영 HALL/ENG 탈환을 HOME_CRITICAL 수준으로
ENDGAME_TURNS = 15            # v7: 남은 턴이 이 이하이면 말기 모드(공격·수비). v12 실험: 20
ENDGAME_NEUTRALIZE_W = 10.0   # v7: 말기에 도달 가능한 상대 건물: 점수 x 이 값 가산
ENDGAME_FLAG_EXTRA = 8        # v7: 말기 시작 이 턴 전부터 깃발병 상한 확대
ENDGAME_FLAG_CAP = 7
ENDGAME_TARGETS = 3           # v7: 말기 전투병 공격 목표 수(상대 고득점 건물). v12 실험: 5
ENDGAME_DEF_RANGE = 6
CONTEST_SCALED = False         # v7 5번: 실험 결과 효과 없음(60%→60%)
ECON_RAID_ENABLED = False      # v7 6번: 켜면 승률 하락(60%→45%)
ECON_RAID_BONUS = {"HALL": 5.0, "ENG": 4.0, "HOSPITAL": 4.0}
HOLD_ENABLED = False   # v7 실험: 켜면 승률 하락(60%→47.5%)해 비활성
FUTURE_PROD_ENABLED = True
HOLD_RADIUS = 2               # v7: 점령 후 유지 검사 반경(턴)
HOLD_PENALTY = 1.5            # v7: 유지 여유가 음수일 때 1기당 감점
HOLD_SKIP = -4                # v7: 유지 여유가 이보다 나쁘면 목표 제외
OWN_SPAWN_CAP = 20            # v7: 우리 생산 가능량 상한(자원 40 / 단가 2)
HOME_SPAWN_NEAR = 2           # v7: 본진·병원에서 이 거리 안의 침투는 즉시 생산으로 대응         # v7: 말기 수비가 반응하는 적 깃발병 도착 거리 상한
# ---- v8 파라미터
SWEEPER_ENABLED = True        # 로컬 대전: 끄면 v5 상대 15% → 켜면 65%
TAU = 1.0                     # S(H) = H / (H + TAU). 로컬 대전: 3.0보다 1.0이 우세
H_MAX = 12
COVER_H_BONUS = 4             # 아군 W가 같은 시각에 도착 가능하면 H 가산
HYST_F = 2.0
HYST_F_AGE = 2
SNIPE_ENABLED = True
SNIPE_VALUE = 12.0            # 우선순위 정렬용
RISK_ACCEPT = 6.0             # 부분 열세 칸 진입을 감수할 최소 가치
EARLY_RUSH_TURNS = 6
EARLY_DEPOT_BONUS = 6.0
EARLY_CENTER_BONUS = 2.0
INTERCEPT_ENABLED = False     # 로컬 대전: 고가치 일반화 인터셉트는 승률 하락(67.5%→50%)
INTERCEPT_DEPOT_ONLY = True
INTERCEPT_MAX = 2             # 한 턴 인터셉트 임무 수
INTERCEPT_SQUAD = 2
DEFEND_TYPES = ("HALL", "STATION", "PLAZA", "HOSPITAL", "DEPOT")
# ---- v10 파라미터
T0_SOFT = 1.000                # v12.1 최종: 모듈 import 기준 오프닝 탐색 종료(1.5s -> 1.0s, 기계 정지·부하 대비 안전 마진)
T0_HARD = 1.350                # v16 Prime: 프로세스 기동 기준 첫 턴 전체 종료(1.7 import 기준 -> 1.35 기동 기준, 목표 <= 1.5s)
OPENING_ENABLED = True
OPENING_HARD_TURNS = 2
OPENING_SOFT_TURNS = 5
DEBUG_STAY = 0                # 진단용: V12_DEBUG_STAY=1 이면 노출된 대기 로그
TRAP_AVOID = True             # v10.4: 2턴 함정 회피(진입 후 다음 턴 탈출 칸이 없는 칸은 후순위). F 사망 -16%
ESCORT_SLOTS = 1              # v12: F 당 전담 호위 W 최대 수. v10.4 상대 56%(튜닝) / 68%·58%(새 시드 랜덤·실제)
ESCORT_ORDER = "util"          # v27: 호위 배정 순서 "util"(기존) / "danger" / "capture"
ESCORT_RADIUS = 2             # v12: 호위로 뽑을 W 의 F 까지 최대 거리(먼 W 역주행 금지)
ESCORT_TRIGGER_ETA = 3        # v12: F 다음 칸까지 적 W ETA 가 이 이하일 때만 예약(99 = 항상)
SURPLUS_PUSH = False          # v12: 여유 W 를 단일 전선 목표로 집중
SURPLUS_ESCORT_PER_F = 3      # v12: 전선 집중 전에 F 목표 하나당 남겨 둘 W
TRAP_SPAWN = False            # v10.4: 함정 판정에 적 생산 거점(생산 즉시 이동)까지 포함할지
EOV_W = 6.0                   # v10.4: EOV 가중치. 함정 회피와 함께 v9 상대 75.5% -> 81.7% (3개 시드 세트, 600경기)
EOV_CAP = 30                  # v10.4: 유지 턴 상한(이후는 불확실하므로 포화)
DENIAL_W = 0.0                # v10.4: 3.0이면 v9 상대 54.5%로 급락 -> 끔. 적 소유 건물 디나이얼 가치 = DENIAL_W x score x min(잔여턴, EOV_CAP)/EOV_CAP
HALL_EXTRA_BONUS = 0.0        # v10.2: 학생회관 미보유 시 확보 가점, 적 소유면 절반(탈환). 실험 결과는 보고서 참고
HALL_DEFEND = True            # v10.2: 학생회관 수비(KEY_DEFEND, v5부터 기본 포함) 끄기 실험용
CANON_ENABLED = True          # v10.2: K 진영 정규화
ENG_BONUS = 6.0               # v10: 공학관 확보/탈환 가점
ENG_DEFEND = True
MACRO_BONUS = 1.5             # 로컬 대전: 4.0이면 오프닝이 v9 상대 승률을 58% -> 51%로 깎음
# 데스볼 카운터(리플레이 2·8: 3x3 클러스터 25~33 W 전선)
DEATHBALL_ENABLED = True
DB_THRESHOLD = 20             # 3x3(체비쇼프 1) 적 W 합. 8이면 중반 모든 상대가 걸려 오작동(v9 상대 0.8%)
DB_RANGE = 4                  # 공 중심에서 아군 건물·본진까지 이 거리 이내면 활성
DB_MASS_ENABLED = False       # 맞불 집결: 켜면 v9 상대 0~27%로 붕괴(전군 후퇴 효과) -> 비활성
DB_MASS_RATIO = 0.8           # 맞불 집결: 도달 가능한 아군 W >= 공 크기 x 이 비율일 때만
DB_F_NEAR = 2                 # 공 중심 이 거리 이내 목표는 F 감점
DB_F_PENALTY = 6.0
DB_FLANK_DIST = 6             # 공에서 이 거리 이상 떨어진 목표는 측면 우회 가점
DB_FLANK_BONUS = 2.0
DEV_W_BASE_ETA = 3
DEV_F_HALL_ETA = 4
ESCORT_EXTRA = 0               # 1이면 W_req = 적 + 1 (엄격). 0이면 동수(전투병 상쇄 후 F 생존)
ESCORT_CONTESTED_MIN = 0       # 경합 구역(D<2) 진입 시 가용하면 붙이는 최소 호위(차단하지 않음)
TRANSITION_ENABLED = True
MACRO_TYPES = {
    "OPEN_HALL_F2": ("HALL",),
    "OPEN_DEPOT_FAST": ("DEPOT",),
    "OPEN_CENTER_CONTEST": ("PLAZA", "WATCH", "DEPOT", "STATION"),
    "OPEN_STATION_TELE": ("STATION",),
    "OPEN_SAFE_DEFENSIVE": (),
}

# ---- v9 파라미터
FIRST_SOFT = 0.450
FIRST_HARD = 0.550
RETREAT_ENABLED = True
EVAC_ENABLED = True
STAGING_ENABLED = False       # 로컬 대전: 켜면 v8 상대 40.8%, 끄면 60.8%
STAGE_RETREAT_ENABLED = False # 로컬 대전: 끄면 54.2% -> 60.8%
HOME_HYST_ENABLED = True
R_ENTER = 1.5
R_STAGE = 1.0
STAGING_TIMEOUT = 4
W_GOAL_BAN = 6
REV_PEN_F = 2.0
REV_PEN_W = 1.2
THRASH_LIMIT = 2
HOME_ENTER_ETA = 2
HOME_EXIT_ETA = 4
HOME_CONFIRM = 1
TELE_W_ENABLED = True
DEPOT_LOSS_FACTOR = 0.3
# ---- v16 전략 브랜치 스위치(기본 모두 꺼짐 = v12.1 과 동일). 브랜치 폴더의 persona_cfg.py 가 켠다.
# [A] 경제 성채: 아군 홈 HALL/ENG 만 사수. 적 F 가 FORT_ALERT_DIST 이내면 칸 도달 적 W E 에 대해 D >= E + 1 인 최소 W 를 칸 위로.
ECON_FORTRESS = False
FORT_ALERT_DIST = 3
FORT_PULL_DIST = 3
FORT_E2_R = 2                  # v35: E2 반경
DEF_E2 = 0                     # v35: 일반 수비(defend) 필요 W 에도 반경 DEF_E2 적 W 선계산(0 = 끔)
GAR_E2 = 0                     # v35: 수비대 필요 W = max(GARRISON_W, 반경 GAR_E2 적 W + 1) (0 = 끔)
FORT_TYPES = ("HALL", "ENG")    # v35: 성채 대상 유형
FORT_ALL = False               # v35: 홈 건물만이 아니라 소유 건물 전체
# ---- v41 (friend h_r4 이식, 기본 꺼짐)
TT_W = 0.0                    # 1) 시간표: 깃발병 목표에 (도착+TT_H 턴까지 적이 모을 병력 - 우리) x TT_W 감점 (0=끔)
TT_H = 2
TT_CAP = 8.0
TT_SPAWN = True               # 시간표에 본진·병원 생산 가능량(현재 자원 + 수입 누적) 포함
EG_TT = False                 # 2) 말기 공격 목표를 '160턴까지 우리가 더 많이 모을 수 있는 곳'으로 제한·정렬
STV_ENABLED = False           # 상대 경제 시설 탈취 가산(안전도로 깎이지 않게 최종 점수에 더함)
STV_HALL = 12.0               # 상대 학생회관
STV_ENG_SOLE = 20.0           # 상대의 유일한 공학관
STV_ENG = 6.0                 # 상대가 2개 가진 공학관 중 하나
STV_HOSP = 8.0                # 상대 병원
SCORE_EARLY_T = 0             # 이 턴까지 건물 점수 항목을 SCORE_EARLY_W 배로 줄임(0=끔)
SCORE_EARLY_W = 0.0
CW_ENABLED = False            # 전선 축소: 우리 진영 밖 비경제 건물(중앙)의 목표 가중치를 시간에 따라 바꿈
CW_EARLY = 0.3
CW_LATE = 1.0
CW_T1 = 20                    # 이 턴까지 CW_EARLY, 이후 10턴 동안 CW_LATE 로 서서히
CW_STATE = False              # True 면 '우리 진영 경제 시설·보급소를 모두 확보한 턴'부터 전환(최대 CW_T1)
HG_MARGIN = 0                  # v40 사냥 회피: F 다음 칸 j 반경 HG_R 적 W - 반경 HG_R-1 아군 W >= HG_MARGIN 이면 1차 패스에서 제외(0 = 끔)
HG_R = 2
HG_TARGET = False              # True 면 목표 칸(점령 칸)에도 적용
HUNT_EXT = False               # v39 (friend h_r4): 적 F 호위(1칸)보다 HUNT_MARGIN 이상 모을 수 있으면 HUNT_RANGE 칸 밖 W 도 추격
HUNT_RANGE = 2
HUNT_ESC_R = 1                 # v41: 적 F 호위로 셀 반경
HUNT_SPAWN = False             # v41: 적 F 반경 1 에 이번 턴 적 생산 가능 W(본진/병원 인접)도 호위로 계산
HUNT_MARGIN = 1
FORT_E2 = False                # v34: 성채 필요 W = max(도달 위협, 반경 2 적 W) + 1 (friend v17c)
FORT_FLAG_HOLD = False         # 홈 HALL/ENG 위 F: 적 F 2칸 이내 & 칸 적 W 위협 0 일 때만 농성
SCOUT_EVAC = False             # 아군 건물 위 S: 적 F 2칸 이내면 즉시 이탈(S 는 점령을 막지 못한다)
# [B] 초고속 보급소 선점 & 중앙 템포
DEPOT_RUSH = False
DEPOT_RUSH_TURNS = 8
DEPOT_RUSH_BONUS = 30.0
DEPOT_CENTER_TURNS = 12        # 보급소 보너스 입금 후 이 턴 동안 중앙 건물로 F·W 전선 집중
DEPOT_CENTER_F_BONUS = 6.0
# [C] 상대 경제 F 길목 인터셉트
ROUTE_INTERCEPT = False
RI_MAX_ETA = 8                 # 적 F 가 경제 건물에서 이보다 멀면 무시
RI_HOLD = 2                    # 확신이 끊긴 뒤 임무 유지 턴(히스테리시스)
RI_STRICT = False              # v16_AC 정밀화: 아래 3개 제약을 켠다(끄면 v16_C 와 동일)
RI_CONF_DIST = 3               #   확신 = 2턴 연속 접근 + 경제 건물까지 최단 거리 <= 이 값
MAX_INTERCEPT_W = 2            #   적 F 1기당 임무 1개, 파견 W 최대(적 호위 + 1 을 이 수로 못 채우면 발동 안 함)
                               #   이번 턴 누적 파견은 free_W(총 W - 홈 - 중앙 방어 몫) 이하
# [D] 분산 박스 호위(1위 모방): F 3~4기 고정 + F 당 호위 W 4~6기 + 측면 차단
BOX_ESCORT = False
BOX_FLANK = 2                  # F 다음 칸의 위협 쪽 이웃 칸에 두는 측면 W
# [D-True] 1위 팀(0928 1.json) 전진 스크럼: F 5기 캡 오프닝 + W 1선 장벽(Frontier Band) + Quota 컨베이어
FRONTIER_MODE = False
F_CAP_TOTAL = 5                # T1 F2, T2~T4 F1 = 5기. 이후 F 생산 영구 중단
F_OPEN_TURNS = 4
BAND_DEPTH = 2                 # 목표 건물 G 에서 적 본진 쪽 1~2칸
BAND_MAX = 4                   # G 당 장벽 칸 수 상한
CONVEYOR = True                # 부족분이 남은 장벽 칸으로 후방 W 계속 충원
# [D2] 안전 강화 3종
HOSP_FORWARD = False           # 조건부 병원 전진 생산(적 F ETA > 3, 적 W ETA > 2, 병원->장벽 거리 < 본진->장벽)
BAND_COMPRESS = False          # 장벽 폭을 G 적 쪽 이웃 칸 수(지형 폭)에 맞춰 1~2칸으로 압축
POCKET = False                 # 장벽 W 가 quota + POCKET_SURPLUS 이상인 칸에만 F 1턴 중첩 허용
POCKET_SURPLUS = 2
# [D3] 팔랑크스 스택: F 가 밟는 칸에 W 를 같은 턴에 겹쳐 진입(적 도달 W + PHALANX_EXTRA), 잉여 W 는 부족한 F 스택으로 합류
PHALANX_MODE = False
PHALANX_EXTRA = 2
STACK_TARGET = 8               # 공격 F 스택 목표 인원(보충 기준)
PHALANX_OPENING = True         # True: 1위 팀 오프닝(F 5기 캡 + W 올인). False: v12.1 생산 유지(Dx)
import os as _os
DEBUG = int(_os.environ.get('V12_DEBUG', '0'))
LOG_LIMIT = 900_000
LOG_EVERY = 20


# 실험용 환경변수 덮어쓰기(V12_<이름>=값). 제출 환경에서는 설정되지 않으므로 영향 없음.
for _k in [k for k in list(globals()) if k.isupper()]:
    _v = _os.environ.get("V12_" + _k)
    if _v is not None:
        try:
            globals()[_k] = type(globals()[_k])(eval(_v)) if not isinstance(globals()[_k], bool) else _v in ("1", "True")
        except Exception:
            pass

# ---- v16 브랜치 폴더별 설정(persona_cfg.py). 없으면 v12.1 과 동일.
try:
    from persona_cfg import OVERRIDES as _PERSONA
    for _k, _v in _PERSONA.items():
        globals()[_k] = _v
except ImportError:
    pass


if MOD_MODES:
    UTIL_SCORE_W = P6_UTIL_SCORE_W
    FORT_ALERT_DIST = P4_EMERGENCY_DIST


# ------------------------------------------------------------------ 공용

_log_bytes = 0


def log(msg):
    """stderr 로그. 게임 누적 LOG_LIMIT 바이트를 넘으면 버린다."""
    global _log_bytes
    if _log_bytes >= LOG_LIMIT:
        return
    data = msg if msg.endswith("\n") else msg + "\n"
    _log_bytes += len(data.encode("utf-8", "replace"))
    try:
        sys.stderr.write(data)
    except Exception:
        pass


class Clock:
    def __init__(self, budget):
        self.t0 = time.perf_counter()
        self.budget = budget

    def elapsed(self):
        return time.perf_counter() - self.t0

    def over(self):
        return self.elapsed() > self.budget


def capture_cost(btype, own_library):
    cost = CAP["capture_cost"] * (CAP["plaza_multiplier"] if btype == "PLAZA" else 1)
    if own_library:
        cost -= BLD["library_discount"]
    return max(CAP["min_capture_cost"], cost)


# ------------------------------------------------------------------ A. 캐시

class StateCache:
    """맵 고정 정보. 첫 턴에 한 번 만든다."""

    def __init__(self, init):
        self.init = init
        w, h = init.width, init.height
        self.w, self.h, self.n = w, h, w * h
        self.passable = [init.passable(i % w, i // w) for i in range(self.n)]

        order = directions(init)
        nbrs = []
        for i in range(self.n):
            lst = []
            if self.passable[i]:
                x, y = i % w, i // w
                for d in order:
                    dx, dy = DIRS[d]
                    if init.passable(x + dx, y + dy):
                        lst.append((d, (y + dy) * w + x + dx))
            nbrs.append(tuple(lst))
        self.nbrs = nbrs

        # dist[src][dst], step[src][dst] (src 에서 dst 로 가는 첫 방향)
        self.dist = [None] * self.n
        self.step = [None] * self.n
        for s in range(self.n):
            if self.passable[s]:
                self.dist[s], self.step[s] = self._bfs(s)

        self.bpos = {}
        self.btype = {}
        self.bid_at = {}
        for b in init.buildings:
            i = b["y"] * w + b["x"]
            self.bpos[b["id"]] = i
            self.btype[b["id"]] = b["type"]
            self.bid_at[i] = b["id"]
        self.mirror = {}
        for bid, i in self.bpos.items():
            m = self.bid_at.get((h - 1 - i // w) * w + (w - 1 - i % w))
            if m is not None:
                self.mirror[bid] = m
        self.base = {t: p[1] * w + p[0] for t, p in init.bases.items()}

        # 지역 축: 두 본진이 더 크게 벌어진 축(기본 x). 신촌/안암 1.5, 중앙 3.0.
        by, bk = init.bases["Y"], init.bases["K"]
        self.axis = 0 if abs(by[0] - bk[0]) >= abs(by[1] - bk[1]) else 1
        lo, hi = CFG["regions"]["center"]
        mg = CFG["mapgen"]
        center_mean = sum(mg["center_building_score"]) / 2.0
        side_mean = sum(mg["sinchon_building_score"]) / 2.0
        self.prior = {}
        for bid, i in self.bpos.items():
            coord = (i % w) if self.axis == 0 else (i // w)
            self.prior[bid] = center_mean if lo <= coord <= hi else side_mean

        self.observed = {}   # 직접 공개된 점수
        self.known = {}      # 직접 공개 + 점대칭 복원

    def _bfs(self, s):
        dist = [INF] * self.n
        step = [None] * self.n
        dist[s] = 0
        nbrs = self.nbrs
        q = [s]
        for i in q:  # 리스트 순회 중 append 로 큐를 대신한다
            nd = dist[i] + 1
            si = step[i]
            for d, j in nbrs[i]:
                if dist[j] == INF:
                    dist[j] = nd
                    step[j] = d if i == s else si
                    q.append(j)
        return dist, step

    def multi_bfs(self, sources):
        """sources: {idx: 시작 거리}. 전 셀 최단 도착 턴 수(O(N))."""
        dist = [INF] * self.n
        buckets = {}
        for i, d0 in sources.items():
            if self.passable[i] and d0 < dist[i]:
                dist[i] = d0
                buckets.setdefault(d0, []).append(i)
        nbrs = self.nbrs
        for d in sorted(buckets):
            q = [i for i in buckets[d] if dist[i] == d]
            for i in q:
                nd = dist[i] + 1
                for _, j in nbrs[i]:
                    if nd < dist[j]:
                        dist[j] = nd
                        q.append(j)   # 같은 레벨 이후 레벨로 퍼진다(BFS 단조)
        return dist

    def d(self, a, b):
        row = self.dist[a]
        return INF if row is None else row[b]

    def xy(self, i):
        return i % self.w, i // self.w

    def cheb(self, a, b):
        return max(abs(a % self.w - b % self.w), abs(a // self.w - b // self.w))

    def update_scores(self, view):
        for b in view.buildings:
            s = b["score"]
            if s is None or s < 0:
                continue
            bid = b["id"]
            self.observed[bid] = s
            self.known[bid] = s
        for bid, s in self.observed.items():
            m = self.mirror.get(bid)
            if m is not None and m not in self.observed:
                self.known[m] = s

    def score(self, bid):
        if self.btype.get(bid) == "PLAZA":
            return BLD["plaza_score"]
        s = self.known.get(bid)
        return s if s is not None else self.prior.get(bid, 1.5)

    def revealed(self, bid):
        return self.btype.get(bid) == "PLAZA" or bid in self.known


# ------------------------------------------------------------------ [B] 턴0 정적 메타

class StaticMeta:
    """턴0 정적 전처리. 캐시(APSP) 위에서 건물 경주·병목·집결 타일을 계산한다. soft deadline 초과 시 남은 단계 생략."""

    def __init__(self, cache, team, clock):
        c = cache
        opp = "K" if team == "Y" else "Y"
        mb, ob = c.base[team], c.base[opp]
        self.race = {}        # bid -> dict(f_our, f_opp, s_our, s_opp, depot)
        self.choke = {}       # idx -> 최단 경로 통과 빈도
        self.staging = {}     # bid -> [S1, S2]
        self.complete = False
        # [1-A] 정적 보로노이 델타: D(x) = ETA_enemy(x) - ETA_our(x)  (본진 기준, 양수 = 아군 쪽)
        self.delta = [c.d(ob, x) - c.d(mb, x) if c.passable[x] else 0 for x in range(c.n)]
        self.best_exit = {}
        for bid, bi in c.bpos.items():
            fo, fe = c.d(mb, bi), c.d(ob, bi)
            r = {"f_our": fo, "f_opp": fe, "w_our": fo, "w_opp": fe, "fw_our": fo, "fw_opp": fe,
                 "s_our": (fo + 1) // 2, "s_opp": (fe + 1) // 2}
            if c.btype[bid] == "DEPOT":
                r["depot"] = "WIN" if fo < fe - 1 else ("CONTEST" if abs(fo - fe) <= 1 else "LOSS")
            self.race[bid] = r
        if clock.elapsed() > FIRST_SOFT:
            return
        keys = [mb, ob] + list(c.bpos.values())
        for i, a in enumerate(keys):
            if clock.elapsed() > FIRST_SOFT:
                return
            for b in keys[i + 1:]:
                if c.d(a, b) >= INF:
                    continue
                cur = a
                for _ in range(64):
                    if cur == b:
                        break
                    d = c.step[cur][b]
                    cur = next(j for dd, j in c.nbrs[cur] if dd == d)
                    if cur != b:
                        self.choke[cur] = self.choke.get(cur, 0) + 1
        for bid, bi in c.bpos.items():
            ring = [j for j in range(c.n) if c.passable[j] and 1 <= c.d(bi, j) <= 2 and j not in c.bid_at]
            ring.sort(key=lambda j: (c.d(bi, j), -c.d(ob, j), c.d(mb, j), j))
            self.staging[bid] = ring[:2]
        # [1-A] 점령 후 전환 타일 Top3: 인접 칸 중 (다음 거점까지 거리 - 안전 가중) 최소
        for bid, bi in c.bpos.items():
            others = [p for b2, p in c.bpos.items() if b2 != bid]
            cand = []
            for _, j in c.nbrs[bi]:
                nxt = min((c.d(j, p) for p in others), default=0)
                cand.append((nxt - 0.5 * max(-2, min(self.delta[j], 4)), j))
            cand.sort()
            self.best_exit[bid] = [j for _, j in cand[:3]]
        self.complete = True

    def chokepoints(self, k=8):
        return [i for i, _ in sorted(self.choke.items(), key=lambda kv: (-kv[1], kv[0]))[:k]]


# ------------------------------------------------------------------ 예약

class ReservationBook:
    """건물 id ↔ 깃발병 uid 1:1 예약."""

    def __init__(self):
        self.by_building = {}
        self.by_unit = {}

    def holder(self, bid):
        return self.by_building.get(bid)

    def unassign(self, uid, bid=None):
        cur = self.by_unit.get(uid)
        if cur is None or (bid is not None and cur != bid):
            return
        del self.by_unit[uid]
        if self.by_building.get(cur) == uid:
            del self.by_building[cur]

    def assign(self, uid, bid):
        other = self.by_building.get(bid)
        if other is not None and other != uid:
            return False
        self.unassign(uid)
        self.by_building[bid] = uid
        self.by_unit[uid] = bid
        return True

    def reassign(self, uid, old_bid, new_bid):
        self.unassign(uid, old_bid)
        return self.assign(uid, new_bid)

    def prune(self, live_uids):
        for uid in [u for u in self.by_unit if u not in live_uids]:
            self.unassign(uid)


class FAgent:
    """깃발병 1기. 스택을 1기 단위로 쪼개 uid 를 붙인다."""
    __slots__ = ("uid", "idx", "target", "shadow", "stuck", "banned", "next_idx", "util", "age", "snipe",
                 "last_dir", "hist", "thrash")

    def __init__(self, uid, idx):
        self.uid = uid
        self.idx = idx
        self.target = None
        self.shadow = None
        self.stuck = 0
        self.banned = {}
        self.next_idx = None
        self.util = 0.0
        self.age = 0          # 현재 목표 유지 턴 수
        self.snipe = None     # 이번 턴 스나이프 대상 셀 idx
        self.last_dir = None  # v9: 직전 턴 이동 방향
        self.hist = []        # v9: 최근 위치(최대 4)
        self.thrash = 0       # v9: 동일 목표 A-B-A-B 왕복 횟수


class Memory:
    def __init__(self):
        self.cache = None
        self.init_id = None
        self.book = ReservationBook()
        self.next_plans = {}   # 예상 위치 idx -> [FAgent]
        self.uid_seq = 0
        self.scouts_built = 0
        self.depot_claimed = False
        self.enemy_depot_claimed = False
        self.my_depots = set()     # v6: 우리가 보너스를 받은 보급소 id
        self.enemy_depots = set()  # v6: 상대가 보너스를 받은 보급소 id
        self.prev_enemy_eta = {}   # 건물 id -> 지난 턴 적 F 최단 거리
        self.intercept = None      # 진행 중인 보급소 인터셉트 대상 건물 id(로그용)
        self.w_goals = {}          # 예상 위치 idx -> {전진 목표 idx: 기수} (지난 턴 전진 W 목표)
        self.sweeper_uid = None    # 홈 전담 F uid
        self.meta = None           # v9: 턴0 정적 메타
        self.home_alarm = False    # v9: 본진 비상 상태(히스테리시스)
        self.home_calm = 0         # v9: 해제 조건 연속 턴 수
        self.staging = {}          # v9: W 목표 idx -> 집결 대기 턴 수
        self.w_ban = {}            # v9: W 목표 idx -> 금지 해제 턴
        self.w_arr = {}            # v9: 지난 턴 W 도착 칸 -> {출발 칸: 수}
        self.opening = None        # v10: OpeningPolicy
        self.opening_active = False
        self.arch = None           # v10: 판별된 적 아키타입
        self.macro_log = []

    def new_uid(self):
        self.uid_seq += 1
        return self.uid_seq

    def soft_reset(self):
        self.book = ReservationBook()
        self.next_plans = {}


MEM = Memory()


# ------------------------------------------------------------------ C. 위협

class ThreatAnalyzer:
    def __init__(self, cache, enemy_w, spawn_sites, spawn_pot):
        self.c = cache
        self.enemy = self._reach(enemy_w)
        if spawn_pot > 0:
            for s in spawn_sites:
                self.enemy[s] += spawn_pot
                for _, j in cache.nbrs[s]:
                    self.enemy[j] += spawn_pot
        self.friendly = [0] * cache.n

    def _reach(self, stacks):
        grid = [0] * self.c.n
        nbrs = self.c.nbrs
        for i, k in stacks.items():
            grid[i] += k
            for _, j in nbrs[i]:
                grid[j] += k
        return grid

    def set_friendly(self, stacks):
        self.friendly = self._reach(stacks)

    def net(self, i):
        return self.friendly[i] - self.enemy[i]


class MilitaryBudget:
    """상위 병력 예산. 전술 모듈은 여기서 정한 역할별 쿼터 안에서만 W를 차출한다.

    total_W  = 아군 W 총수(이번 턴 생산분 포함)
    free_W   = max(0, total_W - (home_defense + center_defense))
    역할 쿼터: home(홈 방어) / special(특수 전술, free_W >= 2 일 때만) / front(나머지 전부)
    home_req 는 초반(T <= EARLY_TURNS)에 비상 상황이 아니면 0이다.
    """

    def __init__(self, total_w, enemy_w, home_req=REQUIRED_HOME_DEFENSE):
        self.total = total_w
        self.home_req = home_req
        self.center_req = max(CENTER_DEFENSE_MIN, int(enemy_w * CENTER_DEFENSE_RATIO))
        self.free = max(0, total_w - (self.home_req + self.center_req))
        self.special = SPECIAL_SQUAD if self.free >= SPECIAL_SQUAD else 0
        self.home = min(self.home_req, total_w)
        self.front = max(0, total_w - self.home - self.special)

    def quotas(self):
        # v8: 홈 비상 쿼터만 유지하고 나머지 역할은 단일 풀에서 가치 순으로 차출한다.
        return {"home": self.home, "special": INF, "front": INF}


class WarriorPool:
    """이번 턴 아직 명령받지 않은 전투병(avail), 셀별 도착 확정 수(arrive), 역할 쿼터(quota)."""

    def __init__(self, cache, stacks, cmds, quota):
        self.c = cache
        self.cmds = cmds
        self.avail = {i: k for i, k in stacks.items() if k > 0}
        self.arrive = {}
        self.quota = dict(quota)

    def left(self, role):
        return self.quota.get(role, 0)

    def release(self, role, to="front"):
        """쓰지 않은 쿼터를 다른 역할로 돌려준다."""
        k = self.quota.get(role, 0)
        if k > 0:
            self.quota[role] = 0
            self.quota[to] = self.quota.get(to, 0) + k

    def reach(self, c, role="front"):
        avail = self.avail
        s = avail.get(c, 0)
        for _, j in self.c.nbrs[c]:
            s += avail.get(j, 0)
        return self.arrive.get(c, 0) + min(s, self.left(role))

    def commit(self, c, need, role="front"):
        """c 에 need 기를 모은다(제자리 우선, 인접 칸에서 이동). 실제 모은 수 반환."""
        need = min(need, self.left(role))
        got = 0
        k = min(need, self.avail.get(c, 0))
        if k:
            self.avail[c] -= k
            got += k
        for d, j in self.c.nbrs[c]:
            if got >= need:
                break
            k = min(need - got, self.avail.get(j, 0))
            if k and self.cmds.move(j, "W", k, OPPOSITE[d]):
                self.avail[j] -= k
                got += k
        if got:
            self.arrive[c] = self.arrive.get(c, 0) + got
            self.quota[role] -= got
        return got

    def send_toward(self, j, goal, k, threat=None, role="front", staging=None, came=None):
        """j 의 k 기를 goal 쪽으로 한 칸. 위험하면 제자리. 도착 칸 반환.

        v9: staging 이 주어지면 이동 후 예상 병력비 R = (도착 W)/(적 도달 W + 1) 로 판단
            (R < R_STAGE 진입 금지, R < R_ENTER 집결 대기 -> staging[goal] 표시).
            came(지난 턴 도착 기록)이 주어지면 되돌아가는 방향은 같은 거리 대안이 있을 때 피한다.
        """
        k = min(k, self.avail.get(j, 0), self.left(role))
        if k <= 0:
            return None
        self.quota[role] -= k
        dest = j
        if j != goal:
            d = self.c.step[j][goal] if self.c.step[j] is not None else None
            if d is not None:
                nj = next((t for dd, t in self.c.nbrs[j] if dd == d), None)
                if came and nj is not None and came.get(nj, 0) > 0:
                    dg = self.c.d(nj, goal)
                    alt = [(dd, t) for dd, t in self.c.nbrs[j] if t != nj and self.c.d(t, goal) == dg
                           and (threat is None or threat.enemy[t] <= threat.enemy[nj])]
                    if alt:
                        d, nj = alt[0]
                if threat is not None and nj is not None and staging is not None and threat.enemy[nj] > 0:
                    r = (self.arrive.get(nj, 0) + k) / (threat.enemy[nj] + 1)
                    risky = r < R_ENTER
                    if R_STAGE <= r < R_ENTER:
                        staging[goal] = True
                else:
                    risky = (threat is not None and nj is not None
                             and threat.enemy[nj] > self.arrive.get(nj, 0) + k)
                if nj is not None and not risky and self.cmds.move(j, "W", k, d):
                    dest = nj
        self.avail[j] -= k
        self.arrive[dest] = self.arrive.get(dest, 0) + k
        return dest


# ------------------------------------------------------------------ 명령 검증

class CommandBook:
    """모든 명령은 여기를 거친다. 수량·지형·토큰 규격을 검증하고 같은 이동은 병합한다."""

    def __init__(self, view, cache):
        self.c = cache
        self.view = view
        self.stock = {}
        for u in view.my_units():
            key = (u["y"] * cache.w + u["x"], u["kind"])
            self.stock[key] = self.stock.get(key, 0) + u["count"]
        self.spawns = []
        self.teles = []
        self.moves = {}
        self.move2s = {}
        self.prio = None
        self.tele_used = 0

    def _take(self, idx, kind, count):
        if not isinstance(count, int) or count <= 0:
            return False
        have = self.stock.get((idx, kind), 0)
        if have < count:
            return False
        self.stock[(idx, kind)] = have - count
        return True

    def spawn(self, kind, count, site_idx, base_idx):
        if kind not in UNITS or not isinstance(count, int) or count <= 0:
            return False
        if site_idx is not None and not self.c.passable[site_idx]:
            return False
        at = base_idx if site_idx is None else site_idx
        self.stock[(at, kind)] = self.stock.get((at, kind), 0) + count
        self.spawns.append((kind, count, site_idx))
        return True

    def _dest(self, idx, d):
        for dd, j in self.c.nbrs[idx]:
            if dd == d:
                return j
        return None

    def move(self, idx, kind, count, d):
        if kind not in UNITS or d not in DIRS or self._dest(idx, d) is None:
            return False
        if not self._take(idx, kind, count):
            return False
        key = (idx, kind, d)
        self.moves[key] = self.moves.get(key, 0) + count
        return True

    def move2(self, idx, count, d1, d2):
        """정찰병 2칸 이동. 경유 칸과 도착 칸 모두 통과 가능해야 한다(불변조건 5)."""
        if d1 not in DIRS or d2 not in DIRS:
            return False
        x, y = self.c.xy(idx)
        mx, my = x + DIRS[d1][0], y + DIRS[d1][1]
        ex, ey = mx + DIRS[d2][0], my + DIRS[d2][1]
        init = self.c.init
        if not (init.passable(mx, my) and init.passable(ex, ey)):
            return False
        if not self._take(idx, "S", count):
            return False
        key = (idx, d1, d2)
        self.move2s[key] = self.move2s.get(key, 0) + count
        return True

    def can_teleport(self, src, dst, count, owned_stations):
        """TELE 독립 검증(불변조건 4): 턴당 per_turn 회, 최대 max_units 기, 소유 역 min_stations 개 이상."""
        return (self.tele_used < TELE_CFG["per_turn"]
                and len(owned_stations) >= TELE_CFG["min_stations"]
                and src in owned_stations and dst in owned_stations and src != dst
                and isinstance(count, int) and 1 <= count <= TELE_CFG["max_units"])

    def tele(self, src, kind, count, dst, owned_stations):
        if kind not in UNITS or not self.can_teleport(src, dst, count, owned_stations):
            return False
        if not self._take(src, kind, count):
            return False
        self.tele_used += 1
        self.teles.append((src, kind, count, dst))
        return True

    def set_priority(self, idxs):
        if idxs:
            self.prio = list(idxs)

    def emit(self):
        out = []
        for kind, count, site in self.spawns:
            if site is None:
                out.append(spawn(kind, count))
            else:
                out.append(spawn(kind, count, *self.c.xy(site)))
        for src, kind, count, dst in self.teles:
            out.append(tele(*self.c.xy(src), kind, count, *self.c.xy(dst)))
        for (idx, kind, d), count in self.moves.items():
            out.append(move(*self.c.xy(idx), kind, count, d))
        for (idx, d1, d2), count in self.move2s.items():
            out.append(move2(*self.c.xy(idx), count, d1, d2))
        if self.prio:
            out.append(priority([self.c.xy(i) for i in self.prio]))
        good = []
        for cmd in out:
            if valid_tokens(cmd):
                good.append(cmd)
            else:
                log(f"drop malformed: {cmd}")
        return good


def valid_tokens(cmd):
    """출력 직전 명령 규격 최종 검사."""
    t = cmd.split()
    if not t:
        return False

    def ints(xs):
        return all(x.lstrip("-").isdigit() for x in xs)

    op = t[0]
    if op == "SPAWN":
        return len(t) in (3, 5) and t[1] in UNITS and ints(t[2:])
    if op == "MOVE":
        return len(t) == 6 and ints(t[1:3]) and t[3] in UNITS and ints(t[4:5]) and t[5] in DIRS
    if op == "MOVE2":
        return len(t) == 7 and ints(t[1:3]) and t[3] == "S" and ints(t[4:5]) and t[5] in DIRS and t[6] in DIRS
    if op == "TELE":
        return len(t) == 7 and ints(t[1:3]) and t[3] in UNITS and ints(t[4:7])
    if op == "PRIORITY":
        return len(t) >= 3 and len(t) % 2 == 1 and ints(t[1:])
    return False


# ------------------------------------------------------------------ B. 자원

class ResourceManager:
    def __init__(self, brain):
        self.b = brain
        self.budget = 0
        self.reserved = 0
        self.raw_reserved = 0

    def reserved_capture(self, agents):
        """목표까지 dist <= 1 인 깃발병의 목표 점령비 합(건물당 1회)."""
        b = self.b
        seen = set()
        total = 0
        for a in agents:
            if a.target is None or a.target in seen:
                continue
            bld = b.blds.get(a.target)
            if bld is None or bld["owner"] == b.team:
                continue
            if b.c.d(a.idx, b.c.bpos[a.target]) <= 1:
                seen.add(a.target)
                total += capture_cost(bld["type"], b.own_library)
        self.raw_reserved = total
        if RESERVE_NET_OF_INCOME:
            # v8 불변식: R - P + I >= C  (I = 보장 수입, 보급소 보너스는 제외)
            total = max(0, total - b.guaranteed_income)
        return total

    def open_budget(self, agents):
        self.reserved = self.reserved_capture(agents)
        self.budget = max(0, self.b.view.my_resource - self.reserved)
        return self.budget

    def frontier_plan(self, agents):
        """[D-True] T1 F2, T2~T4 F1(누적 F_CAP_TOTAL 까지), 이후 F 생산 영구 중단. 남는 예산 100% W."""
        b = self.b
        budget = self.budget
        fc, wc = UNITS["F"]["cost"], b.w_cost
        made = b.mem.__dict__.get("f_spawned_total", 0)
        kf = 0
        if b.turn == 1:
            kf = min(2, budget // fc, F_CAP_TOTAL)
        elif b.turn <= F_OPEN_TURNS and made < F_CAP_TOTAL:
            kf = min(1, budget // fc, F_CAP_TOTAL - made)
        orders = []
        if kf:
            b.mem.f_spawned_total = made + kf
            budget -= kf * fc
            orders.append(("F", kf, None))
        kw = budget // wc
        if kw:
            orders.append(("W", kw, b.frontier_site()))
        return orders

    def plan(self, agents):
        """(kind, count, site) 목록. 합계 비용이 production_budget 을 넘지 않는다."""
        b = self.b
        if FRONTIER_MODE or (PHALANX_MODE and PHALANX_OPENING):
            return self.frontier_plan(agents)
        budget = self.budget
        fc, wc, sc = UNITS["F"]["cost"], b.w_cost, UNITS["S"]["cost"]
        nF = len(agents)
        nW = sum(b.my["W"].values())
        nS = sum(b.my["S"].values())
        enemy_w = sum(b.en["W"].values())
        capturable = sum(1 for bid in b.blds if b.capturable(bid))
        desired_f = self.flag_cap(capturable)
        if getattr(b, "macro", None) == "OPEN_SAFE_DEFENSIVE" and nF > 0:
            desired_f = min(desired_f, nF)   # v10: 수비 매크로 턴은 W 우선
        if MOD_SURGE and b.turn > 1 and b.n_eng_own > 0 and desired_f > max(nF, BASE_FLAG_CAP):
            desired_f = max(nF, BASE_FLAG_CAP)   # v17 [A4] 공학관(W 2원) 보유 중: 점령 예약 유지, 추가 F 대신 W
            b._stat("surge")
        f_site = self.pick_site("F")
        f_site_capture = self.spawn_capture_cost(f_site)
        if RESERVE_NET_OF_INCOME:
            # 기본 수입 중 기존 예약에 쓰이지 않은 여유분으로 새 F의 즉시 점령비를 충당
            slack = max(0, b.guaranteed_income - self.raw_reserved)
            f_site_capture = max(0, f_site_capture - slack)
        early_safe = b.turn <= NO_ESCORT_TURNS and self.min_enemy_w_dist(agents) > NO_ESCORT_SAFE_DIST
        counts = {"F": 0, "W": 0, "S": 0}

        def buy(kind, cost):
            nonlocal budget
            counts[kind] += 1
            budget -= cost

        force_w = getattr(b, "force_w", 0)
        while force_w > 0 and budget >= wc:   # v7: 홈 침투 대응 생산을 먼저
            buy("W", wc)
            force_w -= 1
        if b.turn <= 1 and nF == 0:
            while counts["F"] < 2 and budget >= fc:
                buy("F", fc)
        if (b.turn >= SCOUT_START_TURN and nS == 0 and b.mem.scouts_built < MAX_SCOUTS_BUILT
                and b.unrevealed and b.turns_left > SCOUT_MIN_TURNS_LEFT and budget >= max(sc, SCOUT_MIN_RES)):
            buy("S", sc)

        rush = enemy_w >= RUSH_MIN_ENEMY_W and enemy_w >= nW + RUSH_MARGIN
        spawn_lock = 0   # 새 F가 생산 칸 옆 건물을 같은 턴에 점령할 수 있으면 그 비용도 잠근다
        for _ in range(40):
            f_total = nF + counts["F"]
            w_total = nW + counts["W"]
            f_need = fc + (f_site_capture if spawn_lock == 0 else 0)
            can_f = (budget >= f_need and b.turns_left > 6 and f_total < desired_f
                     and (not rush or f_total < RUSH_F_FLOOR))
            escorted = early_safe or w_total >= min(f_total, FLAG_ESCORT_W_MIN)
            if can_f and (escorted or b.turn <= 1):
                buy("F", fc)
            elif budget >= wc:
                buy("W", wc)
            elif can_f:
                buy("F", fc)
            else:
                break
            if counts["F"] and spawn_lock == 0 and f_site_capture:
                spawn_lock = f_site_capture
                budget -= spawn_lock

        orders = []
        for kind in ("F", "W", "S"):
            if counts[kind]:
                site = f_site if kind == "F" else self.pick_site(kind)
                orders.append((kind, counts[kind], site))
        spent = counts["F"] * fc + counts["W"] * wc + counts["S"] * sc
        assert spent + spawn_lock <= self.budget, "production over budget"
        self.reserved += spawn_lock
        return orders

    def min_enemy_w_dist(self, agents):
        """아군 본진과 F들에서 가장 가까운 적 W까지 거리."""
        b = self.b
        mine = [b.c.base[b.team]] + [a.idx for a in agents]
        return min((b.c.d(e, m) for e in b.en["W"] for m in mine), default=INF)

    def flag_cap(self, capturable):
        """동시 활동 F 상한. 목표 수와 유휴 자원에 따라 BASE_FLAG_CAP..MAX_FLAGS."""
        cap = BASE_FLAG_CAP
        if capturable > BASE_FLAG_CAP:
            cap += 1
        if capturable > cap and self.b.view.my_resource >= IDLE_RESOURCE:
            cap += 1
        cap = min(MAX_FLAGS, capturable, cap)
        if self.b.turns_left <= ENDGAME_TURNS + ENDGAME_FLAG_EXTRA:
            cap = max(cap, min(ENDGAME_FLAG_CAP, capturable))   # v7: 말기 기습용 깃발병
        return cap

    def spawn_capture_cost(self, site):
        """생산 칸에서 1칸 안에 점령 가능한 건물이 있으면 그중 최대 점령비."""
        b = self.b
        at = b.c.base[b.team] if site is None else site
        cost = 0
        for bid in b.blds:
            if b.capturable(bid) and b.c.d(at, b.c.bpos[bid]) <= 1:
                cost = max(cost, capture_cost(b.blds[bid]["type"], b.own_library))
        return cost

    def pick_site(self, kind):
        """본진(None) 또는 소유 병원 중 전선에 가까운 곳."""
        b = self.b
        if kind == "S" or not b.hospitals:
            return None
        if MOD_HOSP and kind == "W":
            return b.hosp_site_v17()
        if MOD_HOSP_RUSH and kind == "W":
            eb = b.c.base[b.opp]
            return min(b.hospitals, key=lambda h: (b.c.d(h, eb), h))   # 샌드백: 적 본진에 가장 가까운 병원(안전 무시)
        goals = [b.c.bpos[bid] for bid in b.blds if b.capturable(bid)]
        if not goals:
            return None
        base = b.c.base[b.team]

        def score(site):
            return min(b.c.d(site, g) for g in goals)

        best, best_s = None, score(base)
        for h in b.hospitals:
            if b.threat.enemy[h] > 0 or (h, "F") in b.enemy_cells or (h, "W") in b.enemy_cells:
                continue
            s = score(h)
            if s < best_s:
                best, best_s = h, s
        return best


# ------------------------------------------------------------------ 턴 실행

class Brain:
    def __init__(self, view, init, mem, clock, cmds):
        self.view, self.init, self.mem, self.clock, self.cmds = view, init, mem, clock, cmds
        self.c = mem.cache
        self.book = mem.book
        self.team, self.opp = view.team, view.opp
        self.turn = view.turn
        self.turns_left = TOTAL_TURNS - view.turn
        self.agents = []

    # --- 상태 스캔
    def scan(self):
        c, view, team, opp = self.c, self.view, self.team, self.opp
        c.update_scores(view)
        self.blds = {b["id"]: b for b in view.buildings if b["id"] in c.bpos}
        owned = [b for b in self.blds.values() if b["owner"] == team]
        opp_owned = [b for b in self.blds.values() if b["owner"] == opp]
        for b in owned:
            if b["type"] == "DEPOT":
                self.mem.my_depots.add(b["id"])
        self.mem.depot_claimed = bool(self.mem.my_depots)
        if self.mem.depot_claimed and self.mem.__dict__.get("depot_turn") is None:
            self.mem.depot_turn = self.turn      # v16 [B] 보급소 보너스 입금 시점(점령 다음 턴 관측)
            if DEPOT_RUSH:
                self._stat("depot_turn", self.turn)
        self.own_library = any(b["type"] == "LIBRARY" for b in owned)
        n_eng = sum(b["type"] == "ENG" for b in owned)
        n_eng_opp = sum(b["type"] == "ENG" for b in opp_owned)
        floor, wbase, disc = BLD["eng_cost_floor"], UNITS["W"]["cost"], BLD["eng_discount_per"]
        self.w_cost = max(floor, wbase - n_eng * disc)
        self.n_eng_own, self.n_eng_opp_own = n_eng, n_eng_opp
        opp_w_cost = max(floor, wbase - n_eng_opp * disc)
        self.income = RES["base_income"] + RES["hall_bonus"] * sum(b["type"] == "HALL" for b in owned)
        self.stations = {c.bpos[b["id"]] for b in owned if b["type"] == "STATION"}
        self.hospitals = [c.bpos[b["id"]] for b in owned if b["type"] == "HOSPITAL"]
        opp_hosp = [c.bpos[b["id"]] for b in opp_owned if b["type"] == "HOSPITAL"]

        self.my = {k: {} for k in UNITS}
        self.en = {k: {} for k in UNITS}
        self.enemy_cells = set()
        for u in view.units:
            i = u["y"] * c.w + u["x"]
            tbl = self.my if u["team"] == team else self.en
            tbl[u["kind"]][i] = tbl[u["kind"]].get(i, 0) + u["count"]
            if u["team"] != team:
                self.enemy_cells.add((i, u["kind"]))

        self.unrevealed = [bid for bid in self.blds if not c.revealed(bid)]
        pot = min(ENEMY_SPAWN_CAP, view.opp_resource // opp_w_cost)
        self.threat = ThreatAnalyzer(c, self.en["W"], [c.base[opp]] + opp_hosp, pot)
        # v7: 점령 후 유지 검사용 반경 HOLD_RADIUS 도달 병력(생산 가능량 포함)
        self.my_spawn_sites = [c.base[team]] + self.hospitals
        self.my_spawn_pot = min(OWN_SPAWN_CAP, view.my_resource // self.w_cost)
        self.hold_enemy = self._reach_k(self.en["W"], [c.base[opp]] + opp_hosp, pot)
        self.hold_mine = self._reach_k(self.my["W"], self.my_spawn_sites, self.my_spawn_pot)

        # v6: 상대 역 순간이동 위협. 상대 역 2개 이상이면 다른 역 위의 적 W(최대 5)가 이번 턴 도착 가능.
        self.opp_stations = [c.bpos[b["id"]] for b in opp_owned if b["type"] == "STATION"]
        self.opp_tele = len(self.opp_stations) >= TELE_CFG["min_stations"]
        if self.opp_tele:
            for t in self.opp_stations:
                src = max((self.en["W"].get(s, 0) for s in self.opp_stations if s != t), default=0)
                add = min(TELE_CFG["max_units"], src)
                if add:
                    self.threat.enemy[t] += add

        for b in opp_owned:
            if b["type"] == "DEPOT":
                self.mem.enemy_depots.add(b["id"])
        self.mem.enemy_depot_claimed = bool(self.mem.enemy_depots)
        # 적 F의 건물별 최단 도착 거리(ETA). 지난 턴 값과 비교해 접근 여부를 판단한다.
        enemy_f = list(self.en["F"])
        self.enemy_eta = {bid: min((self.enemy_dist(e, c.bpos[bid]) for e in enemy_f), default=INF)
                          for bid in self.blds}
        self.prev_enemy_eta = self.mem.prev_enemy_eta
        self.mem.prev_enemy_eta = self.enemy_eta

        # v8 Step 1: 적/아군 W 도착 턴 지도(다중 출발 BFS). 생산 거점은 생산 즉시 이동 가능하므로 거리 0.
        src = {i: 0 for i in self.en["W"]}
        if view.opp_resource >= opp_w_cost:
            for s_ in [c.base[opp]] + opp_hosp:
                src[s_] = 0
        if self.opp_tele:
            for t in self.opp_stations:
                if any(self.en["W"].get(s_, 0) for s_ in self.opp_stations if s_ != t):
                    src[t] = min(src.get(t, INF), 1)
        self.enemy_w_eta = c.multi_bfs(src)
        self.enemy_w_eta_units = c.multi_bfs({i: 0 for i in self.en["W"]}) if self.en["W"] else [INF] * c.n
        msrc = {i: 0 for i in self.my["W"]}
        if view.my_resource >= self.w_cost:
            for s_ in self.my_spawn_sites:
                msrc[s_] = 0
        self.my_w_eta = c.multi_bfs(msrc)
        # 보장 수입: 기본 + 이번 턴 뺏길 위험이 없는 학생회관(깃발병이 위협받는 학관 제외). 보급소 보너스 제외.
        halls_safe = 0
        for b in owned:
            if b["type"] != "HALL":
                continue
            hi = c.bpos[b["id"]]
            if self.my["F"].get(hi, 0) and self.threat.enemy[hi] > 0:
                continue
            halls_safe += 1
        self.guaranteed_income = RES["base_income"] + RES["hall_bonus"] * halls_safe
        self.home_emergency = False
        self.snipes = []
        self.macro = None
        self.balls = self.detect_deathballs() if DEATHBALL_ENABLED else []

        # 홈 진영 = 아군 본진이 속한 지역(신촌/안암). 홈 경제 = 그 안의 HALL/LIBRARY.
        home_coord = c.base[team] % c.w if c.axis == 0 else c.base[team] // c.w
        lo, hi = 0, c.w - 1
        for rlo, rhi in CFG["regions"].values():
            if rlo <= home_coord <= rhi:
                lo, hi = rlo, rhi
        self.home_blds = set()
        for bid, i in c.bpos.items():
            coord = i % c.w if c.axis == 0 else i // c.w
            if lo <= coord <= hi:
                self.home_blds.add(bid)
        self.home_econ = {bid for bid in self.home_blds if c.btype[bid] in HOME_ECON_TYPES}
        self.capturable_count = sum(1 for bid in self.blds if self.capturable(bid))
        self.econ_slot_open = not any(self.blds[bid]["owner"] == team
                                      for bid in self.home_econ if bid in self.blds)
        self.raid = None
        self.home_pending = sorted(bid for bid in self.home_blds if self.capturable(bid))
        self.sweeper = None

    def _reach_k(self, stacks, sites, pot):
        """반경 HOLD_RADIUS 안에 도달 가능한 전투병 수(셀별). 생산 거점의 생산 가능량 포함."""
        c = self.c
        grid = [0] * c.n
        src = dict(stacks)
        if pot > 0:
            for s_ in sites:
                src[s_] = src.get(s_, 0) + pot
        for i, k in src.items():
            row = c.dist[i]
            if row is None:
                continue
            for j in range(c.n):
                if row[j] <= HOLD_RADIUS:
                    grid[j] += k
        return grid

    def hold_margin(self, bi):
        return self.hold_mine[bi] - self.hold_enemy[bi]

    def enemy_dist(self, e, target):
        """적 유닛의 도착 턴 수. 상대가 역 2개 이상이면 역 → 역 순간이동(1턴) 경로도 고려."""
        c = self.c
        best = c.d(e, target)
        if self.opp_tele:
            for s1 in self.opp_stations:
                d1 = c.d(e, s1)
                if d1 + 1 >= best:
                    continue
                for s2 in self.opp_stations:
                    if s2 != s1:
                        best = min(best, d1 + 1 + c.d(s2, target))
        return best

    def capturable(self, bid):
        b = self.blds.get(bid)
        return b is not None and b["owner"] != self.team and b["type"] != "BASE"

    # --- D. 목표 평가·배정
    def build_agents(self):
        mem = self.mem
        plans = mem.next_plans
        mem.next_plans = {}
        agents = []
        for idx in sorted(self.my["F"]):
            carry = plans.pop(idx, [])
            for _ in range(self.my["F"][idx]):
                a = carry.pop(0) if carry else FAgent(mem.new_uid(), idx)
                a.idx = idx
                a.next_idx = None
                a.shadow = None
                a.banned = {k: v for k, v in a.banned.items() if v >= self.turn}
                a.age += 1
                a.snipe = None
                a.hist = (a.hist + [idx])[-4:]
                h = a.hist
                if len(h) == 4 and h[0] == h[2] and h[1] == h[3] and h[0] != h[1] and a.target is not None:
                    a.thrash += 1
                    a.hist = [idx]
                    if a.thrash >= THRASH_LIMIT and not self.home_emergency:
                        log(f"T{self.turn} F#{a.uid} thrash -> drop target {a.target}")
                        a.banned[a.target] = self.turn + BAN_TURNS
                        self.book.unassign(a.uid)
                        a.target = None
                        a.thrash = 0
                agents.append(a)
        # 남은 계획 = 사망(또는 이동 실패)한 유닛. 예약을 즉시 해제해 유령 예약을 막는다.
        self.book.prune({a.uid for a in agents})
        self.agents = agents
        return agents

    def force_by(self, bi, T, mine):
        """T 턴 안에 칸 bi 에 모일 수 있는 전투병(현재 병력 + 생산 가능량)."""
        c = self.c
        team = self.team if mine else self.opp
        stacks = self.my["W"] if mine else self.en["W"]
        f = sum(k for s_, k in stacks.items() if c.d(s_, bi) <= T)
        if TT_SPAWN:
            sites = [c.base[team]] + [c.bpos[b] for b, bb in self.blds.items() if bb["owner"] == team and c.btype[b] == "HOSPITAL"]
            dmin = min((c.d(s_, bi) for s_ in sites), default=INF)
            if dmin <= T:
                eng = sum(1 for b, bb in self.blds.items() if bb["owner"] == team and c.btype[b] == "ENG")
                halls = sum(1 for b, bb in self.blds.items() if bb["owner"] == team and c.btype[b] == "HALL")
                wc = max(2, 3 - eng)
                res = self.view.my_resource if mine else self.view.opp_resource
                f += res // wc + (T - dmin) * (10 + 2 * halls) // wc
        return f

    def utility(self, a, bid, d):
        u = self._utility_base(a, bid, d)
        c_ = self.c
        if STV_ENABLED and self.blds[bid]["owner"] == self.opp:
            t_ = c_.btype[bid]
            if t_ == "HALL":
                u += STV_HALL
            elif t_ == "ENG":
                n_eng = sum(1 for bb in self.blds.values() if bb["owner"] == self.opp and bb["type"] == "ENG")
                u += STV_ENG_SOLE if n_eng == 1 else STV_ENG
            elif t_ == "HOSPITAL":
                u += STV_HOSP
            self._stat("stv")
        if SCORE_EARLY_T and self.turn <= SCORE_EARLY_T:
            u -= (1.0 - SCORE_EARLY_W) * c_.score(bid) * UTIL_SCORE_W / (d + 1)
        if TT_W > 0 and self.blds[bid]["owner"] != self.team:
            bi = self.c.bpos[bid]
            gap = self.force_by(bi, d + TT_H, False) - self.force_by(bi, d + TT_H, True)
            if gap > 0:
                u -= min(TT_CAP, TT_W * gap)
                self._stat("tt_pen")
        if CW_ENABLED and u > 0:
            u *= self.center_weight(bid)
        return u

    def _utility_base(self, a, bid, d):
        """v8 공통 점수: 보유 가치 x S(H)/S(H_MAX) + 보급소 즉시 보너스 + 초반 템포."""
        c = self.c
        u = self.base_utility(a, bid, d)
        t = c.btype[bid]
        depot = 0.0
        if t == "DEPOT" and bid not in self.mem.my_depots:
            depot = BONUS_DEPOT * (1.0 if d <= self.enemy_eta.get(bid, INF) else DEPOT_CONTESTED_FACTOR)
        hold = u - depot
        if hold > 0:
            hold *= self.safety(bid, d)
        u = hold + depot
        if EOV_W > 0 or DENIAL_W > 0:
            u += self.eov(bid, d)
        u += self.v18_bonus(bid, t, d)
        if t == "HALL" and HALL_EXTRA_BONUS > 0:
            n_hall = sum(1 for b in self.blds.values() if b["owner"] == self.team and b["type"] == "HALL")
            if n_hall == 0:
                u += HALL_EXTRA_BONUS
            elif self.blds[bid]["owner"] == self.opp:
                u += HALL_EXTRA_BONUS * 0.5
        if t == "ENG" and ENG_BONUS > 0 and not MOD_DYN_ECON:
            # 군사 경제: 공학관 1개로 W 단가 3 -> 2 (같은 수입에서 W +50%). 미보유 시 확보·탈환 가점
            if self.n_eng_own == 0:
                u += ENG_BONUS
            elif self.blds[bid]["owner"] == self.opp and self.n_eng_opp_own <= 1:
                u += ENG_BONUS * 0.5
        if self.balls:
            bi_ = c.bpos[bid]
            dmin = min(c.d(e, bi_) for e, _, _ in self.balls)
            if dmin <= DB_F_NEAR:
                u -= DB_F_PENALTY
            elif dmin >= DB_FLANK_DIST:
                u += DB_FLANK_BONUS
        if self.macro is not None:
            types = MACRO_TYPES.get(self.macro, ())
            if self.macro == "OPEN_SAFE_DEFENSIVE":
                if bid in self.home_blds:
                    u += MACRO_BONUS
            elif t in types:
                if not (t == "HALL" and self.macro == "OPEN_HALL_F2" and bid not in self.home_blds):
                    u += MACRO_BONUS
        if self.turn <= EARLY_RUSH_TURNS:
            if t == "DEPOT" and bid not in self.mem.my_depots:
                race = self.mem.meta.race.get(bid, {}) if self.mem.meta else {}
                u += EARLY_DEPOT_BONUS * (DEPOT_LOSS_FACTOR if race.get("depot") == "LOSS" else 1.0)
            if bid not in self.home_blds:
                u += EARLY_CENTER_BONUS
        if DEPOT_RUSH:
            if (self.turn <= DEPOT_RUSH_TURNS and t == "DEPOT" and bid not in self.mem.my_depots
                    and self.blds[bid]["owner"] != self.opp):
                u += DEPOT_RUSH_BONUS
            dt = self.mem.__dict__.get("depot_turn")
            if dt is not None and self.turn - dt <= DEPOT_CENTER_TURNS and self.side_center(bid):
                u += DEPOT_CENTER_F_BONUS
        return u

    def v18_bonus(self, bid, t, d):
        """v18 가점 합: 압력 믹서, 동적 ENG, 트레이딩, 체크메이트, 병원 러시(샌드백)."""
        c = self.c
        u = 0.0
        own = self.blds[bid]["owner"]
        if MOD_META:
            pr, on = self._press, self.mem.__dict__.get("press_on", {})
            if t == "HOSPITAL" and own != self.team and on.get("H"):
                u += META_K * pr["H"]
            if bid in self.home_blds and own != self.team and on.get("E"):
                u += META_K * pr["E"]
            if self.side_center(bid) and own != self.team and on.get("C"):
                u += META_K * pr["C"]
            if on.get("C") and (t == "HOSPITAL" or bid in self.home_blds):
                u -= META_LAMBDA * pr["C"]       # 병원/홈 쏠림으로 중앙 결손
        if MOD_DYN_ECON and t == "ENG":
            w = sum(self.my["W"].values())
            ew = 4.0 + min(5.0, 0.5 * max(0, w - 4))
            if self.n_eng_own == 0:
                u += ew
            elif own == self.opp and self.n_eng_opp_own <= 1:
                u += ew * 0.5
        if MOD_TRADE and own != self.team:
            cents = self.mem.__dict__.get("trade_cents") or []
            if cents and min(c.d(x, c.bpos[bid]) for x in cents) >= 7:
                u += TRADE_BONUS
        if MOD_CHECKMATE and own == self.opp and getattr(self, "_cm", False):
            u += CM_BONUS
        if MOD_MODES:
            u += self.mode_bonus(bid, t, d, own)
        if MOD_HOSP_RUSH and t == "HOSPITAL" and own != self.team:
            u += HR_BONUS
        if MOD_HYENA and own == self.opp and d <= (6 if MOD_HYENA == 4 else 4):
            bi_ = c.bpos[bid]
            if any(c.d(e, bi_) <= 1 for e in self.en["F"]):
                u += HY_BONUS                     # 막 점령했거나 점령 중인 상대 F 곁의 건물
        if MOD_CTRADE and getattr(self, "_sig", None) == "HOSPITAL_RUSH" and own != self.team and c.score(bid) >= 3:
            hs = [c.bpos[b] for b in self.blds if c.btype[b] == "HOSPITAL"]
            if hs and min(c.d(h, c.bpos[bid]) for h in hs) >= 6 and self.enemy_eta.get(bid, INF) >= 3:
                u += CTRADE_BONUS
        return u

    def v18_pressures(self):
        """[A] 적 F 기준 병원(H)·홈 경제(E)·중앙(C) 압력 0~1. 거리 d -> (6-d)/5, 직전 턴보다 멀어지면 x0.6.
        히스테리시스 ON >= 0.5, OFF <= 0.2. [D] 체크메이트 조건도 여기서 판정."""
        c, mem = self.c, self.mem
        groups = {
            "H": [c.bpos[b] for b in self.blds if c.btype[b] == "HOSPITAL" and self.blds[b]["owner"] != self.opp],
            "E": [c.bpos[b] for b in self.home_blds if c.btype[b] in ("HALL", "ENG")],
            "C": [c.bpos[b] for b in self.blds if self.side_center(b)],
        }
        ef = list(self.en["F"])
        prev = mem.__dict__.setdefault("press_d", {})
        on = mem.__dict__.setdefault("press_on", {})
        self._press = {}
        for k, cells in groups.items():
            dmin = min((c.d(e, x) for e in ef for x in cells), default=INF)
            p = 0.0 if dmin >= INF else max(0.0, min(1.0, (6 - dmin) / 5))
            if prev.get(k) is not None and dmin > prev[k]:
                p *= 0.6
            prev[k] = dmin
            self._press[k] = p
            if p >= 0.5:
                on[k] = True
            elif p <= 0.2:
                on[k] = False
            if on.get(k):
                self._stat("press_" + k)
        self._cm = False
        if MOD_CHECKMATE:
            opp_b = [bid for bid, b in self.blds.items() if b["owner"] == self.opp]
            my_sc = sum(c.score(bid) for bid, b in self.blds.items() if b["owner"] == self.team)
            tot = sum(c.score(bid) for bid in self.blds)
            if 0 < len(opp_b) <= CM_MAX and my_sc >= CM_SCORE * tot:
                self._cm = True
                self._stat("cm_turns")

    def v18_radar(self):
        """[C] 거점(광장·아군 쪽 병원·홈 경제·본진) 반경 5 적 W 합 >= RADAR_MIN 이고 접근 중이면 경보.
        적 쪽 최단 경로의 거점 1~2칸 칸에 적 W+1 을 여유 W 로 선집결. 못 채우면 [트레이딩] 포기 + 반대편 가점."""
        if not (MOD_RADAR or MOD_TRADE):
            return
        c, pool, mem = self.c, self.pool, self.mem
        anchors = set([c.base[self.team]] + [c.bpos[b] for b in self.home_blds]
                      + [c.bpos[b] for b in self.blds if c.btype[b] in ("PLAZA", "HOSPITAL")
                         and self.blds[b]["owner"] != self.opp])
        ew = self.en["W"]
        prev = mem.__dict__.setdefault("radar_d", {})
        cents = []
        budget = max(0, self.mb.free)
        for x in sorted(anchors):
            near = [(c.d(e, x), e, k) for e, k in ew.items() if c.d(e, x) <= 5]
            tot = sum(k for _, _, k in near)
            dsum = sum(dd * k for dd, _, k in near)
            approaching = prev.get(x) is not None and tot >= RADAR_MIN and dsum < prev[x]
            prev[x] = dsum if tot >= RADAR_MIN else None
            if not approaching:
                continue
            mine = sum(k for j, k in self.my["W"].items() if c.d(j, x) <= 2)
            if mine >= tot + 1:
                continue                      # 이미 거점 주변 아군 W 가 우세 -> 경보 불필요
            self._stat("radar_alert")
            e0 = min(near)[1]
            D = c.d(e0, x)
            cells = [j for j in range(c.n) if c.passable[j] and 1 <= c.d(j, x) <= 2 and c.d(e0, j) + c.d(j, x) == D]
            need = tot + 1
            got = 0
            if MOD_RADAR and cells:
                scr = min(cells, key=lambda j: (-c.d(j, x), j))
                have = pool.arrive.get(scr, 0)
                want = min(need - have, budget)
                src = sorted((c.d(j, scr), j) for j, n in pool.avail.items() if n > 0 and c.d(j, scr) <= 3)
                if want > 0 and sum(pool.avail[j] for _, j in src) >= want:
                    for _, j in src:
                        if want <= 0:
                            break
                        n = min(want, pool.avail.get(j, 0), pool.left("front"))
                        if n > 0 and pool.send_toward(j, scr, n, None) is not None:
                            want -= n
                            budget -= n
                            got += n
                            self._stat("radar_w", n)
                got += have
            bx = c.bid_at.get(x)
            if MOD_TRADE and got + mine < need and bx is not None and self.blds.get(bx, {}).get("owner") == self.team:
                cents.append(e0)
                self._stat("trade_abandon")
        mem.trade_cents = cents

    def v17c_signature(self):
        """T1~T5: 적 F 마다 가장 가까운 비적 소유 건물(동률이면 무시)을 목표로 보고, 직전 턴보다 가까워진 경우만 표를 준다.
        HOSPITAL_RUSH(병원) / HOME_RAID(아군 홈 ENG·HALL) / CENTER(그 외). 최다 표가 전체의 60% 이상이면 확정, 아니면 None."""
        mem, c = self.mem, self.c
        if "dint_sig" in mem.__dict__ and self.turn > DINT_SIG_TURNS:
            return mem.dint_sig
        votes = mem.__dict__.setdefault("dint_votes", {})
        last = mem.__dict__.setdefault("dint_last", {})
        cand = [bid for bid, b in self.blds.items() if b["owner"] != self.opp]
        for e in self.en["F"]:
            ds = sorted((c.d(e, c.bpos[bid]), bid) for bid in cand)
            if not ds or (len(ds) > 1 and ds[0][0] == ds[1][0]):
                continue
            d0, bid = ds[0]
            if last.get(bid) is not None and d0 >= last[bid]:
                continue
            last[bid] = d0
            t = c.btype[bid]
            k = "HOSPITAL_RUSH" if t == "HOSPITAL" else ("HOME_RAID" if (bid in self.home_blds and t in ("ENG", "HALL")) else "CENTER")
            votes[k] = votes.get(k, 0) + 1
        sig = None
        tot = sum(votes.values())
        if tot:
            k, v = max(votes.items(), key=lambda kv: (kv[1], kv[0]))
            if v >= 0.6 * tot:
                sig = k
        if self.turn >= DINT_SIG_TURNS:
            mem.dint_sig = sig
            if sig:
                self._stat("sig_" + sig)
        return sig

    def v17c_intercept(self):
        """[TEST_1] 적 F 에서 1칸 떨어진 DINT_TYPES 건물(적 소유 아님) X: 적 F 가 다음 턴 밟으면 점령 전 전투로 즉사하도록
        반경 1 의 아군 W 를 X 로 같은 턴에 투입. 필요 W = 1 (X 에 1턴 도달 적 W 가 1기면 2, 2기 이상이면 포기).
        전선 안전장치: 투입 후 여유 W(mb.free)가 음수가 되면 취소. 시그니처 미확정(None)이면 아무것도 안 함."""
        if not MOD_DINT or not self.en["F"]:
            return
        if self.turn > DINT_SIG_TURNS and self.mem.__dict__.get("dint_sig") is None:
            return
        c, pool = self.c, self.pool
        budget = max(0, self.mb.free)
        done = set()
        for e in sorted(self.en["F"]):
            for bid in sorted(self.blds):
                if bid in done or c.btype[bid] not in DINT_TYPES or self.blds[bid]["owner"] == self.opp:
                    continue
                x = c.bpos[bid]
                if c.d(e, x) != 1:
                    continue
                esc = self.threat.enemy[x]
                if esc >= 2:
                    continue
                need = (1 if esc == 0 else 2) - pool.arrive.get(x, 0)
                if need <= 0:
                    done.add(bid)
                    continue
                if need > budget:
                    self._stat("dint_reserve_block")
                    continue
                src = sorted((c.d(j, x), j) for j, n in pool.avail.items() if n > 0 and c.d(j, x) <= 1)
                if sum(pool.avail[j] for _, j in src) < need:
                    continue
                sent = 0
                for _, j in src:
                    if sent >= need:
                        break
                    n = min(need - sent, pool.avail.get(j, 0))
                    if n > 0 and pool.send_toward(j, x, n, None) is not None:
                        sent += n
                if sent:
                    budget -= sent
                    done.add(bid)
                    self._stat("dint_fire")
                    self._stat("dint_w", sent)

    def side_center(self, bid):
        """v16 [B] 중앙 건물: 광장 또는 두 본진에서 거리 차가 2 이하."""
        c = self.c
        if c.btype[bid] == "PLAZA":
            return True
        bi = c.bpos[bid]
        return abs(c.d(c.base[self.team], bi) - c.d(c.base[self.opp], bi)) <= 2

    def _stat(self, key, n=1):
        """v16 계측: 경기 누적 카운터. 턴 끝에 RSTAT 줄로 출력."""
        st = self.mem.__dict__.setdefault("v16stat", {})
        st[key] = st.get(key, 0) + n
        self._stat_dirty = True

    def eov(self, bid, d):
        """v10.4 EOV: 점령 후 예상 유지 턴 x 점수(포화 EOV_CAP), 적 소유면 디나이얼 가치 가산.

        적 F 도착 ETA 는 현재 적 F 와 적 본진 생산(생산 즉시 이동, +1) 중 빠른 쪽.
        상대 건물 탈취는 2단계(중립화 후 점령)이므로 적 도착 후 1턴을 더 유지한다고 본다.
        """
        c = self.c
        bi = c.bpos[bid]
        score = c.score(bid)
        e_eta = min(self.enemy_eta.get(bid, INF), c.d(c.base[self.opp], bi) + 1)
        horizon = max(0, self.turns_left - d)
        hold = min(horizon, max(0, e_eta - d) + 1, EOV_CAP)
        v = EOV_W * score * hold / EOV_CAP
        if DENIAL_W > 0 and self.blds[bid]["owner"] == self.opp:
            v += DENIAL_W * score * min(horizon, EOV_CAP) / EOV_CAP
        return v

    def safety(self, bid, d):
        """Post-Capture Safety. H = 점령 후 적 W가 닿기까지 남는 턴(최대 H_MAX). S(H)/S(H_MAX) 반환."""
        bi = self.c.bpos[bid]
        h = self.enemy_w_eta[bi] - d + 1
        if d >= 4:
            h = max(h, 3)   # 먼 목표는 적 W 위치가 바뀌므로 불확실성 하한
        if self.my_w_eta[bi] <= max(d, 1):
            h += COVER_H_BONUS
        h = max(0, min(H_MAX, h))
        return (h / (h + TAU)) / (H_MAX / (H_MAX + TAU))

    def base_utility(self, a, bid, d):
        c = self.c
        b = self.blds[bid]
        t = b["type"]
        u = c.score(bid) * UTIL_SCORE_W / ((d + 1) ** UTIL_DIST_POW if UTIL_DIST_POW != 1.0 else (d + 1))
        bi = c.bpos[bid]
        if t == "DEPOT" and bid not in self.mem.my_depots:
            # 소프트 락: 적 F보다 늦게 도착하면 보너스를 크게 깎는다
            u += BONUS_DEPOT * (1.0 if d <= self.enemy_eta.get(bid, INF) else DEPOT_CONTESTED_FACTOR)
        elif t == "HALL":
            if MOD_DYN_ECON:
                u += max(1.0, 6.0 * (160 - self.turn) / 160)   # v18 [A] 잔여 턴 비례 감쇄
            else:
                u += BONUS_HALL * min(1.0, self.turns_left / HALL_DECAY_TURNS)
        elif t == "PLAZA":
            u += BONUS_PLAZA
        elif t == "LIBRARY":
            u += self.library_value()
        if bid in self.home_econ and self.econ_slot_open:
            u += HOME_ECON_SLOT_BONUS
        if self.raid is not None and bid == self.raid[0]:
            u += RAID_BONUS
        if b["owner"] == self.opp:
            u += BONUS_RETAKE
            if MOD_GUILLO and t == "ENG" and d <= GUILLO_MAX_D:
                re_eta = min(self.enemy_eta.get(bid, INF), c.d(c.base[self.opp], bi) + 1)
                if re_eta - d >= GUILLO_MIN_ETA:   # 우리가 중립화한 뒤 적 F 재점령까지 GUILLO_MIN_ETA 턴 이상
                    u += GUILLO_BONUS
            if ECON_RAID_ENABLED and t in ECON_RAID_BONUS and self.threat.enemy[bi] == 0:
                u += ECON_RAID_BONUS[t]
            if bid in self.home_blds and (t in HOME_CRITICAL_TYPES or (HOME_ECON_RETAKE and t in ECON_TYPES)):
                u += BONUS_HOME_CRITICAL
            if self.turns_left <= ENDGAME_TURNS and d <= self.turns_left + 1:
                u += c.score(bid) * ENDGAME_NEUTRALIZE_W
                if (bi, "F") in self.enemy_cells:   # 수비 깃발병을 잡으면 같은 턴에 내 소유(2배 효과)
                    u += c.score(bid) * ENDGAME_NEUTRALIZE_W
        if bid not in self.home_blds:
            e_eta = min(self.enemy_eta.get(bid, INF), c.d(c.base[self.opp], bi) + 1)
            if CONTEST_SCALED:
                gap = abs(d - e_eta)
                if gap <= 2:
                    u += BONUS_CONTEST * c.score(bid) / 2.0 * (1.0 - gap / 3.0)
            elif abs(d - e_eta) <= 1:
                u += BONUS_CONTEST
        if (bi, "F") in self.enemy_cells:
            u -= PENALTY_ENEMY_FLAG
        u -= PENALTY_THREAT * self.threat.enemy[bi]
        hm = self.hold_margin(bi)
        if HOLD_ENABLED and hm < 0 and self.turns_left > ENDGAME_TURNS:   # 말기엔 잠깐만 버티면 되므로 검사 생략
            u -= HOLD_PENALTY * (-hm)
        if a.target == bid:
            u += STICKY_BONUS
        if MOD_FLANK and a.uid in getattr(self, "_flank", ()):
            if c.d(c.base[self.opp], bi) < c.d(c.base[self.team], bi) and self.enemy_w_eta[bi] >= FLANK_EW_ETA:
                u += FLANK_BONUS
        return u

    def library_value(self):
        """immediate_cost_cut + expected_future_capture_count 를 할인 가치로 환산. 후반일수록 감쇄."""
        if self.own_library:
            return 0.0  # 중첩 불가
        future = min(self.capturable_count, self.turns_left / LIB_TURNS_PER_CAPTURE)
        return min(LIB_BONUS_CAP, LIB_PER_CAPTURE * (1 + future))

    def choose(self, a):
        """(예약 가능한 최고 건물, 예약 무시한 차선) 반환."""
        c = self.c
        best = shadow = None
        best_u = shadow_u = -INF
        for bid in self.blds:
            if not self.capturable(bid) or a.banned.get(bid, -1) >= self.turn:
                continue
            d = c.d(a.idx, c.bpos[bid])
            if d >= INF or d > self.turns_left + 1:
                continue
            if (HOLD_ENABLED and self.turns_left > ENDGAME_TURNS
                    and self.hold_margin(c.bpos[bid]) < HOLD_SKIP):
                continue
            if (COORD_MODE == "split" and bid in self.home_blds and self.sweeper is not None
                    and a is not self.sweeper and not self.home_emergency):
                continue   # split: 홈 경제는 전담 F 1기만, 나머지는 외곽·보급소
            u = self.utility(a, bid, d)
            holder = self.book.holder(bid)
            if holder is not None and holder != a.uid:
                if COORD_MODE == "hard":
                    continue   # 선점 건물 완전 배제(그림자 추종도 없음)
                if COORD_MODE == "auction":
                    ha = getattr(self, "_agent_by_uid", {}).get(holder)
                    dh = c.d(ha.idx, c.bpos[bid]) if ha is not None else INF
                    if d + COORD_STEAL_MARGIN < dh:   # 더 빨리 도착 -> 우선권(예약 탈취 후보)
                        if u > best_u:
                            best, best_u = bid, u
                        continue
                    u -= COORD_AUCTION_K * (d - dh + 1)
                elif COORD_MODE == "soft":
                    u -= 0.0 if c.btype[bid] in ("PLAZA", "DEPOT") else COORD_SOFT_K / (d + 1)
                else:
                    u -= PENALTY_RESERVED
                if u > shadow_u:
                    shadow, shadow_u = bid, u
            elif u > best_u:
                best, best_u = bid, u
        if COORD_MODE == "soft" and shadow is not None and shadow_u > best_u:
            return None, best_u, shadow   # 감점 후에도 선점 건물이 낫다 -> 백업 진입(그림자 추종)
        return best, best_u, shadow

    def assign(self, a):
        if a is self.sweeper:
            self.assign_sweeper(a)
        else:
            self.assign_front(a)

    def ensure_sweeper(self):
        """홈 전담 F를 유지·지정하고 목표를 배정한다. 홈에 미점령 건물이 없으면 해제(전선 복귀)."""
        mem, c = self.mem, self.c
        if not SWEEPER_ENABLED:
            mem.sweeper_uid = None
            self.sweeper = None
            return None
        if not self.home_pending:
            if mem.sweeper_uid is not None:
                log(f"T{self.turn} home sweep complete, F#{mem.sweeper_uid} -> front")
            mem.sweeper_uid = None
            self.sweeper = None
            return None
        a = next((x for x in self.agents if x.uid == mem.sweeper_uid), None)
        if a is None:
            if len(self.agents) < SWEEPER_MIN_FLAGS:
                self.sweeper = None
                return None
            homes = [c.bpos[bid] for bid in self.home_pending]
            a = min(self.agents, key=lambda x: (min(c.d(x.idx, h) for h in homes), x.uid))
            if mem.sweeper_uid is None or mem.sweeper_uid != a.uid:
                log(f"T{self.turn} home sweeper F#{a.uid} (pending {len(self.home_pending)})")
            mem.sweeper_uid = a.uid
        self.sweeper = a
        self.econ_slot_open = False   # 홈 경제는 전담 F가 맡는다 → 전선 F는 중앙에 집중
        self.assign_sweeper(a)
        return a

    def assign_sweeper(self, a):
        """홈 구역 미점령 건물만 대상. 비용 = 거리 - 유형 가중치 - 유지 가점."""
        c = self.c
        best, best_cost = None, INF
        for bid in self.home_pending:
            if a.banned.get(bid, -1) >= self.turn:
                continue
            holder = self.book.holder(bid)
            if holder is not None and holder != a.uid:
                continue
            d = c.d(a.idx, c.bpos[bid])
            if d >= INF:
                continue
            cost = d - SWEEPER_TYPE_WEIGHT.get(c.btype[bid], 0.0)
            if bid == a.target:
                cost -= SWEEPER_STICKY
            if cost < best_cost:
                best, best_cost = bid, cost
        if best is None or not self.book.reassign(a.uid, a.target, best):
            self.assign_front(a)   # 홈 목표가 모두 막혔으면 이번 턴만 일반 배정
            return
        if best != a.target:
            a.stuck = 0
        a.target, a.util, a.shadow = best, -best_cost, None

    def assign_front(self, a):
        c = self.c
        old = a.target
        best, u, shadow = self.choose(a)
        # v8 Step 4: 히스테리시스. 현재 목표가 유효하면 (새 점수 > 현재 + HYST_F 이고 유지 HYST_F_AGE 턴 이상)일 때만 교체.
        if (old is not None and best is not None and best != old and self.capturable(old)
                and not self.home_emergency and self.book.holder(old) in (None, a.uid)
                and a.banned.get(old, -1) < self.turn):
            d_old = c.d(a.idx, c.bpos[old])
            if d_old < INF and d_old <= self.turns_left + 1:
                u_old = self.utility(a, old, d_old)
                if not (u > u_old + HYST_F and a.age >= HYST_F_AGE):
                    best, u = old, u_old
        evicted = None
        if COORD_MODE == "auction" and best is not None:
            h = self.book.holder(best)
            if h is not None and h != a.uid:
                evicted = getattr(self, "_agent_by_uid", {}).get(h)
                self.book.unassign(h)
                if evicted is not None:
                    evicted.target = None
        if best is not None and self.book.reassign(a.uid, old, best):
            if best != old:
                a.stuck = 0
                a.age = 0
            a.target, a.util, a.shadow = best, u, None
            if MOD_GUILLO and c.btype[best] == "ENG" and self.blds[best]["owner"] == self.opp:
                self._stat("guillo_tgt")
            if MOD_FLANK and a.uid in getattr(self, "_flank", ()):
                self._stat("flank_turns")
            if best in self.home_econ:
                self.econ_slot_open = False  # 홈 경제 슬롯은 1개만 보장
        else:
            self.book.unassign(a.uid)
            a.target, a.util, a.shadow = None, 0.0, shadow
        if evicted is not None and evicted is not self.sweeper and getattr(self, "_auction_depth", 0) < 6:
            self._auction_depth += 1   # 밀려난 F 즉시 재배정(연쇄 상한)
            self.assign_front(evicted)
            self._auction_depth -= 1

    def assign_all(self, agents):
        c = self.c
        self._agent_by_uid = {a.uid: a for a in agents}
        self._auction_depth = 0
        # v8: 유효한 목표의 예약은 유지(서로 목표를 뺏는 순환 방지). 무효 목표만 해제.
        for a in agents:
            if (a.target is None or not self.capturable(a.target)
                    or self.book.holder(a.target) != a.uid or a.banned.get(a.target, -1) >= self.turn):
                self.book.unassign(a.uid)
                if a.target is not None and not self.capturable(a.target):
                    a.target = None

        def order(a):
            on = c.bid_at.get(a.idx)
            capt = on is not None and self.capturable(on)
            pd = c.d(a.idx, c.bpos[a.target]) if a.target in c.bpos else INF
            return (0 if capt else 1, pd, a.uid)

        if MOD_MODES:
            self.evaluate_tactical_mode()
        if MOD_META or MOD_CHECKMATE:
            self.v18_pressures()
        self._sig = self.v17c_signature() if (MOD_DINT or MOD_CTRADE) else None
        if MOD_VETO:
            seen = self.mem.__dict__.setdefault("opp_depot_seen", set())
            seen.update(b for b in self.blds if c.btype[b] == "DEPOT" and self.blds[b]["owner"] == self.opp)
        sweeper = self.ensure_sweeper()   # 홈 전담 F를 먼저 배정해 홈 목표 예약을 확보
        self._flank = set()
        if MOD_FLANK:
            alive = {a.uid for a in agents if a is not sweeper}
            keep = [u_ for u_ in self.mem.__dict__.get("flank_uids", []) if u_ in alive]
            if len(agents) >= FLANK_MIN_F:
                for u_ in sorted(alive, reverse=True):
                    if len(keep) >= FLANK_N:
                        break
                    if u_ not in keep:
                        keep.append(u_)
            else:
                keep = []
            self.mem.flank_uids = keep
            self._flank = set(keep)
        for a in sorted(agents, key=order):
            if a is not sweeper:
                self.assign(a)

    # --- E. 이동·안전
    def secure(self, cell, value=0.0):
        """cell 에 들어가도 NetCombat >= 0 이면 호위를 확정하고 True.

        v8: 아군 W가 0인데 적 W가 닿는 칸(확정 사망 후보)은 거부. 1기 차 열세는 가치가 RISK_ACCEPT 이상이면 감수.
        """
        e = self.threat.enemy[cell]
        pool = self.pool
        if PHALANX_MODE and getattr(self, "_phalanx_f", False):
            # [D3] 공격 F 가 밟을 칸에 (적 도달 W + PHALANX_EXTRA) 를 같은 턴에 겹쳐 넣는다(F 칸·인접 W 에서).
            # 목표 인원을 못 채워도 적 도달 W 이상이면 전진(1:1 상쇄로 F 생존), 그 미만이면 진입 거부.
            have = pool.arrive.get(cell, 0)
            want = e + PHALANX_EXTRA
            if have < want:
                reach = pool.reach(cell)
                if reach >= e and reach > have:
                    got = pool.commit(cell, min(want, reach) - have)
                    self._stat("stack_w", got)
            return pool.arrive.get(cell, 0) >= e
        if FRONTIER_MODE:
            # [D-True] F 칸에 W 를 고정으로 묶지 않는다(호위 커밋 없음). 적 W 가 닿지 않는 칸만 안전.
            if e == 0:
                return True
            # [D2] Pocket: 장벽 W 가 quota(e + 1) + POCKET_SURPLUS 이상 이미 확정된 칸에만 1턴 중첩
            if POCKET and pool.arrive.get(cell, 0) >= e + 1 + POCKET_SURPLUS:
                self._stat("pocket")
                return True
            return False
        if e == 0:
            # [3-A] 안전 구역(D>=2): 호위 0. 경합 구역(D<2): 가용하면 최소 호위만 붙이고 차단하지 않는다.
            if ESCORT_CONTESTED_MIN > 0 and self.mem.meta and self.mem.meta.delta[cell] < 2:
                have = pool.arrive.get(cell, 0)
                if have < ESCORT_CONTESTED_MIN and pool.reach(cell) > have:
                    pool.commit(cell, ESCORT_CONTESTED_MIN - have)
            return True
        req = e + ESCORT_EXTRA          # [3-A] W_req = 적 도달 W (+1: 엄격 계약)
        have = pool.arrive.get(cell, 0)
        if have >= req:
            return True
        reach = pool.reach(cell)
        if reach < req:
            if reach >= e and reach > have:
                pool.commit(cell, reach - have)      # 엄격 계약 미달이지만 동수 이상이면 F는 산다
                return ESCORT_EXTRA == 0
            if reach > 0 and value >= RISK_ACCEPT and e - reach <= 1:
                pool.commit(cell, reach - have)
                return pool.arrive.get(cell, 0) > 0
            return False
        pool.commit(cell, min(req + 1, reach) - have)
        return pool.arrive.get(cell, 0) >= req

    def try_tele(self, a, t):
        c = self.c
        if self.cmds.tele_used >= TELE_CFG["per_turn"] or a.idx not in self.stations:
            return False
        cur = c.d(a.idx, t)
        best, best_d = None, cur
        for s in self.stations:
            if s == a.idx or self.threat.enemy[s] > 0:
                continue
            ds = c.d(s, t)
            if ds + 2 <= best_d:
                best, best_d = s, ds
        if best is not None and self.cmds.tele(a.idx, "F", 1, best, self.stations):
            a.next_idx = best
            return True
        return False

    def plan_flag(self, a, allow_reassign=True):
        c = self.c
        if self.fortress_hold(a):
            return
        if MOD_VETO and self.veto_hold(a):
            return
        if MOD_HYENA and self.hyena_step(a):
            return
        goal_bid = a.target if a.target is not None else a.shadow
        if goal_bid is None:
            cands = [(None, a.idx)] + list(c.nbrs[a.idx])
            t = None
        else:
            t = c.bpos[goal_bid]
            if a.idx == t:
                cands = [(None, a.idx)] + sorted(c.nbrs[a.idx], key=lambda e: c.d(e[1], t))
            else:
                if self.try_tele(a, t):
                    return
                cur = c.d(a.idx, t)
                pen = 0.0 if self.home_emergency else REV_PEN_F * 0.5
                back = OPPOSITE.get(a.last_dir)
                cands = sorted((e for e in c.nbrs[a.idx] if c.d(e[1], t) <= cur + 1),
                               key=lambda e: (c.d(e[1], t) + (pen if e[0] == back else 0.0), e[0] == back))
        if TRANSITION_ENABLED:
            cands = self.transition_order(a, cands, t)
        elif goal_bid is None and EVAC_ENABLED:
            cands = self.evac_order(a, cands)
        passes = (True, False) if TRAP_AVOID else (False,)
        for avoid in passes:
            for d, j in cands:
                if avoid and j != t and self.is_trap(j):
                    continue
                if avoid and HG_MARGIN and (HG_TARGET or j != t) and self.hunted(j):
                    self._stat("hg_skip")
                    continue
                if not self.secure(j, a.util if (t is not None and j == t) else 0.0):
                    if not (MOD_ESCAPE and d is not None and self.yellow_ok(j)):
                        continue
                    self._stat("yellow_enter")
                if d is not None and not self.cmds.move(a.idx, "F", 1, d):
                    continue
                a.next_idx = j
                a.last_dir = d
                if (MOD_HYENA == 2 and t is not None and j == t and a.target is not None
                        and self.blds.get(a.target, {}).get("owner") == self.opp):
                    self._stat("hy_escort_w", self.pool.commit(t, 3))
                if t is not None and (j == t or c.d(j, t) < c.d(a.idx, t)):
                    a.stuck = 0
                return
        # 모든 방향 위험: 제자리가 안전(또는 호위 가능)하면 대기, 아니면 RETREAT
        a.last_dir = None
        safe_stay = self.secure(a.idx)
        if MOD_ESCAPE and not safe_stay and self.escape_red(a, t):
            return
        if not safe_stay and RETREAT_ENABLED and self.retreat(a, t):
            return
        a.next_idx = a.idx
        if DEBUG_STAY and not safe_stay:
            log(f"STAY T{self.turn} {self.c.xy(a.idx)} e={self.threat.enemy[a.idx]} arrive={self.pool.arrive.get(a.idx, 0)} "
                f"reach={self.pool.reach(a.idx)} tgt={a.target} nb_threat={[self.threat.enemy[j] for _, j in self.c.nbrs[a.idx]]}")
        if a.target is None:
            return
        a.stuck += 1
        if a.stuck >= STUCK_LIMIT and allow_reassign:
            old = a.target
            a.banned[old] = self.turn + BAN_TURNS
            self.book.unassign(a.uid, old)
            a.target = None
            a.stuck = 0
            self.assign(a)
            log(f"T{self.turn} F#{a.uid} stuck -> {old} => {a.target}")
            if a.target is not None or a.shadow is not None:
                self.plan_flag(a, allow_reassign=False)

    def transition_order(self, a, cands, t):
        """[3-B] 소유 건물 위 F: 다음 목표 방향 best_exit 타일 → 다음 목표 접근 타일 → 후방 안전 타일 순으로 출발.

        목표가 있으면 같은 거리의 후보 중 best_exit 을 앞으로, 없으면 제자리(건물 위)보다 best_exit 을 먼저 본다.
        """
        c, meta = self.c, self.mem.meta
        bid = c.bid_at.get(a.idx)
        if meta is None or bid is None or self.blds.get(bid, {}).get("owner") != self.team:
            return cands
        exits = meta.best_exit.get(bid, [])
        rank = {j: k for k, j in enumerate(exits)}
        if t is not None and t != a.idx:
            return sorted(cands, key=lambda e: (c.d(e[1], t), rank.get(e[1], 9)))
        moves = [e for e in cands if e[0] is not None]
        moves.sort(key=lambda e: (rank.get(e[1], 9), self.threat.enemy[e[1]], e[1] in c.bid_at))
        stay = [e for e in cands if e[0] is None]
        if self.enemy_w_eta[a.idx] > 3 and not moves:
            return cands
        self.stat_transition = getattr(self, "stat_transition", 0) + 1
        return moves + stay

    def evac_order(self, a, cands):
        """[D] 목표 없는 F: 적 W가 2턴 내 닿는 소유 건물 위라면(깃발 뽑힘 위험) 건물 밖 칸을 먼저 본다."""
        c = self.c
        bid = c.bid_at.get(a.idx)
        if bid is None or self.blds.get(bid, {}).get("owner") != self.team or self.enemy_w_eta[a.idx] > 2:
            return cands
        return sorted(cands, key=lambda e: (e[1] in c.bid_at, self.threat.enemy[e[1]], -self.enemy_w_eta[e[1]]))

    def yellow_ok(self, j):
        """[B] YELLOW: 적 W 가 j 에 동시 도달 가능(1턴)하지만 적 1기 이하이고, j 에서 다음 턴 달아날 칸
        (적 W 1턴 도달 0, 2턴 이상 여유)이 1개 이상이면 진입 허용. 적 2기 이상 동시 도달은 RED 로 본다."""
        c = self.c
        e = self.threat.enemy[j]
        if e == 0 or e > 1:
            return False
        return any(self.threat.enemy[k] == 0 and self.enemy_w_eta_units[k] >= 2 for _, k in c.nbrs[j])

    def escape_red(self, a, t):
        """[B] RED(제자리 1턴 내 적 W 도달 & 지원 부족): 제자리 대기 금지.
        1순위 후퇴(위협 0 & 본진에 가까워짐) -> 2순위 측면(위협 0) -> 3순위 스테이징(아군 W 로 상쇄 가능) -> 최소 열세."""
        c, pool = self.c, self.pool
        home = c.base[self.team]
        here = c.d(a.idx, home)
        best, best_key = None, None
        for d, j in c.nbrs[a.idx]:
            e = self.threat.enemy[j]
            if e == 0 and c.d(j, home) < here:
                tier = 0
            elif e == 0:
                tier = 1
            elif pool.reach(j) >= e:
                tier = 2
            else:
                tier = 3
            key = (tier, e - pool.reach(j), -self.enemy_w_eta_units[j], d)
            if best_key is None or key < best_key:
                best, best_key = (d, j), key
        if best is None:
            return False
        stay_def = self.threat.enemy[a.idx] - pool.reach(a.idx)
        if best_key[0] == 3 and best_key[1] >= stay_def:
            return False
        d, j = best
        if best_key[0] == 2:
            self.secure(j)
        if not self.cmds.move(a.idx, "F", 1, d):
            return False
        a.next_idx = j
        a.last_dir = d
        self._stat("red_" + ("retreat", "lateral", "staging", "least")[best_key[0]])
        return True

    def evaluate_tactical_mode(self):
        """[v18] 매 턴 1회 전황 평가 -> 주 모드 1개(우선순위: BASE_EMERGENCY > ENDGAME_LOCK > COUNTER_DEATHBALL >
        OPENING_RACE > EXPANSION_TEMPO). LOCAL_GUARD 는 건물 단위 오버레이(anchor_w)로 동시 작동.
        예외 시 EXPANSION_TEMPO(= v17b1 기본 행동)로 폴백."""
        self._mode, self._dball = "EXPANSION_TEMPO", None
        try:
            c, mem = self.c, self.mem
            econ = [c.bpos[b] for b in self.home_blds
                    if c.btype[b] in ("HALL", "ENG") and self.blds[b]["owner"] == self.team]
            enemy = list(self.en["F"]) + list(self.en["W"])
            emergency = bool(econ and enemy and min(c.d(e, h) for e in enemy for h in econ) <= P4_EMERGENCY_DIST)
            ew = self.en["W"]
            if sum(ew.values()) >= P3_DEATHBALL_TRIGGER_W:
                best = None
                for e in ew:
                    tot = sum(k for j, k in ew.items() if c.cheb(e, j) <= 1)
                    if tot >= P3_DEATHBALL_TRIGGER_W and (best is None or tot > best[0]):
                        best = (tot, e)
                if best is not None:
                    mine = [c.bpos[b] for b, v in self.blds.items() if v["owner"] == self.team] + [c.base[self.team]]
                    if min(c.d(best[1], m) for m in mine) <= 4:
                        self._dball = best[1]
            if self._dball is not None:
                mem.db_last = (self.turn, self._dball)
            elif mem.__dict__.get("db_last") and self.turn - mem.db_last[0] <= DB_DWELL:
                self._dball = mem.db_last[1]             # 히스테리시스: 경보 해제 후 DB_DWELL 턴 유지(모드 깜빡임 방지)
            my_sc = sum(c.score(b) for b, v in self.blds.items() if v["owner"] == self.team)
            op_sc = sum(c.score(b) for b, v in self.blds.items() if v["owner"] == self.opp)
            if emergency:
                mode = "BASE_EMERGENCY"
            elif self.turn >= P5_ENDGAME_TRIGGER_TURN and my_sc > op_sc:
                mode = "ENDGAME_LOCK"
            elif self._dball is not None:
                mode = "COUNTER_DEATHBALL"
            elif self.turn <= OPENING_RACE_TURNS:
                mode = "OPENING_RACE"
            else:
                mode = "EXPANSION_TEMPO"
            prev = mem.__dict__.get("mode")
            if prev != mode:
                log(f"MODE T{self.turn} {prev} -> {mode}")
                mem.mode = mode
            self._mode = mode
            self._stat("mode_" + mode)
        except Exception:
            log("MODE router error -> EXPANSION_TEMPO\n" + traceback.format_exc())
            self._mode, self._dball = "EXPANSION_TEMPO", None

    def mode_bonus(self, bid, t, d, own):
        """[v18] 모드별 F 효용 가감."""
        c = self.c
        m = getattr(self, "_mode", "EXPANSION_TEMPO")
        u = 0.0
        if m == "OPENING_RACE" and own != self.team:
            if t == "DEPOT" and bid not in self.mem.my_depots:
                u += P1_DEPOT_RACE_WEIGHT
            elif t == "PLAZA":
                u += 0.5 * P1_DEPOT_RACE_WEIGHT
        elif m == "COUNTER_DEATHBALL" and self._dball is not None:
            dd = c.d(self._dball, c.bpos[bid])
            if dd <= DB_AVOID_DIST:
                u -= DB_AVOID_PEN
            elif dd >= DB_RAID_DIST and own != self.team:
                u += DB_RAID_BONUS
        elif m == "ENDGAME_LOCK" and own != self.team and d > LOCK_FAR:
            u -= LOCK_PEN * (d - LOCK_FAR)
        return u

    def anchor_w(self):
        """[v17b3] 이번 턴 아군 소유 건물을 떠나는 F 마다, 적 F 가 ANCHOR_F_DIST 이내면 건물 칸에 W 1기(칸 위 W 우선,
        없으면 인접 W)만 남긴다. 이미 도착 확정 W 가 있으면 추가하지 않음. 매 턴 새로 판정."""
        if not (MOD_ANCHOR or MOD_MODES) or not self.en["F"]:
            return
        c, pool = self.c, self.pool
        cap = P2_ANCHOR_W_MAX if MOD_MODES else 1
        guarded = 0
        for a in self.agents:
            if a.next_idx is None or a.next_idx == a.idx:
                continue
            bid = c.bid_at.get(a.idx)
            if bid is None or self.blds.get(bid, {}).get("owner") != self.team:
                continue
            if min(c.d(e, a.idx) for e in self.en["F"]) > ANCHOR_F_DIST:
                continue
            e = self.threat.enemy[a.idx]
            if not MOD_MODES:
                cap = ANCHOR_W_MAX
            if (MOD_MODES or cap > 1) and e > cap:
                continue                                   # 적 W 우세: 알박기 불가(F 는 이미 전진)
            want = max(1, e) if (MOD_MODES or cap > 1) else 1
            if pool.arrive.get(a.idx, 0) >= want:
                continue
            got = pool.commit(a.idx, min(cap, want) - pool.arrive.get(a.idx, 0))
            self._stat("anchor_w" if got else "anchor_none", max(1, got))
            if got:
                guarded += 1
                if MOD_MODES and DEBUG_MODES:
                    log(f"MODE T{self.turn} LOCAL_GUARD anchor W{got} at {c.xy(a.idx)}")
        if MOD_MODES and guarded:
            self._stat("mode_LOCAL_GUARD")
        if MOD_GUARD_ALL:
            leaving = {a.idx for a in self.agents}
            for bid, b in self.blds.items():
                if b["owner"] != self.team:
                    continue
                x = c.bpos[bid]
                if x in leaving or pool.arrive.get(x, 0) >= 1 or (x, "F") in self.enemy_cells:
                    continue
                if min(c.d(e, x) for e in self.en["F"]) > ANCHOR_F_DIST:
                    continue
                if self.threat.enemy[x] > 0:
                    continue                               # 적 W 가 닿는 칸은 1기로 못 지킴
                if pool.reach(x) - pool.arrive.get(x, 0) <= 0:
                    continue
                got = pool.commit(x, 1)
                self._stat("guard_all_w", got)

    def veto_hold(self, a):
        """[v17b2] 아군 소유 건물 위 F 가 떠나려 할 때 1턴 Veto.
        GREEN(적 F 없음) -> 기존 이동. YELLOW(칸 도달 적 W <= 아군 W, 인접 유휴 W 로 부족분만 보충 가능) -> 1턴 잔류.
        RED(보충 불가) -> 기존 회피 로직. 매 턴 새로 판정(지속 HOLD 없음)."""
        c = self.c
        bid = c.bid_at.get(a.idx)
        if bid is None or self.blds.get(bid, {}).get("owner") != self.team or not self.en["F"]:
            return False
        g = a.target if a.target is not None else a.shadow
        if g is not None and c.bpos.get(g) == a.idx:
            return False
        hi = c.btype[bid] == "DEPOT" and bid not in self.mem.__dict__.get("opp_depot_seen", set())
        lim = VETO_DEPOT_DIST if hi else VETO_F_DIST
        if min(c.d(e, a.idx) for e in self.en["F"]) > lim:
            return False                                   # GREEN
        pool = self.pool
        e = self.threat.enemy[a.idx]
        have = pool.arrive.get(a.idx, 0)
        if e > have:
            if pool.reach(a.idx) < e:
                self._stat("veto_red")
                return False                               # RED: 잔류하면 F 사망
            got = pool.commit(a.idx, e - have)             # 부족분만 인접 W 로
            self._stat("veto_w", got)
            if pool.arrive.get(a.idx, 0) < e:
                return False
        a.next_idx = a.idx
        a.last_dir = None
        self._stat("veto_hold_depot" if hi else "veto_hold")
        return True

    def hyena_step(self, a):
        """[샌드백] 목표가 상대 소유이고 상대 F 가 그 위에 있으며 우리 F 가 인접이면 대기(경합 회피), 떠나면 진입.
        H3 은 2턴째 대기하면 다른 건물로 선회."""
        c = self.c
        if a.target is None or self.blds.get(a.target, {}).get("owner") != self.opp:
            return False
        t = c.bpos[a.target]
        if (t, "F") not in self.enemy_cells or c.d(a.idx, t) != 1:
            return False
        waits = self.mem.__dict__.setdefault("hy_wait", {})
        if MOD_HYENA == 3:
            waits[a.uid] = waits.get(a.uid, 0) + 1
            if waits[a.uid] >= 2:
                waits[a.uid] = 0
                old = a.target
                a.banned[old] = self.turn + 6
                self.book.unassign(a.uid, old)
                a.target = None
                self.assign(a)
                self._stat("hy_fake")
                return False
        a.next_idx = a.idx
        a.last_dir = None
        self._stat("hy_wait")
        return True

    def hunted(self, j):
        c = self.c
        e = sum(n for x, n in self.en["W"].items() if c.d(x, j) <= HG_R)
        if e < HG_MARGIN:
            return False
        m = sum(n for x, n in self.my["W"].items() if c.d(x, j) <= HG_R - 1)
        return e - m >= HG_MARGIN

    def is_trap(self, j):
        """v10.4 2턴 함정: j 에 들어간 뒤 다음 턴에 갈 수 있는 칸(j 와 이웃) 모두가 적 W 2턴 도달권이고,
        그 어느 칸에도 아군 W가 1턴 안에 닿지 못하면 함정."""
        ew = self.enemy_w_eta if TRAP_SPAWN else self.enemy_w_eta_units
        mw = self.my_w_eta
        if ew[j] > 2:
            return False
        for _, k in self.c.nbrs[j]:
            if ew[k] > 2 or mw[k] <= 1:
                return False
        return mw[j] > 1

    def retreat(self, a, t):
        """[D] RETREAT: 제자리 사망 위험. 적 W 1턴 도달 0 칸 → 호위 가능 칸 → 최소 열세 칸 순으로 이탈."""
        c, pool = self.c, self.pool
        best, best_key = None, None
        for d, j in c.nbrs[a.idx]:
            e = self.threat.enemy[j]
            deficit = e - pool.reach(j) if e else -1
            key = (e > 0, deficit, -self.enemy_w_eta[j], c.d(j, t) if t is not None else 0, d)
            if best_key is None or key < best_key:
                best, best_key = (d, j), key
        if best is None:
            return False
        stay_def = self.threat.enemy[a.idx] - pool.reach(a.idx)
        d, j = best
        if best_key[0] and best_key[1] >= stay_def:
            return False   # 이탈해도 나아지지 않음
        if best_key[0]:
            self.secure(j)
        if not self.cmds.move(a.idx, "F", 1, d):
            return False
        a.next_idx = j
        a.last_dir = d
        self.stat_retreat = getattr(self, "stat_retreat", 0) + 1
        return True

    def escort_slots(self):
        """v12: 이동이 정해진 F 마다, 다음 칸까지 적 W ETA <= ESCORT_TRIGGER_ETA 이고 이미 확정된 W 가 없으면
        F 에서 ESCORT_RADIUS 이내(가까운 순)의 W 를 최대 ESCORT_SLOTS 기 F 의 다음 칸으로 동행시킨다."""
        pool, c = self.pool, self.c
        ew = self.enemy_w_eta_units
        if ESCORT_ORDER == "danger":      # v27: 다음 칸에 적 W 가 가장 빨리 닿는 F 부터
            order = sorted(self.agents, key=lambda a: (ew[a.next_idx if a.next_idx is not None else a.idx], -a.util, a.uid))
        elif ESCORT_ORDER == "capture":   # v27: 다음 칸이 목표 건물(이번 턴 점령)인 F 부터
            order = sorted(self.agents, key=lambda a: (not (a.target is not None and a.next_idx == self.c.bpos.get(a.target)),
                                                        -a.util, a.uid))
        else:
            order = sorted(self.agents, key=lambda a: (-a.util, a.uid))
        for a in order:
            if a.target is None:
                continue
            nxt = a.next_idx if a.next_idx is not None else a.idx
            if ew[nxt] > ESCORT_TRIGGER_ETA:
                continue
            have = pool.arrive.get(nxt, 0)
            need = ESCORT_SLOTS - have
            if need <= 0:
                continue
            src = sorted((c.d(j, a.idx), j) for j, k in pool.avail.items()
                         if k > 0 and c.d(j, a.idx) <= ESCORT_RADIUS)
            for _, j in src:
                if need <= 0:
                    break
                k = min(need, pool.avail.get(j, 0))
                if k > 0 and pool.send_toward(j, nxt, k, self.threat) is not None:
                    need -= k
                    self.stat_escort = getattr(self, "stat_escort", 0) + k

    def move_flags(self):
        c = self.c

        def order(a):
            g = a.target if a.target is not None else a.shadow
            t = c.bpos[g] if g is not None else a.idx
            return (0 if a.idx == t and a.target is not None else 1, c.d(a.idx, t), a.uid)

        for a in sorted(self.agents, key=order):
            if self.clock.over():
                break
            if a.next_idx is not None:   # 스나이프 등으로 이미 이동 확정
                continue
            # [D3] 공격 F(홈 전담 제외, 목표 보유)만 동일 칸 스택 동행 안전 판정을 쓴다
            self._phalanx_f = PHALANX_MODE and a is not self.sweeper and a.target is not None
            self.plan_flag(a)
            self._phalanx_f = False

    # --- 전투병: 상위 예산 기반 전술
    def home_alert(self):
        """홈 구역 건물에서 HOME_ALERT_DIST 칸 안에 들어온 적 유닛 수와 그중 W 수."""
        c = self.c
        homes = [c.bpos[bid] for bid in self.home_blds]
        units = w = 0
        for kind, stacks in self.en.items():
            for e, k in stacks.items():
                if any(c.d(e, h) <= HOME_ALERT_DIST for h in homes):
                    units += k
                    if kind == "W":
                        w += k
        return units, w

    def home_requirement(self):
        """홈 방어 쿼터. 침투가 있으면 비상 방어(침투 W 수, 1~3), 없으면 초반 0 / 이후 1."""
        units, w = self.home_alert()
        self.force_w = 0
        self.home_emergency = self.update_home_alarm() if HOME_HYST_ENABLED else units > 0
        if not FUTURE_PROD_ENABLED:
            if units:
                return max(REQUIRED_HOME_DEFENSE, min(HOME_ALERT_MAX_W, w))
            return 0 if self.turn <= EARLY_TURNS else REQUIRED_HOME_DEFENSE
        can_spawn = self.view.my_resource // self.w_cost
        if units:
            # v7: 침투가 생산 거점 근처면 이번 턴 생산분(생산 후 즉시 이동)으로 대응하고 기존 W는 전선 유지
            c = self.c
            near = all(min(c.d(e, s_) for s_ in self.my_spawn_sites) <= HOME_SPAWN_NEAR
                       for kind in ("W", "F") for e in self.en[kind]
                       if any(c.d(e, c.bpos[b]) <= HOME_ALERT_DIST for b in self.home_blds))
            if near and can_spawn >= w + 1:
                self.force_w = w + 1
                return 0
            return max(REQUIRED_HOME_DEFENSE, min(HOME_ALERT_MAX_W, w))
        if self.turn <= EARLY_TURNS or can_spawn >= 2:
            return 0   # v7: 다음 생산으로 대응 가능하면 상시 홈 쿼터 없음
        return REQUIRED_HOME_DEFENSE

    def detect_deathballs(self):
        """적 W 3x3 클러스터 >= DB_THRESHOLD 이고 아군 건물·본진 DB_RANGE 이내면 [(중심, 크기, 예상 목표 idx)]."""
        c = self.c
        ew = self.en["W"]
        if sum(ew.values()) < DB_THRESHOLD:
            return []
        mine = [c.bpos[b["id"]] for b in self.blds.values() if b["owner"] == self.team] + [c.base[self.team]]
        cells = list(ew)
        clus = []
        for e in cells:
            tot = sum(k for j, k in ew.items() if c.cheb(e, j) <= 1)
            if tot >= DB_THRESHOLD:
                clus.append((tot, ew[e], e))
        balls, used = [], set()
        for tot, _, e in sorted(clus, reverse=True):
            if any(c.cheb(e, u) <= 2 for u in used):
                continue
            tgt = min(mine, key=lambda m: (c.d(e, m), m))
            if c.d(e, tgt) > DB_RANGE:
                continue
            used.add(e)
            balls.append((e, tot, tgt))
        if balls and (self.turn % 5 == 0 or DEBUG):
            log(f"T{self.turn} deathball {[(c.xy(e), n, c.xy(t)) for e, n, t in balls]}")
        return balls

    def deathball_defense(self):
        """맞불 집결: 공의 예상 목표 건물에 공 크기 이상을 모을 수 있으면 집결, 아니면 개별 투입 금지(지연)."""
        if not self.balls or not DB_MASS_ENABLED:
            return
        pool, c = self.pool, self.c
        for e, size, tgt in self.balls:
            eta = c.d(e, tgt)
            src = sorted((c.d(j, tgt), j) for j, k in pool.avail.items() if k > 0 and c.d(j, tgt) <= eta + 1)
            have = pool.arrive.get(tgt, 0) + sum(pool.avail[j] for _, j in src)
            if have < size * DB_MASS_RATIO:
                continue
            for _, j in src:
                pool.send_toward(j, tgt, pool.avail.get(j, 0), self.threat)
            self.stat_dbmass = getattr(self, "stat_dbmass", 0) + 1

    def opening_step(self):
        """[2] 오프닝 실행: HARD(1~2턴) / SOFT(3~5턴, 아키타입 판별) / 이후 일반 AI. 이탈 감지 시 즉시 종료."""
        mem, c = self.mem, self.c
        self.macro = None
        if not mem.opening_active or mem.opening is None or self.turn > OPENING_SOFT_TURNS:
            mem.opening_active = mem.opening_active and self.turn <= OPENING_SOFT_TURNS
            return
        reason = None
        if any(c.d(e, c.base[self.team]) <= DEV_W_BASE_ETA for e in self.en["W"]):
            reason = "enemy W near base"
        halls = [c.bpos[b] for b in self.home_blds if c.btype[b] == "HALL"]
        if reason is None and halls and self.en["F"]:
            if min(c.d(e, h) for e in self.en["F"] for h in halls) <= DEV_F_HALL_ETA:
                reason = "enemy F near home hall"
        if reason is None:
            for a in self.agents:
                if a.target is None:
                    continue
                t = c.bpos[a.target]
                mine = self.my["W"].get(t, 0) + sum(self.my["W"].get(j, 0) for _, j in c.nbrs[t])
                if self.threat.enemy[t] > mine and c.d(a.idx, t) <= 2:
                    reason = "enemy W superior at F objective"
                    break
        if reason is not None:
            mem.opening_active = False
            log(f"T{self.turn} opening abort: {reason}")
            return
        if self.turn <= OPENING_HARD_TURNS:
            self.macro = mem.opening.macro(self.turn)
        else:
            mem.arch = opening.classify(self.view.units, self.team, c, self.turn)
            self.macro = mem.opening.macro(self.turn, mem.arch)
        mem.macro_log.append((self.turn, mem.arch, self.macro))
        if DEBUG:
            log(f"T{self.turn} opening macro={self.macro} arch={mem.arch}")

    def update_home_alarm(self):
        """[E] 위협 분리 + 히스테리시스. 진입: ETA <= HOME_ENTER_ETA / 해제: ETA >= HOME_EXIT_ETA 가 HOME_CONFIRM 턴 유지."""
        c, mem = self.c, self.mem
        owned_home = [c.bpos[b] for b in self.home_blds
                      if b in self.blds and self.blds[b]["owner"] == self.team]
        if not owned_home:
            mem.home_alarm, mem.home_calm = False, 0
            return False
        ef = [min((c.d(e, h) for e in self.en["F"]), default=INF) for h in owned_home]
        ew = [self.enemy_w_eta[h] if not (self.enemy_w_eta[h] == 0 and h not in self.en["W"]) else INF
              for h in owned_home]
        f_eta = min(ef)
        w_eta_def = min((ew[k] for k, h in enumerate(owned_home) if self.my["F"].get(h)), default=INF)
        capture_threat = f_eta <= HOME_ENTER_ETA
        combat_threat = w_eta_def <= 1
        if capture_threat or combat_threat:
            mem.home_alarm, mem.home_calm = True, 0
        elif mem.home_alarm:
            if f_eta >= HOME_EXIT_ETA and w_eta_def >= HOME_EXIT_ETA:
                mem.home_calm += 1
                if mem.home_calm > HOME_CONFIRM - 1 and mem.home_calm >= HOME_CONFIRM:
                    mem.home_alarm, mem.home_calm = False, 0
            else:
                mem.home_calm = 0
        return mem.home_alarm

    def home_defense(self):
        """home 쿼터를 소유 홈 경제 건물(없으면 소유 홈 건물, 그것도 없으면 본진) 중 적과 가장 가까운 곳에 둔다."""
        pool, c = self.pool, self.c
        if pool.left("home") <= 0:
            return
        owned = [bid for bid in self.home_blds
                 if bid in self.blds and self.blds[bid]["owner"] == self.team]
        anchors = [c.bpos[bid] for bid in owned if bid in self.home_econ]
        if not anchors:
            anchors = [c.bpos[bid] for bid in owned] or [c.base[self.team]]
        enemies = [i for i, _ in self.enemy_cells]
        anchor = min(anchors, key=lambda a: (min((c.d(e, a) for e in enemies), default=INF), a))
        for dist, j in sorted((c.d(j, anchor), j) for j, k in pool.avail.items() if k > 0):
            if pool.left("home") <= 0 or dist >= INF:
                break
            pool.send_toward(j, anchor, pool.left("home"), self.threat, role="home")

    def depot_intercept(self):
        """조건부 보급소 인터셉트(W 2기). 조건이 하나라도 어긋나면 이번 턴 임무 없음 → 전선 복귀."""
        pool, c, mem = self.pool, self.c, self.mem
        mission = None
        if pool.left("special") >= SPECIAL_SQUAD and self.en["F"]:
            for bid in sorted(self.blds, key=lambda b: (self.enemy_eta.get(b, INF), b)):
                b = self.blds[bid]
                if b["type"] != "DEPOT" or b["owner"] == self.opp or bid in mem.enemy_depots:
                    continue
                eta_f = self.enemy_eta.get(bid, INF)
                if eta_f > INTERCEPT_MAX_ETA:
                    continue
                # 1. 적 F가 보급소로 접근 중
                if not (eta_f < self.prev_enemy_eta.get(bid, INF) or eta_f <= 1):
                    continue
                bi = c.bpos[bid]
                e = min(self.en["F"], key=lambda e: (c.d(e, bi), e))
                # 3. 적 F 주변 1칸 호위 W 1기 이하
                escort = self.en["W"].get(e, 0) + sum(self.en["W"].get(j, 0) for _, j in c.nbrs[e])
                if escort > 1:
                    continue
                # 2. our_W_intercept_eta <= enemy_F_eta 인 W가 2기 이상
                src = sorted((c.d(j, bi), j) for j, k in pool.avail.items()
                             if k > 0 and c.d(j, bi) <= eta_f)
                if sum(pool.avail[j] for _, j in src) < SPECIAL_SQUAD:
                    continue
                mission = (bid, bi, src)
                break
        if mission is None:
            if mem.intercept is not None:
                log(f"T{self.turn} intercept released {mem.intercept}")
            mem.intercept = None
            return
        bid, bi, src = mission
        if mem.intercept != bid:
            log(f"T{self.turn} intercept depot {bid} eta_f={self.enemy_eta[bid]} eta_w={src[0][0]}")
        mem.intercept = bid
        need = SPECIAL_SQUAD
        for _, j in src:
            if need <= 0:
                break
            k = min(need, pool.avail.get(j, 0))
            if k > 0 and pool.send_toward(j, bi, k, None, role="special") is not None:
                need -= k

    # --- v8 Step 2: UNIVERSAL_SNIPE
    def plan_snipes(self):
        """적 F가 서 있거나 이번 턴 진입이 유력한(ETA 1) 건물을 [아군 W + 아군 F 1기] 동시 진입으로 낚아챈다.

        조건: 이동 후 그 칸의 아군 W >= 적 W 최대 도달 수 + 1, 아군 F가 이번 턴 도달(거리 <= 1).
        적 F가 전투로 제거되면 적 소유 건물은 즉시 중립 → 같은 턴 점령 단계에서 내 소유.
        비용은 이 단계에서 목표로 배정해 두어 reserved_capture 가 예약한다.
        """
        if not SNIPE_ENABLED or not self.en["F"]:
            return
        c = self.c
        cands = {}
        for e in self.en["F"]:
            spots = []
            bid = c.bid_at.get(e)
            if bid in self.blds:
                spots.append((bid, True))
            for _, j in c.nbrs[e]:
                b2 = c.bid_at.get(j)
                if b2 in self.blds and self.blds[b2]["owner"] != self.opp:
                    spots.append((b2, False))
            for bid, on in spots:
                b = self.blds[bid]
                if b["owner"] == self.team:
                    continue   # 아군 건물 방어는 defend/hunt 담당
                bi = c.bpos[bid]
                need = self.threat.enemy[bi] + 1
                have = self.my["W"].get(bi, 0) + sum(self.my["W"].get(j, 0) for _, j in c.nbrs[bi])
                if have < need:
                    continue
                val = c.score(bid) * (2.0 if (on and b["owner"] == self.opp) else 1.0) + (3.0 if on else 0.0)
                if bid not in cands or cands[bid][0] < val:
                    cands[bid] = (val, bi, need)
        used = set()
        for bid, (val, bi, need) in sorted(cands.items(), key=lambda kv: (-kv[1][0], kv[0])):
            flags = [a for a in self.agents if a.uid not in used and c.d(a.idx, bi) <= 1]
            if not flags:
                continue
            a = min(flags, key=lambda x: (0 if x.target == bid else 1, c.d(x.idx, bi), x.uid))
            holder = self.book.holder(bid)
            if holder is not None and holder != a.uid:
                self.book.unassign(holder)
                other = next((x for x in self.agents if x.uid == holder), None)
                if other is not None:
                    other.target = None
            if a.target != bid:
                a.age = 0
            self.book.unassign(a.uid)
            self.book.assign(a.uid, bid)
            a.target, a.util, a.shadow = bid, SNIPE_VALUE + val, None
            a.snipe = bi
            used.add(a.uid)
            self.snipes.append(a)
            log(f"T{self.turn} snipe plan {bid} val={val:.1f} need_w={need} F#{a.uid}")
        # 목표를 뺏긴 F 재배정
        for x in self.agents:
            if x.target is None and x.uid not in used:
                self.assign(x)

    def exec_snipes(self):
        """스나이프 실행: W 커밋이 확보된 경우에만 F 진입. 실패하면 일반 이동으로 넘긴다."""
        pool, c = self.pool, self.c
        for a in self.snipes:
            bi = a.snipe
            need = self.threat.enemy[bi] + 1
            have = pool.arrive.get(bi, 0)
            if have < need and pool.reach(bi) >= need:
                pool.commit(bi, need - have)
            if pool.arrive.get(bi, 0) < need:
                a.snipe = None
                continue
            if a.idx != bi:
                d = next((dd for dd, j in c.nbrs[a.idx] if j == bi), None)
                if d is None or not self.cmds.move(a.idx, "F", 1, d):
                    a.snipe = None
                    continue
            a.next_idx = bi
            self.stat_snipe = getattr(self, "stat_snipe", 0) + 1

    # --- v8 Step 2: INTERCEPT (보급소 한정 → 고가치 건물 일반화)
    def intercept_worthy(self, bid):
        t = self.c.btype[bid]
        if t == "DEPOT" and bid not in self.mem.enemy_depots:
            return True
        if INTERCEPT_DEPOT_ONLY:
            return False
        return t in ("HALL", "PLAZA") or self.c.score(bid) >= 3

    def intercept(self):
        """적 F가 접근 중인 고가치 건물에, 적 F보다 먼저(또는 동시) 도착할 수 있는 W를 선배치한다."""
        if not INTERCEPT_ENABLED or not self.en["F"]:
            return
        pool, c = self.pool, self.c
        missions = []
        for bid, b in self.blds.items():
            if b["owner"] == self.opp or not self.intercept_worthy(bid):
                continue
            eta_f = self.enemy_eta.get(bid, INF)
            if eta_f > INTERCEPT_MAX_ETA:
                continue
            if not (eta_f < self.prev_enemy_eta.get(bid, INF) or eta_f <= 1):
                continue
            bi = c.bpos[bid]
            e = min(self.en["F"], key=lambda e: (c.d(e, bi), e))
            escort = self.en["W"].get(e, 0) + sum(self.en["W"].get(j, 0) for _, j in c.nbrs[e])
            squad = max(INTERCEPT_SQUAD, escort + 1)
            src = sorted((c.d(j, bi), j) for j, k in pool.avail.items() if k > 0 and c.d(j, bi) <= eta_f)
            if sum(pool.avail[j] for _, j in src) < squad:
                continue
            val = c.score(bid) + (BONUS_DEPOT if b["type"] == "DEPOT" else 0) + (3 if b["owner"] == self.team else 0)
            missions.append((-val / (eta_f + 1), bid, bi, squad))
        for _, bid, bi, squad in sorted(missions)[:INTERCEPT_MAX]:
            need = squad - pool.arrive.get(bi, 0)
            src = sorted((c.d(j, bi), j) for j, k in pool.avail.items() if k > 0)
            eta_f = self.enemy_eta.get(bid, INF)
            for dist, j in src:
                if need <= 0 or dist > eta_f:
                    break
                k = min(need, pool.avail.get(j, 0))
                if k > 0 and pool.send_toward(j, bi, k, None, role="special") is not None:
                    need -= k

    def check_hospital_raid_viable(self):
        """상대 병원 기습 가능 여부. (병원 id, 가장 가까운 아군 역 idx, 거리) 또는 None.

        조건: 소유 역 >= min_stations, 병원 수비 병력 0(RAID_DEFENSE_RANGE 안 적 W 없음·위협 0),
        병원 근처(RAID_STATION_RANGE) 아군 역 존재, 기습 후에도 free_W >= RAID_MIN_FREE_W.
        점령 턴에는 생산이 불가하고 다음 턴부터 가능하므로 점령 후 생존이 필요하다.
        """
        if len(self.stations) < TELE_CFG["min_stations"] or self.mb.free < RAID_MIN_FREE_W:
            return None
        c = self.c
        best = None
        for bid, b in self.blds.items():
            if b["type"] != "HOSPITAL" or b["owner"] != self.opp:
                continue
            hi = c.bpos[bid]
            if self.threat.enemy[hi] > 0:
                continue
            if any(c.d(j, hi) <= RAID_DEFENSE_RANGE for j in self.en["W"]):
                continue
            ds, s = min(((c.d(s, hi), s) for s in self.stations), default=(INF, None))
            if ds > RAID_STATION_RANGE:
                continue
            if best is None or ds < best[2]:
                best = (bid, s, ds)
        return best

    def raid_support(self):
        """기습 활성 시 남은 special 쿼터로 병원에 W를 보내 점령 후 생존(Hold)을 돕는다."""
        pool, c = self.pool, self.c
        if self.raid is None or pool.left("special") <= 0:
            return
        hi = c.bpos[self.raid[0]]
        for _, j in sorted((c.d(j, hi), j) for j, k in pool.avail.items() if k > 0):
            if pool.left("special") <= 0:
                break
            pool.send_toward(j, hi, pool.left("special"), self.threat, role="special")

    def stage_retreat(self, j):
        """[C] 집결 칸 j 가 이번 턴 열세로 위협받으면(적 W 도달 > 아군) 위협이 가장 낮은 이웃으로 후퇴."""
        pool, c = self.pool, self.c
        k = pool.avail.get(j, 0)
        e = self.threat.enemy[j]
        if k <= 0 or e == 0 or e <= k + pool.arrive.get(j, 0) - 1 or self.home_emergency:
            return False
        if j in self.en["F"]:
            return False   # 적 F가 있는 칸은 사냥 대상
        best = min(c.nbrs[j], key=lambda e_: (self.threat.enemy[e_[1]], -self.enemy_w_eta[e_[1]], e_[0]), default=None)
        if best is None or self.threat.enemy[best[1]] >= e:
            return False
        if not self.cmds.move(j, "W", k, best[0]):
            return False
        pool.avail[j] -= k
        pool.arrive[best[1]] = pool.arrive.get(best[1], 0) + k
        self.stat_wretreat = getattr(self, "stat_wretreat", 0) + k
        return True

    def tele_w(self, j, g, cnt):
        """[F] TELE 최소 투입: 목표 R_projected >= R_ENTER 에 필요한 최소 W(최대 5)만 역 -> 역 순간이동."""
        c, pool = self.c, self.pool
        if (self.cmds.tele_used >= TELE_CFG["per_turn"] or j not in self.stations
                or len(self.stations) < TELE_CFG["min_stations"]):
            return False
        cur = c.d(j, g)
        best, best_d = None, cur
        for s_ in self.stations:
            if s_ == j or self.threat.enemy[s_] > 0:
                continue
            ds = c.d(s_, g)
            if ds + 2 <= best_d:
                best, best_d = s_, ds
        if best is None:
            return False
        e = self.threat.enemy[g]
        need = max(1, -(-int(R_ENTER * (e + 1) * 10) // 10))
        if MOD_TELE_COND and need - pool.arrive.get(g, 0) < TELE_DEFICIT_MIN:
            self._stat("tele_skip")
            return False
        n = min(TELE_CFG["max_units"], cnt, pool.avail.get(j, 0), need)
        if n <= 0 or not self.cmds.tele(j, "W", n, best, self.stations):
            return False
        pool.avail[j] -= n
        pool.arrive[best] = pool.arrive.get(best, 0) + n
        log(f"T{self.turn} tele W x{n} {c.xy(j)} -> {c.xy(best)} for {c.xy(g)}")
        self._stat("tele_w", n)
        return True

    # --- v16 [A] 경제 성채
    def fortress_guard(self):
        """아군 홈 HALL/ENG 만. 적 F 가 FORT_ALERT_DIST 이내면 칸 도달 적 W E 에 대해 D >= E + 1 이 되도록
        가까운 W 부터 최소 수만 칸 위로(칸 위 W 잔류, 인접 W 진입, 먼 W 한 칸 전진). F 이동보다 먼저 실행."""
        if not ECON_FORTRESS or not self.en["F"]:
            return
        pool, c = self.pool, self.c
        ef = list(self.en["F"])
        blds = [b for b, x in self.blds.items() if x["owner"] == self.team] if FORT_ALL else self.home_blds
        for bid in sorted(blds, key=lambda b: (c.btype[b] != "ENG", -c.score(b) if FORT_ALL else 0, b)):
            b = self.blds.get(bid)
            if b is None or b["owner"] != self.team or c.btype[bid] not in FORT_TYPES:
                continue
            bi = c.bpos[bid]
            if min(c.d(e, bi) for e in ef) > FORT_ALERT_DIST:
                continue
            self._stat("fort")
            thr = self.threat.enemy[bi]
            if FORT_E2:
                thr = max(thr, self.e_near(bi, FORT_E2_R))
            need = thr + 1 - pool.arrive.get(bi, 0)
            src = sorted((c.d(j, bi), j) for j, k in pool.avail.items()
                         if k > 0 and c.d(j, bi) <= FORT_PULL_DIST)
            for _, j in src:
                if need <= 0:
                    break
                k = min(need, pool.avail.get(j, 0), pool.left("front"))
                if k > 0 and pool.send_toward(j, bi, k, None) is not None:
                    need -= k
                    self._stat("fort_w", k)

    def center_weight(self, bid):
        c = self.c
        t = c.btype[bid]
        bi = c.bpos[bid]
        mb, ob = c.base[self.team], c.base[self.opp]
        if t in ("HALL", "ENG", "HOSPITAL") or c.d(mb, bi) < c.d(ob, bi):
            return 1.0
        mem = self.mem.__dict__
        t1 = CW_T1
        if CW_STATE:
            if "cw_switch" not in mem:
                side = [b_ for b_, bb in self.blds.items() if c.btype[b_] in ("HALL", "ENG", "HOSPITAL", "DEPOT")
                        and c.d(mb, c.bpos[b_]) < c.d(ob, c.bpos[b_])]
                if side and all(self.blds[b_]["owner"] == self.team for b_ in side):
                    mem["cw_switch"] = self.turn
            t1 = min(mem.get("cw_switch", CW_T1), CW_T1)
        if self.turn <= t1:
            return CW_EARLY
        if self.turn >= t1 + 10:
            return CW_LATE
        return CW_EARLY + (CW_LATE - CW_EARLY) * (self.turn - t1) / 10.0

    def e_near(self, bi, r):
        c = self.c
        return sum(n for e, n in self.en["W"].items() if c.d(e, bi) <= r)

    def garrison(self):
        """[v20] 경제 수비대: 소유 홈 경제 건물 칸에 W 를 GARRISON_W 기까지 상주. 칸 위 W 는 잔류, 가까운 W 부터 합류.
        적 F 접근 시의 추가 병력은 기존 fortress_guard 가 담당."""
        if not MOD_GARRISON:
            return
        pool, c = self.pool, self.c
        for bid in sorted(self.home_blds, key=lambda b: (c.btype[b] != "ENG", b)):
            b = self.blds.get(bid)
            if b is None or b["owner"] != self.team or c.btype[bid] not in GARRISON_TYPES:
                continue
            bi = c.bpos[bid]
            need = (max(GARRISON_W, self.e_near(bi, GAR_E2) + 1) if GAR_E2 else GARRISON_W) - pool.arrive.get(bi, 0)
            if need <= 0:
                continue
            src = sorted((c.d(j, bi), j) for j, k in pool.avail.items() if k > 0 and c.d(j, bi) <= GARRISON_PULL)
            for _, j in src:
                if need <= 0:
                    break
                k = min(need, pool.avail.get(j, 0), pool.left("front"))
                if k > 0 and pool.send_toward(j, bi, k, None) is not None:
                    need -= k
                    self._stat("garrison_w", k)

    def fortress_hold(self, a):
        """[A] 홈 HALL/ENG 위 F 농성: 적 F 2칸 이내 & 칸 적 W 위협 0 일 때만(아군 F 전사 = 즉시 중립화)."""
        if not FORT_FLAG_HOLD or not self.en["F"]:
            return False
        c = self.c
        bid = c.bid_at.get(a.idx)
        if bid is None or bid not in self.home_blds or c.btype[bid] not in ("HALL", "ENG"):
            return False
        if self.blds.get(bid, {}).get("owner") != self.team or self.threat.enemy[a.idx] > 0:
            return False
        if min(c.d(e, a.idx) for e in self.en["F"]) > 2:
            return False
        a.next_idx = a.idx
        a.last_dir = None
        self._stat("hold")
        return True

    # --- v16 [C] 상대 경제 F 길목 인터셉트
    def route_intercept(self):
        """적 F 가 2턴 연속 같은 경제 건물(ENG/HALL/DEPOT, 적 소유 제외)에 가까워지면 그 건물을 목표로 확신.
        확신이 끊겨도 RI_HOLD 턴은 임무 유지(핑퐁 방지). 적 F -> 건물 최단 경로 층 중
        아군 W 가 적 F 보다 먼저(또는 동시에) 닿고 W_ally >= W_enemy + 1 을 채울 수 있는 칸에 매복한다.
        층 폭이 좁은(병목) 칸, 같으면 이른 칸 우선. 조건 미충족이면 아무것도 하지 않는다(v12.1 기본 행동)."""
        if not ROUTE_INTERCEPT:
            return
        mem, c, pool = self.mem, self.c, self.pool
        hist = mem.__dict__.setdefault("ri_hist", [])
        missions = mem.__dict__.setdefault("ri_missions", {})
        cur = sorted(self.en["F"])
        econ = [bid for bid, b in self.blds.items()
                if (MOD_AMBUSH or c.btype[bid] in ("ENG", "HALL", "DEPOT")) and b["owner"] != self.opp]
        found = {}
        if len(hist) >= 2 and econ and cur:
            p1, p2 = hist[-1], hist[-2]
            for e in cur:
                a = min(p1, key=lambda q: (c.d(q, e), q), default=None)
                if a is None or c.d(a, e) > 1 or a == e:
                    continue
                b_ = min(p2, key=lambda q: (c.d(q, a), q), default=None)
                if b_ is None or c.d(b_, a) > 1 or b_ == a:
                    continue
                lim = RI_CONF_DIST if RI_STRICT else RI_MAX_ETA
                cands = [bid for bid in econ
                         if c.d(e, c.bpos[bid]) < c.d(a, c.bpos[bid]) < c.d(b_, c.bpos[bid])
                         and c.d(e, c.bpos[bid]) <= lim]
                if cands:
                    bid = min(cands, key=lambda x: (c.d(e, c.bpos[x]), x))
                    found[bid] = e
        for bid in list(missions):
            if bid in found:
                missions[bid] = {"e": found[bid], "lost": 0}
            else:
                missions[bid]["lost"] += 1
                if missions[bid]["lost"] > RI_HOLD or bid not in econ:
                    del missions[bid]
        for bid, e in found.items():
            if bid not in missions:
                missions[bid] = {"e": e, "lost": 0}
                self._stat("ri_new")
        hist.append(cur)
        del hist[:-2]
        if not cur:
            return
        served = set()
        budget = max(0, self.mb.free) if RI_STRICT else INF
        for bid, m in sorted(missions.items(), key=lambda kv: (kv[1]["lost"], kv[0])):
            bi = c.bpos[bid]
            e = m["e"] if m["e"] in self.en["F"] else min(cur, key=lambda q: (c.d(q, bi), q))
            if RI_STRICT and e in served:
                continue                          # 적 F 1기당 임무 1개
            D = c.d(e, bi)
            if D >= INF or D > RI_MAX_ETA + 1:
                continue
            esc = self.en["W"].get(e, 0) + sum(self.en["W"].get(j, 0) for _, j in c.nbrs[e])
            if RI_STRICT and esc + 1 > min(MAX_INTERCEPT_W, budget):
                continue                          # W 2기(또는 여유분)로 우세를 못 만들면 v12.1 전선 유지
            layers = {}
            de, db = c.dist[e], c.dist[bi]
            for x in range(c.n):
                if c.passable[x] and 1 <= de[x] <= D and de[x] + db[x] == D:
                    layers.setdefault(de[x], []).append(x)
            best = None
            for k, cells in sorted(layers.items()):
                for x in cells:
                    need = max(esc, self.threat.enemy[x]) + 1 - pool.arrive.get(x, 0)
                    if need <= 0:
                        best = best or ((len(cells), k, x), x, [], 0)
                        continue
                    if RI_STRICT and need > min(MAX_INTERCEPT_W, budget):
                        continue
                    src = sorted((c.d(j, x), j) for j, n in pool.avail.items() if n > 0 and c.d(j, x) <= k)
                    if sum(pool.avail[j] for _, j in src) < need:
                        continue
                    key = (len(cells), k, x)
                    if best is None or key < best[0]:
                        best = (key, x, src, need)
            if best is None or not best[2]:
                continue
            _, x, src, need = best
            self._stat("ri_fire")
            served.add(e)
            for _, j in src:
                if need <= 0:
                    break
                n = min(need, pool.avail.get(j, 0), pool.left("front"))
                if n > 0 and pool.send_toward(j, x, n, None) is not None:
                    need -= n
                    budget -= n
                    self._stat("ri_w", n)

    # --- v16 [D-True] 전진 스크럼
    def frontier_bands(self):
        """공격 F(홈 전담 F 제외)의 목표 G 마다, G 에서 1~BAND_DEPTH 칸이면서 G 보다 적 본진에 가까운 칸 중
        적 W 가 가장 빨리 닿는 순으로 BAND_MAX(압축 시 지형 폭 1~2)칸을 장벽으로 지정.
        칸 -> (quota = 칸 도달 적 W + 1, F 의 G 도착 ETA). 여러 F 가 공유하면 이른 ETA 를 쓴다."""
        if getattr(self, "_bands", None) is not None:
            return self._bands
        c = self.c
        eb = c.base[self.opp]
        ew = self.enemy_w_eta_units
        cells = {}
        for a in self.agents:
            if a.target is None or a is self.sweeper:
                continue
            G = c.bpos[a.target]
            feta = c.d(a.idx, G)
            if feta >= INF:
                continue
            dG = c.d(G, eb)
            cand = [x for x in range(c.n)
                    if c.passable[x] and 1 <= c.d(x, G) <= BAND_DEPTH and c.d(x, eb) < dG]
            if not cand:
                cand = [j for _, j in c.nbrs[G]]
            limit = BAND_MAX
            if BAND_COMPRESS:
                width = sum(1 for _, j in c.nbrs[G] if c.d(j, eb) < dG)
                limit = 1 if width <= 1 else 2
            cand.sort(key=lambda x: (ew[x], c.d(x, G), x))
            for x in cand[:limit]:
                q = self.threat.enemy[x] + 1
                prev = cells.get(x)
                if prev is None or feta < prev[1]:
                    cells[x] = (q, feta)
        self._bands = cells
        return cells

    def hosp_site_v17(self):
        """v17 [A1] W 생산 위치: 안전한 소유 병원 중 전선(공격 F 목표)까지 본진보다 가까운 곳."""
        c = self.c
        fronts = [c.bpos[a.target] for a in self.agents
                  if a.target is not None and a is not self.sweeper and a.target in c.bpos]
        if not fronts:
            fronts = [c.bpos[bid] for bid in self.blds if self.capturable(bid)]
        if not fronts:
            return None
        near = lambda s: min(c.d(s, g) for g in fronts)  # noqa: E731
        best, best_d = None, near(c.base[self.team])
        ef = list(self.en["F"])
        for h in self.hospitals:
            if ef and min(c.d(e, h) for e in ef) <= HOSP_SAFE_ETA:
                continue
            if self.enemy_w_eta_units[h] <= HOSP_SAFE_ETA:
                continue
            dh = near(h)
            if dh < best_d:
                best, best_d = h, dh
        self._stat("hosp_w" if best is not None else "hosp_home")
        return best

    def frontier_site(self):
        """생산 위치. [D-True] 본진. [D2] 소유 병원이 안전(적 F ETA > 3, 적 W ETA > 2)하고
        장벽까지 병원이 본진보다 가까우면 병원(전선 보충 시간 단축). 위협 시 본진으로 회귀."""
        if not HOSP_FORWARD or not self.hospitals:
            return None
        c = self.c
        bands = self.frontier_bands()
        if not bands:
            return None
        base = c.base[self.team]
        near = lambda s: min(c.d(s, x) for x in bands)
        best, best_d = None, near(base)
        ef = list(self.en["F"])
        for h in self.hospitals:
            if ef and min(c.d(e, h) for e in ef) <= 3:
                continue
            if self.enemy_w_eta_units[h] <= 2:
                continue
            dh = near(h)
            if dh < best_d:
                best, best_d = h, dh
        return best

    def frontier_screen(self):
        """장벽 칸마다 deficit = quota - 확정 W.
        1차(JIT): W_eta(칸) <= F_eta(G) 인 W 만 투입(F 보다 늦는 W 는 부르지 않음), 열세여도 진입(1:1 상쇄).
        2차(컨베이어): 남은 부족분은 후방 W 를 가장 가까운 부족 칸으로 계속 전진시켜 충원(열세 칸 진입은 금지)."""
        if not FRONTIER_MODE:
            return
        c, pool = self.c, self.pool
        bands = self.frontier_bands()
        if not bands:
            return
        deficit = {x: max(0, q - pool.arrive.get(x, 0)) for x, (q, _) in bands.items()}
        for x in sorted(bands, key=lambda x: (bands[x][1], x)):
            feta = max(1, bands[x][1])
            if deficit[x] <= 0:
                continue
            src = sorted((c.d(j, x), j) for j, k in pool.avail.items() if k > 0 and c.d(j, x) <= feta)
            for _, j in src:
                if deficit[x] <= 0:
                    break
                k = min(deficit[x], pool.avail.get(j, 0), pool.left("front"))
                if k > 0 and pool.send_toward(j, x, k, None) is not None:
                    deficit[x] -= k
                    self._stat("front_jit", k)
        if not CONVEYOR:
            return
        for j in sorted(pool.avail, key=lambda j: (-pool.avail[j], j)):
            open_cells = [x for x in bands if deficit[x] > 0]
            if not open_cells:
                break
            k = pool.avail.get(j, 0)
            if k <= 0:
                continue
            x = min(open_cells, key=lambda x: (c.d(j, x), x))
            if c.d(j, x) >= INF:
                continue
            n = min(k, deficit[x], pool.left("front"))
            if n > 0 and pool.send_toward(j, x, n, self.threat) is not None:
                deficit[x] -= n
                self._stat("front_conv", n)

    def phalanx_reinforce(self):
        """[D3] 잉여 W 는 빈 공간 대신, 스택이 STACK_TARGET 에 못 미치는 공격 F(홈 전담 제외)의 다음 칸으로 최단 전진."""
        if not PHALANX_MODE:
            return
        c, pool = self.c, self.pool
        need = {}
        for a in self.agents:
            if a.target is None or a is self.sweeper:
                continue
            t = a.next_idx if a.next_idx is not None else a.idx
            need[t] = STACK_TARGET - pool.arrive.get(t, 0)
        for j in sorted(pool.avail, key=lambda j: (-pool.avail[j], j)):
            open_ = [t for t in need if need[t] > 0]
            if not open_:
                break
            k = pool.avail.get(j, 0)
            if k <= 0:
                continue
            t = min(open_, key=lambda t: (c.d(j, t), t))
            if c.d(j, t) >= INF:
                continue
            n = min(k, need[t], pool.left("front"))
            if n > 0 and pool.send_toward(j, t, n, self.threat) is not None:
                need[t] -= n
                self._stat("reinf_w", n)

    # --- v16 [D] 분산 박스 호위
    def box_escort(self):
        """F 호위 슬롯(ESCORT_SLOTS 기, F 다음 칸) 외에, 다음 칸의 이웃 중 적 W 가 가장 빨리 닿는 칸에
        BOX_FLANK 기를 세워 측면을 막는다(반경 ESCORT_RADIUS 안의 W 만, 먼 W 역주행 금지)."""
        if not BOX_ESCORT:
            return
        pool, c = self.pool, self.c
        ew = self.enemy_w_eta_units
        for a in sorted(self.agents, key=lambda a: (-a.util, a.uid)):
            if a.target is None:
                continue
            nxt = a.next_idx if a.next_idx is not None else a.idx
            flank = min(c.nbrs[nxt], key=lambda e: (ew[e[1]], e[1]), default=None)
            if flank is None or ew[flank[1]] > ESCORT_TRIGGER_ETA:
                continue
            fc = flank[1]
            need = BOX_FLANK - pool.arrive.get(fc, 0)
            src = sorted((c.d(j, fc), j) for j, k in pool.avail.items()
                         if k > 0 and c.d(j, a.idx) <= ESCORT_RADIUS)
            for _, j in src:
                if need <= 0:
                    break
                k = min(need, pool.avail.get(j, 0))
                if k > 0 and pool.send_toward(j, fc, k, self.threat) is not None:
                    need -= k
                    self._stat("box_w", k)

    def hunt_ext(self):
        if not HUNT_EXT:
            return
        pool, c = self.pool, self.c

        def val(e):
            b = c.bid_at.get(e)
            return 3 if (b is not None and b in self.blds and self.blds[b]["owner"] == self.team) else 1
        for f in sorted(self.en["F"], key=lambda e: (-val(e), e)):
            esc = sum(k for s_, k in self.en["W"].items() if c.d(s_, f) <= HUNT_ESC_R)
            if HUNT_SPAWN:
                esc = max(esc, self.threat.enemy[f])
            need = esc + HUNT_MARGIN - pool.arrive.get(f, 0)
            if need <= 0:
                continue
            src = sorted((c.d(j, f), j) for j, k in pool.avail.items() if k > 0 and 1 <= c.d(j, f) <= HUNT_RANGE)
            if sum(pool.avail[j] for _, j in src) < need:
                continue
            for _, j in src:
                if need <= 0:
                    break
                k = min(need, pool.avail.get(j, 0))
                if k > 0 and pool.send_toward(j, f, k, None) is not None:
                    need -= k
                    self._stat("hunt_ext", k)

    def hunt(self):
        pool, c = self.pool, self.c
        targets = []
        for e in self.en["F"]:
            bid = c.bid_at.get(e)
            val = 1
            if bid is not None and bid in self.blds:
                val = 3 if self.blds[bid]["owner"] == self.team else 2
            targets.append((-val, e))
        for _, e in sorted(targets):
            need = self.threat.enemy[e] + 1 - pool.arrive.get(e, 0)
            if need <= 0:
                continue
            if pool.reach(e) - pool.arrive.get(e, 0) >= need:
                pool.commit(e, need)

    def defend(self):
        """v6: 위협받는 핵심 건물에 (도달 가능한 적 W + 1)기까지 모은다. 말기에는 범위를 넓힌다."""
        pool, c = self.pool, self.c
        if not self.en["F"]:
            return
        endgame = self.turns_left <= ENDGAME_TURNS
        alert = (max(DEFEND_ALERT_DIST, min(self.turns_left + 1, ENDGAME_DEF_RANGE))
                 if endgame else DEFEND_ALERT_DIST)
        owned = [bid for bid, b in self.blds.items() if b["owner"] == self.team]
        econ_first = (lambda x: c.btype[x] not in ECON_TYPES) if ECON_FIRST else (lambda x: False)
        for bid in sorted(owned, key=lambda x: (econ_first(x), -c.score(x), x)):
            t = self.blds[bid]["type"]
            econ = t in ECON_TYPES
            if t == "HALL" and not HALL_DEFEND:
                continue
            if not (t in KEY_DEFEND or (ENG_DEFEND and t == "ENG") or c.score(bid) >= 3
                    or (endgame and c.score(bid) >= 2)):
                continue
            if self.enemy_eta.get(bid, INF) > (max(alert, ECON_ALERT_DIST) if econ else alert):
                continue
            bi = c.bpos[bid]
            pull = max(DEFEND_PULL_DIST, ECON_PULL_DIST) if econ else DEFEND_PULL_DIST
            thr = self.threat.enemy[bi]
            if DEF_E2:
                thr = max(thr, self.e_near(bi, DEF_E2))
            need = max(1, thr + 1) - pool.arrive.get(bi, 0)
            if need <= 0:
                continue
            src = sorted((c.d(j, bi), j) for j, k in pool.avail.items() if k > 0)
            for dist, j in src:
                if need <= 0 or dist > pull:
                    break
                k = min(need, pool.avail.get(j, 0), pool.left("front"))
                if k > 0 and pool.send_toward(j, bi, k, self.threat) is not None:
                    need -= k

    def push_target(self):
        """v12 전선 목표: 적 소유 건물 중 (점수 / (아군 W 무게중심 거리 + 1)) 최대, 없으면 최대 적 W 스택, 없으면 적 본진."""
        c = self.c
        ws = [(j, k) for j, k in self.pool.avail.items() if k > 0]
        if not ws:
            return None
        tot = sum(k for _, k in ws)
        center = min((j for j, _ in ws), key=lambda i: sum(c.d(i, j) * k for j, k in ws) / tot)
        opp_b = [bid for bid, b in self.blds.items() if b["owner"] == self.opp]
        if opp_b:
            bid = max(opp_b, key=lambda b: (c.score(b) / (c.d(center, c.bpos[b]) + 1), -b))
            return c.bpos[bid]
        if self.en["W"]:
            return max(self.en["W"], key=lambda e: (self.en["W"][e], -e))
        return c.base[self.opp]

    def endgame_attack(self):
        """v7 말기 공격: 160턴까지 닿는 상대 고득점 건물 상위 N곳에 남은 전투병을 집중."""
        pool, c = self.pool, self.c
        tl = self.turns_left
        cands = []
        for bid, b in self.blds.items():
            if b["owner"] != self.opp:
                continue
            bi = c.bpos[bid]
            dmin = min((c.d(j, bi) for j in pool.avail if pool.avail[j] > 0), default=INF)
            if dmin <= tl + 1:
                cands.append((-c.score(bid), dmin, bi))
        goals = [bi for _, _, bi in sorted(cands)[:ENDGAME_TARGETS]]
        if not goals:
            return False
        load = {g: 0 for g in goals}
        for j in sorted(pool.avail):
            k = pool.avail.get(j, 0)
            plan = {}
            for _ in range(k):
                g = min(load, key=lambda g: (c.d(j, g) + load[g], g))
                load[g] += 1
                plan[g] = plan.get(g, 0) + 1
            for g, cnt in plan.items():
                pool.send_toward(j, g, cnt, None)
        return True

    def advance(self):
        pool, c = self.pool, self.c
        if self.turns_left <= ENDGAME_TURNS and self.endgame_attack():
            return
        goals = []
        for a in self.agents:
            g = a.target if a.target is not None else a.shadow
            if g is not None:
                goals.append(c.bpos[g])
        if not goals:
            goals = list(self.en["F"])
        if not goals:
            goals = [c.bpos[bid] for bid in self.blds if self.capturable(bid)]
        if DEPOT_RUSH:
            dt = self.mem.__dict__.get("depot_turn")
            if dt is not None and self.turn - dt <= DEPOT_CENTER_TURNS:
                goals = goals + [c.bpos[b] for b in self.blds
                                 if self.side_center(b) and self.blds[b]["owner"] != self.team]
        prev_goals = self.mem.w_goals
        next_goals = {}
        self.mem.w_goals = next_goals
        ban = self.mem.w_ban
        kept = [g for g in goals if ban.get(g, -1) < self.turn]
        if kept:
            goals = kept
        if not goals:
            return
        push = self.push_target() if SURPLUS_PUSH else None
        cap = SURPLUS_ESCORT_PER_F if push is not None else INF
        load = {g: 0 for g in goals}
        plan = {}   # j -> {g: 기수}
        # 1차: 지난 턴 목표가 아직 유효한 W는 그 목표를 그대로 유지(왕복 방지)
        for j in sorted(pool.avail):
            left = pool.avail.get(j, 0)
            for g, n in sorted(prev_goals.get(j, {}).items()):
                if left <= 0:
                    break
                if g in load and c.d(j, g) < INF:
                    keep = min(n, left)
                    load[g] += keep
                    left -= keep
                    slot = plan.setdefault(j, {})
                    slot[g] = slot.get(g, 0) + keep
        # 2차: 새 W(또는 목표가 사라진 W)만 거리 + 부하로 분배
        for j in sorted(pool.avail):
            k = pool.avail.get(j, 0) - sum(plan.get(j, {}).values())
            if k <= 0:
                continue
            groups = plan.setdefault(j, {})
            for _ in range(k):
                open_g = [g for g in load if load[g] < cap]
                if not open_g:
                    if push is not None and c.d(j, push) < INF:
                        groups[push] = groups.get(push, 0) + 1   # v12: 여유 병력은 단일 전선 목표로
                    continue
                g = min(open_g, key=lambda g: (c.d(j, g) + LOAD_WEIGHT * load[g], g))
                if c.d(j, g) >= INF:
                    break
                load[g] += 1
                groups[g] = groups.get(g, 0) + 1
        staged = {}
        mem = self.mem
        for j, groups in plan.items():
            for g, cnt in groups.items():
                if TELE_W_ENABLED and self.tele_w(j, g, cnt):
                    continue
                if STAGE_RETREAT_ENABLED and self.stage_retreat(j):
                    continue
                dest = pool.send_toward(j, g, cnt, self.threat,
                                        staging=staged if STAGING_ENABLED else None,
                                        came=None if (self.home_emergency or REV_PEN_W <= 0) else mem.w_arr.get(j))
                if dest is not None:
                    slot = next_goals.setdefault(dest, {})
                    slot[g] = slot.get(g, 0) + cnt
        # [C] 집결 타임아웃: STAGING_TIMEOUT 턴 연속 대기한 목표는 W_GOAL_BAN 턴 금지(전역 재할당)
        nxt = {}
        for g in staged:
            nxt[g] = mem.staging.get(g, 0) + 1
            if nxt[g] >= STAGING_TIMEOUT:
                mem.w_ban[g] = self.turn + W_GOAL_BAN
                nxt.pop(g)
                log(f"T{self.turn} staging timeout -> retarget {self.c.xy(g)}")
        mem.staging = nxt

    # --- 정찰병
    def move_scouts(self):
        c, cmds = self.c, self.cmds
        home = c.base[self.team]
        for j in sorted(self.my["S"]):
            k = cmds.stock.get((j, "S"), 0)
            if k <= 0:
                continue
            goal = home
            if self.unrevealed and self.turns_left > 5:
                goal = min((c.bpos[bid] for bid in self.unrevealed),
                           key=lambda g: (c.d(j, g) - (2 if c.btype[c.bid_at[g]] == "WATCH" else 0), g))
            enemy = self.threat.enemy
            best_key, best_act = (enemy[j] > 0, c.d(j, goal), 2), None
            if SCOUT_EVAC and self.en["F"]:
                here = c.bid_at.get(j)
                if (here is not None and self.blds.get(here, {}).get("owner") == self.team
                        and min(c.d(e, j) for e in self.en["F"]) <= 2):
                    best_key = (True, INF, 9)      # [A] 제자리(농성) 금지: 어떤 이동이든 선택
                    self._stat("s_evac")
            for d1, m in c.nbrs[j]:
                key = (enemy[m] > 0, c.d(m, goal), 1)
                if key < best_key:
                    best_key, best_act = key, (d1,)
                for d2, e in c.nbrs[m]:
                    key = (enemy[e] > 0, c.d(e, goal), 0)
                    if key < best_key:
                        best_key, best_act = key, (d1, d2)
            if best_act is None:
                continue
            if len(best_act) == 2:
                cmds.move2(j, k, *best_act)
            else:
                cmds.move(j, "S", k, best_act[0])

    # --- 실행
    def production(self, rm):
        c, cmds = self.c, self.cmds
        base = c.base[self.team]
        new_agents = []
        for kind, count, site in rm.plan(self.agents):
            if not cmds.spawn(kind, count, site, base):
                continue
            at = base if site is None else site
            self.my[kind][at] = self.my[kind].get(at, 0) + count
            if kind == "W":
                self._stat("w_spawn", count)
                if site is not None:
                    self._stat("w_spawn_hosp", count)
            if kind == "S":
                self.mem.scouts_built += count
            if kind == "F":
                for _ in range(count):
                    a = FAgent(self.mem.new_uid(), at)
                    new_agents.append(a)
        self.agents.extend(new_agents)
        # 이번 생산으로 F가 2기 이상이 되면(예: 1턴) 여기서 홈 전담 F를 지정한다
        if new_agents and self.sweeper is None:
            self.ensure_sweeper()
        for a in new_agents:
            if a is not self.sweeper:
                self.assign(a)

    def set_priority(self):
        c = self.c
        picks = []
        for a in self.agents:
            if a.target is None or a.next_idx != c.bpos[a.target]:
                continue
            if self.capturable(a.target):
                picks.append((-a.util, a.target))
        for a in self.snipes:
            if a.snipe is not None and a.next_idx == a.snipe:
                picks.append((-INF, a.target))
        seen, idxs = set(), []
        for _, bid in sorted(picks):
            if bid not in seen:
                seen.add(bid)
                idxs.append(c.bpos[bid])
        self.cmds.set_priority(idxs)

    def finish(self):
        # 계측: W 유휴 비율 = 1 - (이번 턴 이동·순간이동한 W / 보유 W). 행동에는 영향 없음.
        w_total = sum(getattr(self, "my", {}).get("W", {}).values()) if hasattr(self, "my") else 0
        if w_total:
            moved = sum(cnt for (_, kind, _), cnt in self.cmds.moves.items() if kind == "W")
            moved += sum(cnt for _, kind, cnt, _ in self.cmds.teles if kind == "W")
            self._stat("w_turns", w_total)
            self._stat("w_moved", moved)
        if getattr(self, "_stat_dirty", False):
            log("RSTAT " + " ".join(f"{k}={v}" for k, v in self.mem.v16stat.items()))
        arr = {}
        for (idx, kind, d), cnt in self.cmds.moves.items():
            if kind != "W":
                continue
            j = next((t for dd, t in self.c.nbrs[idx] if dd == d), None)
            if j is not None:
                slot = arr.setdefault(j, {})
                slot[idx] = slot.get(idx, 0) + cnt
        self.mem.w_arr = arr
        plans = {}
        for a in self.agents:
            nxt = a.next_idx if a.next_idx is not None else a.idx
            plans.setdefault(nxt, []).append(a)
        self.mem.next_plans = plans

    def play(self):
        try:
            self.scan()
            enemy_w = sum(self.en["W"].values())
            home_req = self.home_requirement()
            # 생산 전 예산으로 기습 가능 여부만 판단(목표 배정에 반영)
            self.mb = MilitaryBudget(sum(self.my["W"].values()), enemy_w, home_req)
            if HOSPITAL_RAID_ENABLED:
                self.raid = self.check_hospital_raid_viable()
            agents = self.build_agents()
            self.opening_step()
            self.assign_all(agents)
            self.plan_snipes()
            rm = ResourceManager(self)
            rm.open_budget(agents)
            self.production(rm)
            # 생산분을 포함한 최종 병력 → 단일 풀(홈 비상 쿼터만 별도)
            self.mb = MilitaryBudget(sum(self.my["W"].values()), enemy_w, home_req)
            self.pool = WarriorPool(self.c, self.my["W"], self.cmds, self.mb.quotas())
            self.threat.set_friendly(self.my["W"])
            self.exec_snipes()          # 1) UNIVERSAL_SNIPE
            self.home_defense()         # 2) HOME_EMERGENCY
            self.pool.release("home")
            self.fortress_guard()       # 2b) v16 [A] 홈 HALL/ENG 칸 사수(F 이동보다 먼저)
            self.garrison()             # 2b'') v20 경제 수비대 상주
            self.v17c_intercept()       # 2b') v17c [TEST_1] 1턴 도착지 요격
            self.frontier_screen()      # 2c) v16 [D-True] 장벽 JIT 투입 + 컨베이어 충원(F 이동보다 먼저)
            self.move_flags()           # 3) CAPTURE (+ RETREAT, 호위 커밋)
            self.anchor_w()             # 3a) v17b3 W 1기 알박기
            if ESCORT_SLOTS > 0:
                self.escort_slots()     # 3b) v12 호위 슬롯
            self.box_escort()           # 3c) v16 [D] 측면 박스
            self.phalanx_reinforce()    # 3c') v16 [D3] 잉여 W -> 부족한 F 스택 합류
            self.route_intercept()      # 3d) v16 [C] 경제 F 길목 매복
            self.v18_radar()            # 3e) v18 [C] 원거리 레이더 선집결 / 트레이딩
            for phase in (self.deathball_defense, self.hunt, self.hunt_ext, self.defend, self.intercept, self.advance,
                          self.move_scouts, self.set_priority):
                if self.clock.over():
                    log(f"T{self.turn} degraded at {phase.__name__} {self.clock.elapsed() * 1000:.0f}ms")
                    break
                phase()
            if DEBUG and self.turn <= DEBUG:
                for a in self.agents:
                    log(f"T{self.turn} F#{a.uid} at {self.c.xy(a.idx)} tgt={a.target} util={a.util:.2f} age={a.age} next={self.c.xy(a.next_idx) if a.next_idx is not None else None}")
            if self.turn == 1 or self.turn % LOG_EVERY == 0:
                log(f"T{self.turn} res={self.view.my_resource} rsv={rm.reserved} "
                    f"F={len(self.agents)} W={self.mb.total} free={self.mb.free} "
                    f"S={sum(self.my['S'].values())} known={len(self.c.known)} "
                    f"{self.clock.elapsed() * 1000:.1f}ms")
        finally:
            self.finish()


# ------------------------------------------------------------------ F. 진입점

def build_opening(init):
    """[1-B] 턴0 빔 서치. import 기준 T0_SOFT 에서 종료."""
    c = MEM.cache
    team = init.team
    opp = "K" if team == "Y" else "Y"
    axis = c.axis
    lo, hi = CFG["regions"]["center"]
    my_coord = c.base[team] % c.w if axis == 0 else c.base[team] // c.w

    def home_of(bid):
        i = c.bpos[bid]
        coord = i % c.w if axis == 0 else i // c.w
        if lo <= coord <= hi:
            return None
        return 0 if (coord < lo) == (my_coord < lo) else 1

    try:
        bd = opening.Board(c, team, c.score, home_of)
        pol = opening.build_policy(bd, T_START + T0_SOFT)
        MEM.opening = pol
        MEM.opening_active = bool(pol.hard)
        st = pol.stats
        log(f"opening: passes={st['passes']} rollouts={st['rollouts']} depth={st['depth']} "
            f"{st['ms']:.0f}ms t0={1000 * (time.perf_counter() - T_START):.0f}ms age={1000 * _AGE:.0f}ms hard={pol.hard[:5]} "
            f"robust={ {a: round(v, 1) for a, v in pol.robust.items()} }")
    except Exception:
        log(traceback.format_exc())
        MEM.opening, MEM.opening_active = None, False


def decide(view, init):
    clock = Clock(TURN_BUDGET)
    cmds = None
    try:
        if MEM.cache is None or MEM.init_id != id(init):
            MEM.__init__()
            MEM.cache = StateCache(init)
            MEM.init_id = id(init)
            clock.budget = FIRST_TURN_BUDGET
            MEM.meta = StaticMeta(MEM.cache, init.team, clock)
            log(f"cache+meta built {clock.elapsed() * 1000:.1f}ms complete={MEM.meta.complete} "
                f"choke={[MEM.cache.xy(i) for i in MEM.meta.chokepoints(4)]}")
            if OPENING_ENABLED:
                build_opening(init)
            gc.collect()      # 롤아웃 임시 상태 정리 후 동결: 이후 턴의 GC 정지 시간 스파이크 완화
            try:
                gc.freeze()
            except AttributeError:
                pass
            # 첫 턴 남은 처리(Brain)는 import 기준 T0_HARD 까지
            clock.budget = max(0.05, T_START + T0_HARD - clock.t0)
        cmds = CommandBook(view, MEM.cache)
        Brain(view, init, MEM, clock, cmds).play()
        return cmds.emit()
    except Exception:
        log(traceback.format_exc())
        MEM.soft_reset()
        try:
            return cmds.emit() if cmds is not None else []
        except Exception:
            return []


def main_loop():
    """END 누락·flush 누락 방지: 파싱/결정 실패에도 매 턴 END 를 출력한다."""
    si, so = sys.stdin, sys.stdout
    init_lines = read_block(si)
    if init_lines is None:
        return
    canon = None
    try:
        init = parse_init(init_lines)
        if CANON_ENABLED and init.team == "K":
            try:
                canon = Canon(init)
            except Exception:
                log(traceback.format_exc())
                canon = None
    except Exception:
        log(traceback.format_exc())
        init = None
    while True:
        block = read_block(si)
        if block is None:
            break
        cmds = []
        try:
            if init is not None:
                view = parse_turn(block, init)
                if canon is not None:
                    cmds = [canon.out(cm) for cm in decide(canon.view(view), canon.init)]
                else:
                    cmds = decide(view, init)
        except Exception:
            log(traceback.format_exc())
            cmds = []
        try:
            for cmd in cmds:
                so.write(cmd + "\n")
        except Exception:
            pass
        so.write("END\n")
        so.flush()


if __name__ == "__main__":
    main_loop()
