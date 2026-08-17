# -*- coding: utf-8 -*-
"""적층형 경사 필통 — 파라메트릭 FreeCAD 스크립트

실행:  /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd pen_holder.py
산출:  output/pen_holder.FCStd, output/tier1.stl, output/module.stl, output/thumbscrew.stl

부품 3종
  - module     : 적층 모듈 (경사 2칸, 바닥 스냅 후크 + 상단 캐치 창)
  - tier1      : 1단 (모듈 본체 + 뒷면 일체형 책상 클램프 + 암나사)
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
# 파라미터 (participant: reference/pen-holder-reference.stl 실측 근거)
# ---------------------------------------------------------------------------
W = 80.0            # 모듈 폭 (요구 사양 8cm)
D = 100.0           # 모듈 깊이 (요구 사양 10cm)
H = 170.0           # 모듈 높이 (요구 사양 17cm)
N_COMP = 2          # 경사 칸 수 (그릴링 확정)
PITCH = H / N_COMP  # 칸 피치 85mm

WALL = 3.0          # 측벽·뒷벽·앞벽 두께 (참고 STL 실측 ≈3mm)
BOT_T = 4.0         # 바닥판 두께 (참고 STL 실측 ≈4mm)
SHELF_T = 4.0       # 선반 수직 두께 (참고 STL 실측 ≈4mm)
ANGLE = 20.0        # 선반 경사각(도) — 참고 STL 법선 실측
LIP = 6.0           # 선반 앞 끝 위 낮은 턱 높이
BOTTOM_CUBBY = True  # 최하단 선반 아래를 전면 개방 수납 포켓으로 (앞턱 LIP 유지)
FLANGE = 3.0        # 하단 개방 시 측벽 안쪽에 남기는 바닥판 레일 폭 (스커트 부착용)

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
OPENING = 40.0      # 상판 물림 개구 (상판 18~25mm + 조임 여유)
PLATE_T = 12.0      # 뒷판 두께
JAW_T = 14.0        # 아래턱 두께 (나사 4mm 피치 × 3.5산 물림)
CLAMP_W = 60.0      # 클램프 폭 (중앙 정렬)
JAW_REACH = 55.0    # 상판 아래로 들어가는 길이
PLATE_UP = 40.0     # 뒷판이 모듈 뒷벽을 타고 올라가는 보강 높이
HOLE_Y = 72.0       # 나사 구멍 중심 y (책상 모서리에서 28mm 안쪽)

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
def make_body(bottom_open=False):
    """bottom_open=True: 하단 포켓의 바닥판·앞턱을 제거해, 적층 시 아래
    모듈의 최상단 칸과 공간이 이어진다 (적층 모듈용). tier1은 False로
    바닥을 유지한다. 측벽 안쪽 FLANGE 폭 바닥판 레일은 남긴다 (측면
    스커트가 매달리는 자리)."""
    body = Part.makeBox(W, D, H)

    cuts = []
    for k in range(N_COMP):
        b = k * PITCH
        floor_back = b + BOT_T                    # 선반 상면 z (뒷벽 쪽, y=97)
        ff = floor_back + IN_D * TAN              # 선반 상면 z (앞면, y=0)
        lip_top = ff + LIP
        z_at_lip = ff - WALL * TAN                # y=WALL 에서의 선반 상면 z

        if k < N_COMP - 1:
            # 천장 = 위 선반의 밑면
            b_up = (k + 1) * PITCH
            ceil_front = (b_up + BOT_T + IN_D * TAN) - SHELF_T
            ceil_back = (b_up + BOT_T) - SHELF_T
        else:
            ceil_front = ceil_back = H            # 최상단 칸은 위로 개방

        poly = [
            (0.0, lip_top),
            (0.0, ceil_front),
            (IN_D, ceil_back),
            (IN_D, floor_back),
            (WALL, z_at_lip),
            (WALL, lip_top),
        ]
        cuts.append(prism_yz(poly, WALL, W - 2 * WALL))

        if k == 0 and BOTTOM_CUBBY:
            # 최하단 선반 아래 전면 개방 수납 포켓
            # 바닥 = 바닥판 상면, 천장 = 경사 선반 밑면, 앞에 LIP 턱
            under_front = BOT_T + IN_D * TAN - SHELF_T   # y=0 선반 밑면 z
            y_end = IN_D - SHELF_T / TAN  # 선반 밑면이 바닥판 상면과 만나는 y
            if under_front > BOT_T + LIP + 2.0:
                cubby = [
                    (0.0, BOT_T + LIP),
                    (0.0, under_front),
                    (y_end, BOT_T),
                    (WALL, BOT_T),
                    (WALL, BOT_T + LIP),
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
                # 앞턱 제거 (레일 위 잔여 스터브 포함 전폭)
                cuts.append(Part.makeBox(W - 2 * WALL, WALL + 0.6,
                                         LIP + 0.6,
                                         Vector(WALL, -0.5, BOT_T - 0.1)))

    # 상단 캐치 창 (양 측벽 관통)
    for x0 in (-0.5, W - WALL - 0.5):
        win = Part.makeBox(WALL + 1.0, WIN_W, WIN_H,
                           Vector(x0, HOOK_Y - WIN_W / 2.0, WIN_TOP - WIN_H))
        cuts.append(win)

    for c in cuts:
        body = body.cut(c)
    return body


# ---------------------------------------------------------------------------
# 적층 모듈 = 본체 + 바닥 스커트/스냅 후크
# ---------------------------------------------------------------------------
def make_module():
    body = make_body(bottom_open=True)

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

    # 뒷면 스커트
    parts.append(Part.makeBox(W - 2 * (WALL + CLEAR), SKIRT_T, SKIRT_D,
                              Vector(WALL + CLEAR, D - WALL - CLEAR - SKIRT_T,
                                     -SKIRT_D)))

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
    body = make_body()

    x0 = (W - CLAMP_W) / 2.0
    plate = Part.makeBox(CLAMP_W, PLATE_T, OPENING + JAW_T + PLATE_UP,
                         Vector(x0, D, -(OPENING + JAW_T)))
    jaw = Part.makeBox(CLAMP_W, D + PLATE_T - (D - JAW_REACH), JAW_T,
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
    module = make_module()
    tier1 = make_tier1()
    screw = make_thumbscrew()

    ok = True
    print("== 검증 ==")
    # (a) 유효 솔리드
    ok &= check("module.isValid", module.isValid())
    ok &= check("tier1.isValid", tier1.isValid())
    ok &= check("screw.isValid", screw.isValid())

    # (b) 바운딩박스 (테셀레이션 실측)
    bb = TightBB(module)
    ok &= check("module bbox XY", abs(bb.XLength - W) < 0.1
                and abs(bb.YLength - D) < 0.1,
                "X=%.2f Y=%.2f" % (bb.XLength, bb.YLength))
    ok &= check("module body height", abs(bb.ZMax - H) < 0.05
                and abs(bb.ZMin + SKIRT_D) < 0.05,
                "Z=%.1f..%.1f (본체 170 + 스커트 12)" % (bb.ZMin, bb.ZMax))

    bt = TightBB(tier1)
    ok &= check("tier1 bbox", abs(bt.XLength - W) < 0.1
                and abs(bt.YMax - (D + PLATE_T)) < 0.1
                and abs(bt.ZMin + (OPENING + JAW_T)) < 0.1,
                "Y max=%.1f Z=%.1f..%.1f" % (bt.YMax, bt.ZMin, bt.ZMax))

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

    print("== 내보내기 ==")
    for name, shape in (("module", module), ("tier1", tier1),
                        ("thumbscrew", screw)):
        obj = doc.addObject("Part::Feature", name)
        obj.Shape = shape
        path = os.path.join(OUT_DIR, name + ".stl")
        mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.1,
                                      AngularDeflection=0.5)
        mesh.write(path)  # 바이너리 STL
        print("STL:", path)

    doc.recompute()
    fcstd = os.path.join(OUT_DIR, "pen_holder.FCStd")
    doc.saveAs(fcstd)
    print("FCStd:", fcstd)

    print("== 결과 ==")
    print("VERIFICATION", "PASS" if ok else "FAIL")


main()
