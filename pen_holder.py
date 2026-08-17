# -*- coding: utf-8 -*-
"""적층형 경사 필통 — 파라메트릭 FreeCAD 스크립트

실행:  /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd pen_holder.py
산출:  output/pen_holder.FCStd, output/{tier1,module2,module3,thumbscrew}.stl

부품 4종 (모듈 높이는 모두 170mm — 어떤 조합으로 쌓아도 호환)
  - module2    : 적층 모듈 2칸 (칸 피치 85mm, 긴 물건용)
  - module3    : 적층 모듈 3칸 (칸 피치 56.7mm, 촘촘한 분류용)
  - tier1      : 1단 3칸 (본체 + 뒷면 일체형 책상 클램프 + 암나사)
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
# 파라미터 (실측 근거: reference/pen-holder-reference.stl)
# ---------------------------------------------------------------------------
W = 80.0            # 모듈 폭 (요구 사양 8cm)
D = 100.0           # 모듈 깊이 (요구 사양 10cm)
H = 170.0           # 모듈 높이 (요구 사양 17cm, 전 부품 공통 — 적층 호환)
TIER1_SLOTS = 3     # 1단(바닥 모듈) 칸 수
MODULE_SLOTS = (2, 3)  # 적층 모듈 변형별 칸 수 → module2 / module3

WALL = 3.0          # 측벽·뒷벽·앞벽 두께 (참고 STL 실측 ≈3mm)
BOT_T = 4.0         # 바닥판 두께 (참고 STL 실측 ≈4mm)
SHELF_T = 4.0       # 선반 수직 두께 (참고 STL 실측 ≈4mm)
ANGLE = 20.0        # 선반 경사각(도) — 참고 STL 법선 실측
LIP = 3.0           # 선반 앞 끝 위 낮은 턱 높이
# 앞턱 뒷면을 수직 단차로 두면, 뒷면을 베드에 대고 출력할 때 아래를 향한
# 평평한 천장이 되어 서포트가 필요하다. 기저 폭 LIP_BASE 만큼 램프로
# 눕혀 자기지지 각도(베드 대비 45° 초과)를 만든다. LIP_BASE > LIP 필수.
LIP_BASE = 8.0      # 앞턱 램프의 깊이 방향 기저 폭
BOTTOM_CUBBY = True  # 최하단 선반 아래를 전면 개방 수납 포켓으로 (앞턱 LIP 유지)
FLANGE = 3.0        # 하단 개방 시 측벽 안쪽에 남기는 바닥판 레일 폭 (스커트 부착용)
FILLET_R = 1.4      # 앞쪽 모서리 필렛 반경 (벽 3mm: 양쪽 합이 면 폭 미만이어야 함)

# --- 측벽 타공 (장식·통기) ---
PERFORATE = True    # 측벽 타공 패턴 on/off
PERF_D = 4.5        # 구멍 지름
PERF_PITCH = 8.0    # 구멍 간격 (스태거드/벌집 배열)
PERF_MARGIN = 1.5   # 선반 슬래브 띠와의 최소 여유

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
CLAMP_W = 60.0      # 클램프 폭 (중앙 정렬)
JAW_REACH = 55.0    # 뒷면에서 앞으로 뻗는 아래턱 길이
HOLE_Y = 72.0       # 나사 구멍 중심 y (책상 물림면 y=D-PLATE_T 에서 16mm 안쪽)

# --- 나사 (업로드 썸스크류 실측: OD18.5 / 골 12.7 / 피치 4 / 나사부 22) ---
THR_PITCH = 4.0
THR_OD = 18.5
THR_ROOT = 12.7
THR_LEN = 22.0
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


def fillet_front(shape, radius=FILLET_R):
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
             and e.BoundBox.ZMax < H - 0.01]
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
def perforation_cuts(n_comp):
    """측벽 타공용 X관통 원기둥 컴파운드 (없으면 None).

    회피 조건이 y/z에만 걸리므로 양 측벽의 배치가 동일 — 관통 원기둥
    하나가 두 벽을 함께 뚫고, 중간은 칸 내부 빈 공간이라 무해하다.
    선반 슬래브 띠(± PERF_MARGIN), 캐치 창·상단 결합부(z>150),
    하단(z<10), 앞뒤 가장자리(y 8~90 밖)는 비운다.
    """
    pitch = H / n_comp
    r = PERF_D / 2.0
    row_h = PERF_PITCH * 0.866  # 벌집 배열 행 간격
    cyls = []
    row = 0
    z = 10.0 + r
    while z + r <= 150.0:
        y = 8.0 + (PERF_PITCH / 2.0 if row % 2 else 0.0)
        while y + r <= 90.0:
            clear = True
            for k in range(n_comp):
                ft = k * pitch + BOT_T + (IN_D - y) * TAN  # 선반 상면 z
                if (z + r > ft - SHELF_T - PERF_MARGIN
                        and z - r < ft + PERF_MARGIN):
                    clear = False
                    break
            if clear:
                cyls.append(Part.makeCylinder(
                    r, W + 2.0, Vector(-1.0, y, z), Vector(1, 0, 0)))
            y += PERF_PITCH
        z += row_h
        row += 1
    return Part.makeCompound(cyls) if cyls else None


def make_body(n_comp, bottom_open=False):
    """n_comp: 경사 칸 수 (칸 피치 = H / n_comp).

    bottom_open=True: 하단 포켓의 바닥판·앞턱을 제거해, 적층 시 아래
    모듈의 최상단 칸과 공간이 이어진다 (적층 모듈용). tier1은 False로
    바닥을 유지한다. 측벽 안쪽 FLANGE 폭 바닥판 레일은 남긴다 (측면
    스커트가 매달리는 자리)."""
    pitch = H / n_comp
    body = Part.makeBox(W, D, H)

    cuts = []
    for k in range(n_comp):
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

    # 상단 캐치 창 (양 측벽 관통)
    for x0 in (-0.5, W - WALL - 0.5):
        win = Part.makeBox(WALL + 1.0, WIN_W, WIN_H,
                           Vector(x0, HOOK_Y - WIN_W / 2.0, WIN_TOP - WIN_H))
        cuts.append(win)

    # 측벽 타공 패턴
    if PERFORATE:
        holes = perforation_cuts(n_comp)
        if holes:
            cuts.append(holes)

    for c in cuts:
        body = body.cut(c)
    return body


# ---------------------------------------------------------------------------
# 적층 모듈 = 본체 + 바닥 스커트/스냅 후크
# ---------------------------------------------------------------------------
def make_module(n_comp):
    body = make_body(n_comp, bottom_open=True)

    sk_y0, sk_y1 = 8.0, D - WALL - CLEAR          # 스커트 y 범위 (측면)
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
    bump_l = prism_xz([
        (xl, -SKIRT_D),
        (xl - BUMP_D, -SKIRT_D + (BUMP_D)),        # 45° 진입 챔퍼
        (xl - BUMP_D, -SKIRT_D + BUMP_H),
        (xl, -SKIRT_D + BUMP_H),
    ], HOOK_Y - HOOK_W / 2.0, HOOK_W)
    xr = W - WALL - CLEAR                          # 우측 스커트 바깥면
    bump_r = prism_xz([
        (xr, -SKIRT_D),
        (xr + BUMP_D, -SKIRT_D + BUMP_D),
        (xr + BUMP_D, -SKIRT_D + BUMP_H),
        (xr, -SKIRT_D + BUMP_H),
    ], HOOK_Y - HOOK_W / 2.0, HOOK_W)
    parts += [bump_l, bump_r]

    for p in parts:
        body = body.fuse(p)
    return body


# ---------------------------------------------------------------------------
# 1단 = 본체 + 뒷면 일체형 클램프(암나사)
# ---------------------------------------------------------------------------
def make_tier1():
    body = make_body(TIER1_SLOTS)

    # 클램프는 뒷면 평면(y=D)과 플러시 — 뒷판이 안쪽으로 들어가고,
    # 본체 바닥(z=0)과의 접합 단면(CLAMP_W × PLATE_T)이 강성을 담당
    x0 = (W - CLAMP_W) / 2.0
    plate = Part.makeBox(CLAMP_W, PLATE_T, OPENING + JAW_T,
                         Vector(x0, D - PLATE_T, -(OPENING + JAW_T)))
    jaw = Part.makeBox(CLAMP_W, JAW_REACH, JAW_T,
                       Vector(x0, D - JAW_REACH, -(OPENING + JAW_T)))
    clamp = plate.fuse(jaw)

    # 암나사 (아래턱 관통, 축 Z)
    neg = make_internal_thread_negative(JAW_T + 2.0)
    neg.translate(Vector(W / 2.0, HOLE_Y, -(OPENING + JAW_T) - 1.0))
    clamp = clamp.cut(neg)

    return body.fuse(clamp)


# ---------------------------------------------------------------------------
# 썸스크류 (업로드본 호환 규격)
# ---------------------------------------------------------------------------
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
    shaft = Part.makeCylinder(THR_ROOT / 2.0, 24.0, Vector(0, 0, KNOB_H))
    # 리지 z 범위 ≈ -1.4 .. (길이-1)+1.4 — 아래 끝은 손잡이 속,
    # 위 끝은 샤프트 끝(z=34) 안쪽에 묻히도록 길이 -1, +11 배치
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
    screw = make_thumbscrew()

    ok = True
    print("== 검증 ==")
    # (a) 유효 솔리드
    for n in MODULE_SLOTS:
        ok &= check("module%d.isValid" % n, modules[n].isValid())
    ok &= check("tier1.isValid", tier1.isValid())
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

    bs = TightBB(screw)
    # 플루트가 손잡이 가장자리를 깎아 실측 폭은 공칭 지름보다 약간 작다
    ok &= check("screw bbox", KNOB_D - 1.0 < bs.XLength <= KNOB_D + 0.1
                and abs(bs.ZLength - 34.0) < 0.2,
                "D=%.1f (공칭 %.1f) H=%.1f" % (bs.XLength, KNOB_D, bs.ZLength))

    # (c) 나사-암나사 정합 (구성값 검산)
    ok &= check("thread fit", THR_CLEAR >= 0.3,
                "반경 공차 %.1fmm (수나사 OD %.1f / 암나사 크레스트 %.1f)"
                % (THR_CLEAR, THR_OD, THR_OD + 2 * THR_CLEAR))
    # 스냅 정합 (구성값 검산)
    engage = BUMP_D - CLEAR
    ok &= check("snap fit", 1.0 < engage < 3.0 and WIN_H - BUMP_H >= 0.3,
                "돌기 물림 %.2fmm, 창 상하 여유 %.1fmm" % (engage, WIN_H - BUMP_H))
    # 앞쪽 필렛 적용 확인
    ok &= check("front fillet",
                all(r > 0 for r in fillets.values()) and fr_t > 0,
                "module2 r=%.1f / module3 r=%.1f / tier1 r=%.1f"
                % (fillets[2], fillets[3], fr_t))
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

    print("== 내보내기 ==")
    parts = [("module%d" % n, modules[n]) for n in MODULE_SLOTS]
    parts += [("tier1", tier1), ("thumbscrew", screw)]
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
    row = ["tier1"] + ["module%d" % n for n in MODULE_SLOTS] + ["thumbscrew"]
    for i, name in enumerate(row):
        objs[name].Placement = App.Placement(
            Vector(i * (W + LAYOUT_GAP), 0, 0), App.Rotation())
        print("  나열 %-11s x=%.0f" % (name, i * (W + LAYOUT_GAP)))

    asm_x = len(row) * (W + LAYOUT_GAP) + LAYOUT_GAP
    # 썸스크류: 나사부 시작(z=11)을 아래턱 밑면(z=-(OPENING+JAW_T))에 맞춤
    screw_dz = -(OPENING + JAW_T) - 11.0
    for name, shape, pos in (
            ("asm_tier1", tier1, Vector(asm_x, 0, 0)),
            ("asm_module3", modules[3], Vector(asm_x, 0, H)),
            ("asm_screw", screw, Vector(asm_x + W / 2.0, HOLE_Y, screw_dz))):
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
