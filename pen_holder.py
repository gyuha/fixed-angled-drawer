# -*- coding: utf-8 -*-
"""적층형 경사 필통 — 파라메트릭 FreeCAD 스크립트

실행:  /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd pen_holder.py
산출:  output/pen_holder.FCStd,
       output/{tier1,module2,module3,topmodule,lid,thumbscrew}.stl

부품 6종 (적층 모듈 높이는 모두 170mm — 어떤 조합으로 쌓아도 호환)
  - module2    : 적층 모듈 2칸 (칸 피치 85mm, 긴 물건용)
  - module3    : 적층 모듈 3칸 (칸 피치 56.7mm, 촘촘한 분류용)
  - tier1      : 1단 3칸 (본체 + 뒷면 일체형 책상 클램프 + 암나사)
  - topmodule  : 마감 모듈 (바닥 없음·천장 일체, 높이 56.7mm)
  - lid        : 평판 뚜껑 (모듈 바닥과 동일한 스냅 스커트 — 2칸/3칸 모듈용)
  - thumbscrew : 클램프 조임 나사 (업로드 참고 나사와 호환 규격)

좌표계: X=폭(0..80), Y=깊이(0=앞..100=뒤), Z=높이(0=바닥)
"""
import math
import os

import FreeCAD as App
import MeshPart
import Part
from FreeCAD import Vector

# ---------------------------------------------------------------------------
# 파라미터 — 벽 두께·경사각 등 일부 값은 초기 참고 모델에서 실측해 정한
# 것이다. 참고 모델 자체는 저장소에서 제외했고, 실측값은 아래 주석에 남는다.
# ---------------------------------------------------------------------------
W = 70.0            # 모듈 폭 (8cm 시제품이 넓어 7cm로 축소, 8cm판은 output-8cm/)
D = 100.0           # 모듈 깊이 (요구 사양 10cm)
H = 170.0           # 모듈 높이 (요구 사양 17cm, 전 부품 공통 — 적층 호환)
TIER1_SLOTS = 3     # 1단(바닥 모듈) 칸 수
MODULE_SLOTS = (2, 3)  # 적층 모듈 변형별 칸 수 → module2 / module3

WALL = 2.4          # 측벽·뒷벽·앞벽 두께. 3.0에서 낮춰 재료 15% 절감
                    # (스냅 물림·필렛은 유지 — 아래 'snap wall guard' 검증 참고)
BOT_T = 3.0         # 바닥판 두께 (4.0에서 낮춤)
SHELF_T = 3.0       # 선반 수직 두께 (4.0에서 낮춤)
ANGLE = 20.0        # 선반 경사각(도) — 참고 STL 법선 실측
LIP = 3.0           # 선반 앞 끝 위 낮은 턱 높이
# 앞턱 뒷면을 수직 단차로 두면, 뒷면을 베드에 대고 출력할 때 아래를 향한
# 평평한 천장이 되어 서포트가 필요하다. 기저 폭 LIP_BASE 만큼 램프로
# 눕혀 자기지지 각도(베드 대비 45° 초과)를 만든다. LIP_BASE > LIP 필수.
LIP_BASE = 8.0      # 앞턱 램프의 깊이 방향 기저 폭
BOTTOM_CUBBY = True  # 최하단 선반 아래를 전면 개방 수납 포켓으로 (앞턱 LIP 유지)
FLANGE = 3.0        # 하단 개방 시 측벽 안쪽에 남기는 바닥판 레일 폭 (스커트 부착용)
FILLET_R = 1.4      # 앞쪽 모서리 필렛 반경 (벽 3mm: 양쪽 합이 면 폭 미만이어야 함)

# --- 서랍 변형 (tier1-drawer) + 서랍 부품 ---
DRAWER_CLEAR = 0.4      # 서랍 좌우 각 공차
DRAWER_V_CLEAR = 0.5    # 서랍 상하 합 공차
DRAWER_BACK_GAP = 2.0   # 밀어 넣었을 때 뒷벽 앞 여유 (깊이 정지)
DRAWER_WALL = 2.5       # 서랍 측·뒷벽 두께
DRAWER_BOT_T = 3.0      # 서랍 바닥 두께
DRAWER_FRONT_T = 3.0    # 서랍 앞판 두께
PULL_W = 30.0           # 앞판 손가락 개구 폭
PULL_H = 16.0           # 앞판 손가락 개구 높이 (중앙 배치 — 모멘트 0)
PULL_FILLET_R = 1.0     # 개구 모서리 라운딩 — 손가락이 걸리는 자리
# 레일: 홈은 서랍 측벽, 리브는 본체 측벽 (서랍이 파이는 쪽)
RAIL_GROOVE_D = 1.4     # 서랍 측벽 홈 깊이
RAIL_GROOVE_H = 3.0     # 서랍 측벽 홈 높이
RAIL_RIB_D = 1.0        # 본체 측벽 리브 돌출
RAIL_RIB_H = 2.4        # 본체 측벽 리브 높이
RAIL_PAD_T = 1.0        # 홈 뒤 서랍 벽을 안쪽으로 덧대는 보강 두께
RAIL_START = 0.2        # 레일 시작 위치 (깊이 비율) — 앞에서 이만큼 들어간 뒤부터
                        # 앞면에 레일이 보이지 않고, 깊이의 4/5 구간이 안내된다

# --- 측벽 타공 (장식·통기) ---
PERFORATE = True    # 측벽 타공 패턴 on/off
PERF_D = 4.5        # 구멍 지름
PERF_PITCH = 8.0    # 구멍 간격 (스태거드/벌집 배열)
PERF_MARGIN = 1.5   # 선반 슬래브 띠와의 최소 여유

# --- 마감용 최상단 모듈 + 별도 뚜껑 ---
# 마감 모듈(topmodule)은 천장이 일체로 붙은 한 부품이고, 전체 높이는
# 3칸 모듈의 한 칸 높이(H/3). 별도 뚜껑(lid)은 모듈 바닥과 똑같은 스냅
# 스커트를 써서 2칸·3칸 모듈 위에 그대로 덮인다.
TOP_H = H / 3.0     # 마감 모듈 전체 높이 (천장 포함)
LID_T = 3.0         # 천장판·뚜껑판 두께
TOP_CEIL = TOP_H - LID_T     # 마감 모듈 천장 밑면 높이

LAYOUT_GAP = 30.0   # FCStd 문서 내 부품 나열 간격 (스크린샷용, STL 무관)

TAN = math.tan(math.radians(ANGLE))
IN_D = D - WALL     # 선반이 걸치는 깊이 (앞면 y=0 ~ 뒷벽 안쪽 y=97)

# --- 스냅핏 (그릴링 확정: 스냅핏 클립, ADR 260817-160757) ---
CLEAR = 0.25        # 스커트-내벽 공차
SKIRT_T = 2.5       # 스커트 두께
SKIRT_D = 12.0      # 스커트 내려가는 깊이
HOOK_W = 14.0       # 후크 탭 폭
HOOK_GAP = 3.0      # 후크 탭 양옆 유격 슬롯
BUMP_D = 1.8        # 후크 돌기 돌출량
BUMP_H = 5.0        # 후크 돌기 높이
WIN_H = 5.4         # 캐치 창 높이 (돌기 + 0.4 여유)
WIN_W = HOOK_W + 1.0
WIN_TOP = H - 6.6   # 창 상단 z (스커트 결합 시 돌기 상면과 0.4 여유)
HOOK_Y = 50.0       # 후크/창 중심의 y 위치

# --- 클램프 (그릴링 확정: 일체형 ㄷ자, 개구 40mm) ---
# FDM 출력 대응: 클램프 전체가 뒷면 평면(y=D)과 플러시 — 등을 대고
# 평평하게 안착 출력. 뒷판은 안쪽(y = D-PLATE_T .. D)으로 들어간다.
OPENING = 40.0      # 상판 물림 개구 (상판 18~25mm + 조임 여유)
PLATE_T = 12.0      # 뒷판 두께 (안쪽 방향)
JAW_T = 14.0        # 아래턱 두께 (나사 4mm 피치 × 3.5산 물림)
CLAMP_W = 40.0      # 클램프 폭 (중앙 정렬). 나사 구멍 Ø19.3 양옆에 10.3mm씩
                    # 남는다 — 더 줄이면 아래 '구멍 주변 재료' 검증이 걸린다
JAW_REACH = 45.0    # 뒷면에서 앞으로 뻗는 아래턱 길이 (나사 구멍 앞 7.4mm 여유)
JAW_FILLET_R = 5.0  # 아래턱 앞 끝 좌우 모서리 필렛 반경
HOLE_Y = 72.0       # 나사 구멍 중심 y (책상 물림면 y=D-PLATE_T 에서 16mm 안쪽)

# --- 나사 (업로드 썸스크류 실측: OD18.5 / 골 12.7 / 피치 4 / 나사부 22) ---
THR_PITCH = 4.0
THR_OD = 18.5
THR_ROOT = 12.7
# 나사부 길이: 참고 나사는 22mm였으나 그 길이로는 아래턱 위로 10mm만
# 올라와 두께 30mm 미만 상판에 닿지 않았다. 25mm 연장해 5~40mm 상판을
# 모두 물 수 있게 한다 (아래 '체결 가능 상판 두께' 검증 참고).
THR_LEN = 47.0
SHAFT_LEN = THR_LEN + 2.0    # 나사산 양끝이 묻히도록 샤프트를 조금 길게
KNOB_D = 32.6       # 손잡이 지름 (실측)
KNOB_H = 10.0       # 손잡이 높이 (실측)
THR_CLEAR = 0.4     # 암나사 반경 공차

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


# ---------------------------------------------------------------------------
# 보조 함수
# ---------------------------------------------------------------------------
def prism_yz(points, x0, dx):
    """YZ 평면 다각형((y,z) 목록)을 x0에서 +X로 dx만큼 압출한 프리즘."""
    vecs = [Vector(x0, y, z) for y, z in points]
    vecs.append(vecs[0])
    face = Part.Face(Part.Wire(Part.makePolygon(vecs)))
    return face.extrude(Vector(dx, 0, 0))


def prism_xz(points, y0, dy):
    """XZ 평면 다각형((x,z) 목록)을 y0에서 +Y로 dy만큼 압출한 프리즘."""
    vecs = [Vector(x, y0, z) for x, z in points]
    vecs.append(vecs[0])
    face = Part.Face(Part.Wire(Part.makePolygon(vecs)))
    return face.extrude(Vector(0, dy, 0))


def fillet_front(shape, radius=FILLET_R, height=H):
    """앞쪽(y < 벽두께) 모서리에 필렛. 손이 닿는 앞면을 부드럽게.

    적층 연결부는 제외: z=0 이하(하단 레일·스커트) 또는 z=H(상단 테두리)에
    닿는 모서리는 결합면이 평평해야 하므로 필렛하지 않는다. 부분 필렛이
    불가능해 측벽 앞 세로 모서리(z 0~H 관통)도 함께 제외된다.

    OCC 필렛은 모서리 조합에 따라 실패할 수 있어 반경을 낮추며 재시도하고,
    끝내 실패하면 원본을 그대로 반환한다 (형상 안전 우선).
    """
    edges = [e for e in shape.Edges
             if e.BoundBox.YMax < WALL + 0.01
             and e.BoundBox.ZMin > 0.01
             and e.BoundBox.ZMax < height - 0.01
             and e.Length > 2.0 * radius]
    if not edges:
        return shape, 0.0
    for r in (radius, 1.0, 0.6):
        try:
            out = shape.makeFillet(r, edges)
            if out.isValid():
                return out, r
        except Exception:
            pass
    return shape, 0.0


def make_thread_ridge(root_r, crest_r, half_root, half_crest, pitch, length):
    """헬리컬 나사산 리지 솔리드 (사다리꼴 단면 스윕).

    주의: 프로파일 폭만큼 z가 양끝으로 ±half_root 넘친다. OCC의 common()
    클리핑이 이 헬리컬 솔리드에 조용히 실패하므로(검증 실험으로 확인),
    호출부에서 넘친 끝단이 다른 재료 속에 묻히도록 배치한다.
    """
    helix = Part.makeHelix(pitch, length, root_r)
    profile = Part.makePolygon([
        Vector(root_r - 0.5, 0, -half_root),
        Vector(root_r - 0.5, 0, half_root),
        Vector(crest_r, 0, half_crest),
        Vector(crest_r, 0, -half_crest),
        Vector(root_r - 0.5, 0, -half_root),
    ])
    return Part.Wire(helix).makePipeShell([Part.Wire(profile)], True, True)


def make_internal_thread_negative(length):
    """암나사 네거티브(빼기용) 솔리드, z=0에서 +Z로 length. 끝단 넘침은
    빼기 대상 바깥이므로 무해."""
    bore_r = THR_ROOT / 2.0 + THR_CLEAR
    crest_r = THR_OD / 2.0 + THR_CLEAR
    core = Part.makeCylinder(bore_r, length)
    ridge = make_thread_ridge(bore_r, crest_r, 1.6, 0.8, THR_PITCH, length)
    return core.fuse(ridge)


# ---------------------------------------------------------------------------
# 모듈 본체 (칸·창까지 포함, 스커트/클램프 제외 공통부)
# ---------------------------------------------------------------------------
def perforation_cuts(n_comp, height=H, z_max=None, z_min=10.0,
                     bay_ceiling=None):
    """측벽 타공용 X관통 원기둥 컴파운드 (없으면 None).

    n_comp=0 이면 선반이 없는 것으로 보고 회피 조건에서 제외한다.

    회피 조건이 y/z에만 걸리므로 양 측벽의 배치가 동일 — 관통 원기둥
    하나가 두 벽을 함께 뚫고, 중간은 칸 내부 빈 공간이라 무해하다.
    선반 슬래브 띠(± PERF_MARGIN), 캐치 창·상단 결합부(z>150),
    하단(z<10), 앞뒤 가장자리(y 8~90 밖)는 비운다.
    """
    pitch = height / n_comp if n_comp else 0.0
    r = PERF_D / 2.0
    row_h = PERF_PITCH * 0.866  # 벌집 배열 행 간격
    cyls = []
    row = 0
    z = z_min + r
    z_top = height - 20.0 if z_max is None else z_max
    while z + r <= z_top:
        y = 8.0 + (PERF_PITCH / 2.0 if row % 2 else 0.0)
        while y + r <= 90.0:
            clear = True
            for k in range(n_comp):
                ft = k * pitch + BOT_T + (IN_D - y) * TAN  # 선반 상면 z
                if (z + r > ft - SHELF_T - PERF_MARGIN
                        and z - r < ft + PERF_MARGIN):
                    clear = False
                    break
            if clear and bay_ceiling is not None:
                # 서랍 구간(경사 천장 아래)은 서랍이 지나가는 면이라 비운다
                c0, slope = bay_ceiling
                if z - r < c0 - slope * y:
                    clear = False
            if clear:
                cyls.append(Part.makeCylinder(
                    r, W + 2.0, Vector(-1.0, y, z), Vector(1, 0, 0)))
            y += PERF_PITCH
        z += row_h
        row += 1
    return Part.makeCompound(cyls) if cyls else None


def catch_windows(height):
    """상단 캐치 창 (양 측벽 관통) — 위 모듈/뚜껑의 스냅 돌기가 걸리는 자리."""
    win_top = height - 6.6
    return [Part.makeBox(WALL + 1.0, WIN_W, WIN_H,
                         Vector(x0, HOOK_Y - WIN_W / 2.0, win_top - WIN_H))
            for x0 in (-0.5, W - WALL - 0.5)]


def snap_skirt_parts():
    """바닥 스냅 스커트 + 돌기 (z = -SKIRT_D .. 0). 모듈·뚜껑 공용."""
    sk_y0, sk_y1 = 8.0, D - WALL - CLEAR
    parts = []

    # 측면 스커트 (후크 탭 슬롯 제외하고 세 토막)
    for x_out in (WALL + CLEAR, W - WALL - CLEAR - SKIRT_T):
        y_slot0 = HOOK_Y - HOOK_W / 2.0 - HOOK_GAP
        y_slot1 = HOOK_Y + HOOK_W / 2.0 + HOOK_GAP
        for ya, yb in ((sk_y0, y_slot0),
                       (HOOK_Y - HOOK_W / 2.0, HOOK_Y + HOOK_W / 2.0),
                       (y_slot1, sk_y1)):
            parts.append(Part.makeBox(SKIRT_T, yb - ya, SKIRT_D,
                                      Vector(x_out, ya, -SKIRT_D)))

    # 뒷면 스커트는 두지 않는다 — 뒷면을 베드에 대고 출력할 때 베드에서
    # 3.25mm 떠 있는 평판(≈880mm²)이 되어 서포트를 부른다. 깊이 방향
    # 위치 결정은 측면 스커트 뒤끝(y=96.75)이 아래 모듈 뒷벽에 닿아 담당.

    # 스냅 돌기 (바깥쪽 돌출, 하단 45° 챔퍼) — 좌/우
    xl = WALL + CLEAR                              # 좌측 스커트 바깥면
    parts.append(prism_xz([
        (xl, -SKIRT_D),
        (xl - BUMP_D, -SKIRT_D + BUMP_D),          # 45° 진입 챔퍼
        (xl - BUMP_D, -SKIRT_D + BUMP_H),
        (xl, -SKIRT_D + BUMP_H),
    ], HOOK_Y - HOOK_W / 2.0, HOOK_W))
    xr = W - WALL - CLEAR                          # 우측 스커트 바깥면
    parts.append(prism_xz([
        (xr, -SKIRT_D),
        (xr + BUMP_D, -SKIRT_D + BUMP_D),
        (xr + BUMP_D, -SKIRT_D + BUMP_H),
        (xr, -SKIRT_D + BUMP_H),
    ], HOOK_Y - HOOK_W / 2.0, HOOK_W))
    return parts


def drawer_bay_geometry():
    """서랍 구간(bay)과 쐐기 서랍의 치수를 한 곳에서 계산한다.

    서랍은 경사 천장을 따라가는 쐐기형이라 앞이 높고 뒤가 낮다. 천장과
    서랍 상면의 기울기가 같으므로 인출·삽입 중 간섭이 없다(빼면 여유가
    오히려 늘어난다). 반환: dict.
    """
    pitch = H / TIER1_SLOTS
    ceil_front = (pitch + BOT_T + IN_D * TAN) - SHELF_T   # 앞쪽 천장 z
    ceil_back = (pitch + BOT_T) - SHELF_T                 # 뒷쪽 천장 z
    dd = IN_D - DRAWER_BACK_GAP
    h_front = (ceil_front - DRAWER_V_CLEAR) - BOT_T       # 서랍 앞 높이(서랍 기준)
    d = dict(
        bay_bot=BOT_T, ceil_front=ceil_front, ceil_back=ceil_back,
        bay_w=W - 2 * WALL, bay_d=IN_D,
        drawer_w=(W - 2 * WALL) - 2 * DRAWER_CLEAR,
        drawer_d=dd,
        h_front=h_front,
        h_rear=h_front - TAN * dd,                        # 서랍 뒤 높이
        rail_y0=RAIL_START * dd,                          # 레일 시작 y (앞에서 안쪽)
    )
    return d


_SHELL = {}
_DRAWER_INFO = {}


def drawer_shell():
    """개구·홈·보강 없는 서랍 껍데기 (무게중심 계산용, 캐시)."""
    if "s" not in _SHELL:
        g = drawer_bay_geometry()
        dw, dd = g["drawer_w"], g["drawer_d"]
        outer = prism_yz([(0.0, 0.0), (0.0, g["h_front"]),
                          (dd, g["h_rear"]), (dd, 0.0)], 0.0, dw)
        inner = prism_yz([
            (DRAWER_FRONT_T, DRAWER_BOT_T),
            (DRAWER_FRONT_T, g["h_front"] + 1.0),
            (dd - DRAWER_WALL, g["h_rear"] + 1.0),
            (dd - DRAWER_WALL, DRAWER_BOT_T),
        ], DRAWER_WALL, dw - 2 * DRAWER_WALL)
        _SHELL["s"] = outer.cut(inner)
    return _SHELL["s"]


def rail_z_local():
    """레일·손가락 개구를 놓을 높이 = 빈 서랍의 실제 무게중심 높이.

    당김점·무게중심·레일이 한 선에 놓여 기울임 모멘트가 0이 된다.
    솔리드에서 직접 구하므로 형상이 바뀌면 자동으로 따라온다.
    """
    sh = drawer_shell()
    solid = sh.Solids[0] if sh.Solids else sh   # 불리언 결과가 컴파운드로 감싸짐
    return solid.CenterOfMass.z


def make_body(n_comp, bottom_open=False, drawer_bay=False):
    """n_comp: 경사 칸 수 (칸 피치 = H / n_comp).

    bottom_open=True: 하단 포켓의 바닥판·앞턱을 제거해, 적층 시 아래
    모듈의 최상단 칸과 공간이 이어진다 (적층 모듈용). tier1은 False로
    바닥을 유지한다. 측벽 안쪽 FLANGE 폭 바닥판 레일은 남긴다 (측면
    스커트가 매달리는 자리)."""
    pitch = H / n_comp
    body = Part.makeBox(W, D, H)

    cuts = []
    g = drawer_bay_geometry() if drawer_bay else None
    for k in range(n_comp):
        if drawer_bay and k == 0:
            # 최하단 칸 → 쐐기 서랍 구간. 경사 선반·앞턱·하단 포켓을 한 번에
            # 제거해 바닥부터 경사 천장까지가 그대로 서랍 공간이 된다.
            cuts.append(prism_yz([
                (0.0, g["bay_bot"]),
                (0.0, g["ceil_front"]),
                (IN_D, g["ceil_back"]),
                (IN_D, g["bay_bot"]),
            ], WALL, W - 2 * WALL))
            continue
        b = k * pitch
        floor_back = b + BOT_T                    # 선반 상면 z (뒷벽 쪽, y=97)
        ff = floor_back + IN_D * TAN              # 선반 상면 z (앞면, y=0)
        lip_top = ff + LIP

        if k < n_comp - 1:
            # 천장 = 위 선반의 밑면
            b_up = (k + 1) * pitch
            ceil_front = (b_up + BOT_T + IN_D * TAN) - SHELF_T
            ceil_back = (b_up + BOT_T) - SHELF_T
        else:
            ceil_front = ceil_back = H            # 최상단 칸은 위로 개방

        # 마지막 점 → 첫 점을 잇는 변이 앞턱 램프 (자기지지)
        poly = [
            (0.0, lip_top),
            (0.0, ceil_front),
            (IN_D, ceil_back),
            (IN_D, floor_back),
            (LIP_BASE, ff - LIP_BASE * TAN),
        ]
        cuts.append(prism_yz(poly, WALL, W - 2 * WALL))

        if k == 0 and BOTTOM_CUBBY:
            # 최하단 선반 아래 전면 개방 수납 포켓
            # 바닥 = 바닥판 상면, 천장 = 경사 선반 밑면, 앞에 LIP 턱
            under_front = BOT_T + IN_D * TAN - SHELF_T   # y=0 선반 밑면 z
            y_end = IN_D - SHELF_T / TAN  # 선반 밑면이 바닥판 상면과 만나는 y
            if under_front > BOT_T + LIP + 2.0:
                # 마지막 점 → 첫 점을 잇는 변이 앞턱 램프 (자기지지)
                cubby = [
                    (0.0, BOT_T + LIP),
                    (0.0, under_front),
                    (y_end, BOT_T),
                    (LIP_BASE, BOT_T),
                ]
                cuts.append(prism_yz(cubby, WALL, W - 2 * WALL))

            if bottom_open:
                # 바닥판 개방 (측벽 쪽 FLANGE 레일 존치)
                opening = [
                    (0.0, -0.5),
                    (0.0, under_front),
                    (y_end, BOT_T),
                    (y_end, -0.5),
                ]
                cuts.append(prism_yz(opening, WALL + FLANGE,
                                     W - 2 * (WALL + FLANGE)))
                # 앞턱 램프 제거 (레일 위 잔여 스터브 포함 전폭)
                cuts.append(Part.makeBox(W - 2 * WALL, LIP_BASE + 0.6,
                                         LIP + 0.7,
                                         Vector(WALL, -0.5, BOT_T - 0.1)))

    cuts += catch_windows(H)

    # 측벽 타공 패턴 (서랍 구간은 서랍이 닿는 면이므로 제외)
    if PERFORATE:
        bay = (g["ceil_front"] + 3.0, TAN) if drawer_bay else None
        holes = perforation_cuts(n_comp, H, bay_ceiling=bay)
        if holes:
            cuts.append(holes)

    for c in cuts:
        body = body.cut(c)

    if drawer_bay:
        # 레일 리브 — 앞에서 rail_y0 만큼 들어간 지점부터 뒤까지 (앞면에 보이지 않음)
        rz = g["bay_bot"] + rail_z_local() - RAIL_RIB_H / 2.0
        ry = g["rail_y0"]
        for rx in (WALL, W - WALL - RAIL_RIB_D):
            body = body.fuse(Part.makeBox(RAIL_RIB_D, IN_D - ry, RAIL_RIB_H,
                                          Vector(rx, ry, rz)))
    return body


# ---------------------------------------------------------------------------
# 적층 모듈 = 본체 + 바닥 스커트/스냅 후크
# ---------------------------------------------------------------------------
def make_module(n_comp):
    body = make_body(n_comp, bottom_open=True)
    for p in snap_skirt_parts():
        body = body.fuse(p)
    return body


# ---------------------------------------------------------------------------
# 마감용 최상단 모듈 (천장 일체) + 별도 평판 뚜껑
# ---------------------------------------------------------------------------
def make_top_module():
    """스택 맨 위를 마감하는 모듈 — 천장 일체, 바닥 없음.

    바닥이 없어 아래 모듈의 맨 위 칸과 공간이 그대로 이어지고, 그
    공간을 자신의 천장이 덮어 마감한다. 위에 아무것도 올라가지 않으므로
    상단 캐치 창은 두지 않는다. 바닥 스냅 스커트로 아래 모듈에 결합하고,
    측벽 안쪽 FLANGE 레일만 남겨 스커트를 매단다. 전체 높이 TOP_H.
    """
    body = Part.makeBox(W, D, TOP_H)

    cuts = [
        # 레일 위 ~ 천장 밑면: 벽 사이 개방 (뒷벽은 IN_D 까지만 파서 남김)
        Part.makeBox(W - 2 * WALL, IN_D, TOP_CEIL - BOT_T,
                     Vector(WALL, 0, BOT_T)),
        # 레일 높이 구간: 가운데만 뚫어 측벽 쪽 레일을 남김
        Part.makeBox(W - 2 * (WALL + FLANGE), IN_D, BOT_T + 0.5,
                     Vector(WALL + FLANGE, 0, -0.5)),
    ]

    if PERFORATE:
        # 선반 없음 → 회피 조건 없음. 천장 3mm 아래까지만 타공
        holes = perforation_cuts(0, TOP_H, z_max=TOP_CEIL - 3.0)
        if holes:
            cuts.append(holes)

    for c in cuts:
        body = body.cut(c)
    for p in snap_skirt_parts():
        body = body.fuse(p)
    return body


def make_lid():
    """평판 뚜껑 — 모듈 바닥과 동일한 스냅 스커트를 그대로 쓴다.

    판은 z=0..LID_T, 스커트는 z<0 이므로 2칸·3칸 모듈 위에 그대로
    덮여 딸깍 걸린다. 출력 시에는 판이 베드에 닿도록 뒤집는다.
    """
    lid = Part.makeBox(W, D, LID_T)
    for p in snap_skirt_parts():
        lid = lid.fuse(p)
    return lid


# ---------------------------------------------------------------------------
# 1단 = 본체 + 뒷면 일체형 클램프(암나사)
# ---------------------------------------------------------------------------
def make_tier1(drawer=False):
    body = make_body(TIER1_SLOTS, drawer_bay=drawer)

    # 클램프는 뒷면 평면(y=D)과 플러시 — 뒷판이 안쪽으로 들어가고,
    # 본체 바닥(z=0)과의 접합 단면(CLAMP_W × PLATE_T)이 강성을 담당
    x0 = (W - CLAMP_W) / 2.0
    plate = Part.makeBox(CLAMP_W, PLATE_T, OPENING + JAW_T,
                         Vector(x0, D - PLATE_T, -(OPENING + JAW_T)))
    jaw = Part.makeBox(CLAMP_W, JAW_REACH, JAW_T,
                       Vector(x0, D - JAW_REACH, -(OPENING + JAW_T)))
    clamp = plate.fuse(jaw)

    # 아래턱 앞 끝 좌우 모서리 필렛 (손이 닿는 자리) — 나사산 절삭 전에
    # 적용한다. 헬리컬 구멍이 생긴 뒤에는 OCC 필렛이 불안정하다.
    jaw_y = D - JAW_REACH
    ends = [e for e in clamp.Edges
            if e.BoundBox.YMax < jaw_y + 0.01
            and e.BoundBox.XLength < 0.01
            and e.BoundBox.ZLength > 1.0]
    if ends:
        filleted = clamp.makeFillet(JAW_FILLET_R, ends)
        if filleted.isValid():
            clamp = filleted

    # 암나사 (아래턱 관통, 축 Z)
    neg = make_internal_thread_negative(JAW_T + 2.0)
    neg.translate(Vector(W / 2.0, HOLE_Y, -(OPENING + JAW_T) - 1.0))
    clamp = clamp.cut(neg)

    return body.fuse(clamp)


# ---------------------------------------------------------------------------
# 썸스크류 (업로드본 호환 규격)
# ---------------------------------------------------------------------------
def make_drawer():
    """서랍 부품 — 경사 천장을 따라가는 쐐기 상자.

    앞판이 개구 전체 높이를 덮고 위가 열려 있어 경사 공간까지 쓴다.
    측벽에는 레일 **홈**을 파고(리브는 본체 쪽), 홈은 앞에서 rail_y0 만큼
    들어간 지점부터 뒤끝까지만 있어 앞면에 드러나지 않는다. 홈 뒤쪽 벽은
    안쪽 보강 패드로 두께를 회복한다. 손가락 개구와 홈은 모두 빈 서랍의
    무게중심 높이에 둔다 (당김 시 기울임 모멘트 0).

    출력은 바닥을 베드에 — 위가 열려 있고 상면 경사도 재료가 끝나는
    방향이라 서포트가 필요 없다.
    """
    g = drawer_bay_geometry()
    dw, dd = g["drawer_w"], g["drawer_d"]
    rz = rail_z_local()

    box = drawer_shell()

    # 손가락 개구 — 앞판 관통, 무게중심 높이 중앙
    ell = Part.Ellipse(Vector(0, 0, 0), PULL_W / 2.0, PULL_H / 2.0)
    pull = Part.Face(Part.Wire(ell.toShape())).extrude(
        Vector(0, 0, DRAWER_FRONT_T + 2.0))
    pull.rotate(Vector(0, 0, 0), Vector(1, 0, 0), -90.0)   # 압출 방향 → +Y
    pull.translate(Vector(dw / 2.0, -1.0, rz))
    box = box.cut(pull)

    # 개구 모서리 라운딩 — 3mm 판을 그냥 뚫으면 각진 모서리가 손가락을
    # 파고든다. 실제로 힘이 걸리는 안쪽 모서리까지 함께 굴린다.
    pull_edges = [e for e in box.Edges
                  if e.BoundBox.YMax <= DRAWER_FRONT_T + 0.01
                  and abs(e.BoundBox.Center.x - dw / 2.0) < PULL_W / 2.0 + 0.5
                  and abs(e.BoundBox.Center.z - rz) < PULL_H / 2.0 + 0.5
                  and e.Length > 2.0 * PULL_FILLET_R]
    _DRAWER_INFO["pull_fillet"] = 0.0
    for r in (PULL_FILLET_R, 0.6, 0.4):
        try:
            out = box.makeFillet(r, pull_edges)
            if out.isValid():
                box = out
                _DRAWER_INFO["pull_fillet"] = r
                break
        except Exception:
            pass

    ry = g["rail_y0"]
    # 홈 뒤 벽 두께 회복용 안쪽 보강 패드 (홈보다 위아래·앞뒤로 넉넉히)
    pad_h = RAIL_GROOVE_H + 4.0
    for px in (DRAWER_WALL, dw - DRAWER_WALL - RAIL_PAD_T):
        box = box.fuse(Part.makeBox(RAIL_PAD_T, dd - ry - DRAWER_WALL, pad_h,
                                    Vector(px, ry, rz - pad_h / 2.0)))
    # 레일 홈 — 뒤끝은 열어 리브가 빠져나가게(+1), 앞끝은 막아 앞면에 안 보임
    for gx in (0.0, dw - RAIL_GROOVE_D):
        box = box.cut(Part.makeBox(RAIL_GROOVE_D, dd - ry + 1.0, RAIL_GROOVE_H,
                                   Vector(gx, ry, rz - RAIL_GROOVE_H / 2.0)))
    return box


def make_thumbscrew():
    knob = Part.makeCylinder(KNOB_D / 2.0, KNOB_H)
    # 그립 플루트 8개
    for i in range(8):
        a = math.radians(i * 45.0)
        r = KNOB_D / 2.0
        c = Part.makeCylinder(3.5, KNOB_H + 2.0,
                              Vector(r * math.cos(a), r * math.sin(a), -1.0))
        knob = knob.cut(c)

    # 샤프트(골 원통)가 나사산의 코어를 겸함
    shaft = Part.makeCylinder(THR_ROOT / 2.0, SHAFT_LEN, Vector(0, 0, KNOB_H))
    # 리지 z 범위 ≈ -1.4 .. (길이-1)+1.4 — 아래 끝은 손잡이 속,
    # 위 끝은 샤프트 끝 안쪽에 묻히도록 길이 -1, +KNOB_H+1 배치
    ridge = make_thread_ridge(THR_ROOT / 2.0, THR_OD / 2.0, 1.4, 0.6,
                              THR_PITCH, THR_LEN - 1.0)
    ridge.translate(Vector(0, 0, KNOB_H + 1.0))

    return knob.fuse(shaft).fuse(ridge)


# ---------------------------------------------------------------------------
# 생성 · 검증 · 내보내기
# ---------------------------------------------------------------------------
def check(name, ok, detail=""):
    print(("PASS" if ok else "FAIL"), name, detail)
    return ok


class TightBB(object):
    """테셀레이션 기반 실측 바운딩박스.

    Shape.BoundBox는 트림 전 곡면 제어점 기준의 보수적 추정이라
    헬리컬 절삭 후 실제보다 크게 나온다 (검증 실험으로 확인).
    """

    def __init__(self, shape, dev=0.3):
        pts, _ = shape.tessellate(dev)
        self.XMin = min(p.x for p in pts); self.XMax = max(p.x for p in pts)
        self.YMin = min(p.y for p in pts); self.YMax = max(p.y for p in pts)
        self.ZMin = min(p.z for p in pts); self.ZMax = max(p.z for p in pts)
        self.XLength = self.XMax - self.XMin
        self.YLength = self.YMax - self.YMin
        self.ZLength = self.ZMax - self.ZMin


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    doc = App.newDocument("pen_holder")

    print("== 부품 생성 ==")
    modules = {}
    fillets = {}
    for n in MODULE_SLOTS:
        modules[n], fillets[n] = fillet_front(make_module(n))
    tier1, fr_t = fillet_front(make_tier1())
    # 윗면은 마감면(결합면 아님)이라 앞 모서리도 필렛 대상에 포함
    topmod, fr_top = fillet_front(make_top_module(), height=TOP_H + 1.0)
    tier1d, fr_td = fillet_front(make_tier1(drawer=True))
    drawer = make_drawer()
    lid = make_lid()          # 평판이라 필렛 없음 (윗면이 마감면)
    screw = make_thumbscrew()

    ok = True
    print("== 검증 ==")
    # (a) 유효 솔리드
    for n in MODULE_SLOTS:
        ok &= check("module%d.isValid" % n, modules[n].isValid())
    ok &= check("tier1.isValid", tier1.isValid())
    ok &= check("topmodule.isValid", topmod.isValid())
    ok &= check("lid.isValid", lid.isValid())
    ok &= check("tier1-drawer.isValid", tier1d.isValid())
    ok &= check("drawer.isValid", drawer.isValid())
    ok &= check("screw.isValid", screw.isValid())

    # (b) 바운딩박스 (테셀레이션 실측)
    for n in MODULE_SLOTS:
        bb = TightBB(modules[n])
        ok &= check("module%d bbox" % n, abs(bb.XLength - W) < 0.1
                    and abs(bb.YLength - D) < 0.1
                    and abs(bb.ZMax - H) < 0.05
                    and abs(bb.ZMin + SKIRT_D) < 0.05,
                    "X=%.2f Y=%.2f Z=%.1f..%.1f"
                    % (bb.XLength, bb.YLength, bb.ZMin, bb.ZMax))

    bt = TightBB(tier1)
    ok &= check("tier1 bbox", abs(bt.XLength - W) < 0.1
                and abs(bt.YMax - D) < 0.1
                and abs(bt.ZMin + (OPENING + JAW_T)) < 0.1,
                "Y max=%.1f(뒷면 플러시) Z=%.1f..%.1f"
                % (bt.YMax, bt.ZMin, bt.ZMax))

    bp = TightBB(topmod)
    ok &= check("topmodule bbox", abs(bp.XLength - W) < 0.1
                and abs(bp.YLength - D) < 0.1
                and abs(bp.ZMax - TOP_H) < 0.05
                and abs(bp.ZMin + SKIRT_D) < 0.05,
                "X=%.2f Y=%.2f Z=%.1f..%.1f" % (bp.XLength, bp.YLength,
                                                bp.ZMin, bp.ZMax))
    bl = TightBB(lid)
    ok &= check("lid bbox", abs(bl.XLength - W) < 0.1
                and abs(bl.YLength - D) < 0.1
                and abs(bl.ZMax - LID_T) < 0.05,
                "X=%.2f Y=%.2f Z=%.1f..%.1f" % (bl.XLength, bl.YLength,
                                                bl.ZMin, bl.ZMax))
    ok &= check("topmodule height", abs(TOP_H - H / 3.0) < 0.01,
                "마감 모듈 높이 %.1fmm = 3칸 모듈 1칸(%.1fmm)"
                % (TOP_H, H / 3.0))
    # 마감 모듈: 바닥은 열려 있고(아래 칸과 연결) 천장은 막혀 있어야 한다
    floored = topmod.isInside(Vector(W / 2.0, D / 2.0, BOT_T / 2.0), 0.01, True)
    railed = topmod.isInside(Vector(WALL + FLANGE / 2.0, D / 2.0, BOT_T / 2.0),
                             0.01, True)
    ceiled = topmod.isInside(Vector(W / 2.0, D / 2.0, TOP_H - LID_T / 2.0),
                             0.01, True)
    ok &= check("topmodule open bottom / closed top",
                (not floored) and railed and ceiled,
                "바닥 개방=%s, 레일 존치=%s, 천장 일체=%s"
                % (not floored, railed, ceiled))

    bs = TightBB(screw)
    # 플루트가 손잡이 가장자리를 깎아 실측 폭은 공칭 지름보다 약간 작다
    ok &= check("screw bbox", KNOB_D - 1.0 < bs.XLength <= KNOB_D + 0.1
                and abs(bs.ZLength - (KNOB_H + SHAFT_LEN)) < 0.2,
                "D=%.1f (공칭 %.1f) H=%.1f" % (bs.XLength, KNOB_D, bs.ZLength))
    # 체결 가능 상판 두께 — 나사가 아래턱 위로 나오는 만큼이 물림 범위다
    reach = SHAFT_LEN - JAW_T          # 턱 위 최대 돌출
    min_desk = OPENING - reach         # 물 수 있는 가장 얇은 상판
    ok &= check("clamp reach", min_desk <= 15.0,
                "상판 %.0f~%.0fmm 체결 가능 (턱 위 돌출 %.0fmm)"
                % (max(min_desk, 0.0), OPENING, reach))
    # 나사 구멍 주변 재료 — 클램프 폭을 더 줄이면 여기가 먼저 위험해진다
    side = CLAMP_W / 2.0 - (THR_OD / 2.0 + THR_CLEAR)
    ok &= check("clamp hole margin", side >= 8.0,
                "구멍(Ø%.1f) 양옆 재료 %.1fmm (최소 8mm)"
                % (THR_OD + 2 * THR_CLEAR, side))

    # (c) 나사-암나사 정합 (구성값 검산)
    ok &= check("thread fit", THR_CLEAR >= 0.3,
                "반경 공차 %.1fmm (수나사 OD %.1f / 암나사 크레스트 %.1f)"
                % (THR_CLEAR, THR_OD, THR_OD + 2 * THR_CLEAR))
    # 스냅 정합 (구성값 검산)
    engage = BUMP_D - CLEAR
    ok &= check("snap fit", 1.0 < engage < 3.0 and WIN_H - BUMP_H >= 0.3,
                "돌기 물림 %.2fmm, 창 상하 여유 %.1fmm" % (engage, WIN_H - BUMP_H))
    # 벽 두께 vs 스냅 돌기 — 벽을 더 얇게 하면 돌기가 벽을 관통하거나
    # 캐치 물림이 사라진다. 조용히 깨지는 관계라 검증으로 고정한다.
    eng = BUMP_D - CLEAR
    ok &= check("snap wall guard", WALL - eng >= 0.5 and eng >= 1.0,
                "돌기 물림 %.2fmm / 벽 %.1fmm → 관통 여유 %.2fmm (0.5 이상)"
                % (eng, WALL, WALL - eng))
    # 앞쪽 필렛 적용 확인
    ok &= check("front fillet",
                all(r > 0 for r in fillets.values()) and fr_t > 0
                and fr_top > 0,
                "module2 r=%.1f / module3 r=%.1f / tier1 r=%.1f / top r=%.1f"
                % (fillets[2], fillets[3], fr_t, fr_top))
    # 앞턱 램프 자기지지 각도 (뒷면을 베드에 대고 출력하는 기준)
    # 프린트 높이 방향 = 모델 y, 측방 = 모델 z
    ramp_deg = math.degrees(math.atan2(LIP_BASE, LIP + LIP_BASE * TAN))
    ok &= check("lip self-support", ramp_deg > 45.0,
                "앞턱 램프 %.1f° (베드 대비, 45° 초과 필요)" % ramp_deg)
    # 타공 배치 확인 (부품별 구멍 수)
    if PERFORATE:
        counts = {n: len(perforation_cuts(n).Solids) for n in (2, 3)}
        ok &= check("perforation", counts[2] > 40 and counts[3] > 40,
                    "2칸 %d개 / 3칸 %d개 (관통 기준, 벽당 동일)"
                    % (counts[2], counts[3]))

    # --- 서랍 변형 검증 ---
    g = drawer_bay_geometry()
    rz = rail_z_local()
    side = (g["bay_w"] - g["drawer_w"]) / 2.0
    ok &= check("drawer fit", side >= 0.35 and DRAWER_V_CLEAR >= 0.45,
                "좌우 각 %.2f · 상하 %.2fmm 여유 (서랍 %.1f×%.0f, 앞 %.1f→뒤 %.1f 쐐기)"
                % (side, DRAWER_V_CLEAR, g["drawer_w"], g["drawer_d"],
                   g["h_front"], g["h_rear"]))
    stop = g["bay_d"] - g["drawer_d"]
    ok &= check("drawer stop", stop >= 1.5,
                "밀어 넣으면 뒷벽 %.1fmm 앞에서 멈춤" % stop)
    ok &= check("pull opening",
                PULL_W >= 28.0 and PULL_H >= 15.0
                and rz - PULL_H / 2.0 > DRAWER_BOT_T,
                "%.0f×%.0fmm, 중심 z=%.1f = 빈 서랍 무게중심 (모멘트 0)"
                % (PULL_W, PULL_H, rz))
    ok &= check("pull edge rounding", _DRAWER_INFO.get("pull_fillet", 0) > 0,
                "개구 모서리 r%.1f (앞뒤 양면, 손가락 닿는 면)"
                % _DRAWER_INFO.get("pull_fillet", 0))
    rail_v = (RAIL_GROOVE_H - RAIL_RIB_H) / 2.0
    rail_d = RAIL_GROOVE_D - RAIL_RIB_D
    wall_left = DRAWER_WALL - RAIL_GROOVE_D + RAIL_PAD_T
    ok &= check("rail fit",
                rail_v >= 0.25 and rail_d >= 0.35 and wall_left >= 1.5,
                "상하 각 %.2f · 깊이 %.2fmm 여유, 홈 뒤 서랍 벽 %.1fmm(보강 포함)"
                % (rail_v, rail_d, wall_left))
    travel = g["drawer_d"] - g["rail_y0"]
    ok &= check("rail extent",
                g["rail_y0"] > 5.0
                and abs(g["rail_y0"] / g["drawer_d"] - RAIL_START) < 0.01,
                "앞에서 %.0fmm 들어간 지점부터(앞면 노출 없음), 깊이의 %.0f%%가 안내 → %.0fmm 인출까지"
                % (g["rail_y0"], (1 - RAIL_START) * 100, travel))
    # 서랍 구간에는 타공이 없어야 한다 (본체) / 서랍 자체도 타공 없음
    bay = (g["ceil_front"] + 3.0, TAN)
    bay_holes = [c for c in perforation_cuts(TIER1_SLOTS, H,
                                            bay_ceiling=bay).Solids
                 if c.BoundBox.ZMin < bay[0] - TAN * c.BoundBox.YMax]
    perf_r = PERF_D / 2.0
    drawer_holes = [f for f in drawer.Faces
                    if isinstance(f.Surface, Part.Cylinder)
                    and abs(f.Surface.Radius - perf_r) < 0.1]
    ok &= check("no perforation at drawer",
                len(bay_holes) == 0 and len(drawer_holes) == 0,
                "서랍 구간 본체 %d개 · 서랍 %d개" % (len(bay_holes),
                                                len(drawer_holes)))
    ok &= check("drawer volume", drawer.Volume > 0,
                "서랍 재료 %.0fcm³, 내부 용적 약 %.0fcm³"
                % (drawer.Volume / 1000.0,
                   (g["drawer_w"] * g["drawer_d"]
                    * (g["h_front"] + g["h_rear"]) / 2.0
                    - drawer.Volume) / 1000.0))

    print("== 내보내기 ==")
    parts = [("module%d" % n, modules[n]) for n in MODULE_SLOTS]
    parts += [("tier1", tier1), ("tier1-drawer", tier1d),
              ("drawer", drawer), ("topmodule", topmod), ("lid", lid),
              ("thumbscrew", screw)]
    objs = {}
    for name, shape in parts:
        obj = doc.addObject("Part::Feature", name)
        obj.Shape = shape
        objs[name] = obj
        path = os.path.join(OUT_DIR, name + ".stl")
        mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.1,
                                      AngularDeflection=0.5)
        mesh.write(path)  # 바이너리 STL — 형상 원점 기준 (Placement 이전)
        print("STL:", path)

    # 문서 배치 (스크린샷용) — STL 내보내기 이후에만 적용해 출력물은
    # 원점을 유지한다. 위: 부품 나열, 오른쪽: 조립 상태.
    print("== 배치 ==")
    row = (["tier1", "tier1-drawer", "drawer"]
           + ["module%d" % n for n in MODULE_SLOTS]
           + ["topmodule", "lid", "thumbscrew"])
    for i, name in enumerate(row):
        objs[name].Placement = App.Placement(
            Vector(i * (W + LAYOUT_GAP), 0, 0), App.Rotation())
        print("  나열 %-11s x=%.0f" % (name, i * (W + LAYOUT_GAP)))

    asm_x = len(row) * (W + LAYOUT_GAP) + LAYOUT_GAP
    # 썸스크류: 나사부 시작(z=11)을 아래턱 밑면(z=-(OPENING+JAW_T))에 맞춤
    screw_dz = -(OPENING + JAW_T) - 11.0
    asm2_x = asm_x + W + LAYOUT_GAP          # 뚜껑 사용 예 (2칸 모듈 + 뚜껑)
    for name, shape, pos in (
            ("asm_tier1", tier1, Vector(asm_x, 0, 0)),
            ("asm_module3", modules[3], Vector(asm_x, 0, H)),
            ("asm_topmodule", topmod, Vector(asm_x, 0, 2 * H)),
            ("asm_screw", screw, Vector(asm_x + W / 2.0, HOLE_Y, screw_dz)),
            ("asm_module2", modules[2], Vector(asm2_x, 0, 0)),
            ("asm_lid", lid, Vector(asm2_x, 0, H)),
            # 분해 뷰 — 뚜껑을 띄워 별개 부품임이 드러나게
            ("exp_module2", modules[2], Vector(asm2_x + W + LAYOUT_GAP, 0, 0)),
            ("exp_lid", lid, Vector(asm2_x + W + LAYOUT_GAP, 0, H + 35.0)),
            # 서랍을 절반 빼낸 분해 뷰
            ("exp_tier1d", tier1d, Vector(asm2_x + 2 * (W + LAYOUT_GAP), 0, 0)),
            ("exp_drawer", drawer,
             Vector(asm2_x + 2 * (W + LAYOUT_GAP) + WALL + DRAWER_CLEAR,
                    -55.0, BOT_T + DRAWER_V_CLEAR / 2.0))):
        o = doc.addObject("Part::Feature", name)
        o.Shape = shape
        o.Placement = App.Placement(pos, App.Rotation())
        print("  조립 %-11s at (%.0f, %.0f, %.0f)" % (name, pos.x, pos.y, pos.z))

    doc.recompute()
    fcstd = os.path.join(OUT_DIR, "pen_holder.FCStd")
    doc.saveAs(fcstd)
    print("FCStd:", fcstd)

    print("== 결과 ==")
    print("VERIFICATION", "PASS" if ok else "FAIL")


main()
