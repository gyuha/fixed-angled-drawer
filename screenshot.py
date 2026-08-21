# -*- coding: utf-8 -*-
"""기준 변형(output/w70-wall2.4)의 FCStd 뷰를 PNG로 저장 (FreeCAD GUI 필요).

실행:  /Applications/FreeCAD.app/Contents/MacOS/FreeCAD screenshot.py
산출:  output/shot-<뷰이름>.png

GUI가 잠깐 떴다 닫힌다. 헤드리스(freecadcmd)에서는 Gui 모듈이 없어
동작하지 않으므로 위 실행줄을 그대로 쓸 것.
"""
import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

HERE = os.path.dirname(os.path.abspath(__file__))
REF_VARIANT = "w70-wall2.4"   # pen_holder.py 의 REF_VARIANT 와 일치
DOC = os.path.join(HERE, "output", REF_VARIANT, "pen_holder.FCStd")
SIZE = (1600, 1200)

# 부품 색상 — 색은 GUI 속성(ViewObject)이라 헤드리스 pen_holder.py 에서는
# 지정할 수 없다. 여기서 칠하고 문서를 저장해 FCStd 에도 남긴다.
SCREW_COLOR = (0.80, 0.11, 0.11)   # 썸스크류: 빨강
DRAWER_COLOR = (0.95, 0.95, 0.95)  # 서랍: 흰색 (완전 백색은 흰 배경에 묻혀 살짝 낮춤)


def part_color(name):
    """객체 이름 → 색. asm_/exp_ 접두어를 벗겨 부품 이름으로 판정한다.

    'drawer'(서랍 부품)와 'tier1_drawer'(서랍 변형 본체)를 반드시 구분해야
    하므로 부분 문자열이 아니라 접두어를 벗긴 정확 비교를 쓴다.
    """
    base = name.split("_", 1)[1] if name.startswith(("asm_", "exp_")) else name
    if base == "drawer":
        return DRAWER_COLOR
    if "screw" in base:
        return SCREW_COLOR
    return None

# 뷰 이름 → (표시 그룹, 카메라 메서드)
# 그룹은 객체 이름 접두어로 고른다 — 부품이 늘어도 이 목록을 고칠 일이 없다.
#   "asm_" → assembly (조립 상태) / "exp_" → exploded (뚜껑 분해)
#   그 외   → parts (부품 나열)
VIEWS = [
    ("parts-axo", "parts", "viewAxonometric"),
    ("assembly-axo", "assembly", "viewAxonometric"),
    ("assembly-front", "assembly", "viewFront"),
    ("assembly-right", "assembly", "viewRight"),
    ("lid-open", "exploded", "viewAxonometric"),
]


def shoot():
    doc = App.openDocument(DOC)
    Gui.updateGui()
    Gui.ActiveDocument = Gui.getDocument(doc.Name)
    view = Gui.activeDocument().activeView()
    Gui.Selection.clearSelection()     # 선택 하이라이트(초록)가 찍히지 않게

    # 부품별 색 지정 (나열·조립·분해 뷰의 모든 인스턴스)
    for o in doc.Objects:
        col = part_color(o.Name)
        if col:
            o.ViewObject.ShapeColor = col
            o.ViewObject.DiffuseColor = [col]
            print("색상:", o.Name, "→", "빨강" if col == SCREW_COLOR else "흰색")

    for name, group, cam in VIEWS:
        for o in doc.Objects:
            if o.Name.startswith("asm_"):
                g = "assembly"
            elif o.Name.startswith("exp_"):
                g = "exploded"
            else:
                g = "parts"
            o.ViewObject.Visibility = (g == group)
        getattr(view, cam)()
        Gui.SendMsgToActiveView("ViewFit")
        Gui.updateGui()
        path = os.path.join(HERE, "output", "shot-%s.png" % name)
        view.saveImage(path, SIZE[0], SIZE[1], "White")
        print("PNG:", path)
    for o in doc.Objects:                 # 저장 전 모든 부품을 다시 보이게
        o.ViewObject.Visibility = True
    doc.save()                            # 색상을 FCStd 에 보존
    print("FCStd 저장:", DOC)
    App.closeDocument(doc.Name)
    Gui.getMainWindow().close()


# GUI 이벤트 루프가 준비된 뒤 실행하고, 끝나면 앱을 종료한다
QtCore.QTimer.singleShot(1200, shoot)
QtCore.QTimer.singleShot(9000, Gui.getMainWindow().close)
