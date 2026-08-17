# -*- coding: utf-8 -*-
"""output/pen_holder.FCStd 의 뷰를 PNG로 저장 (FreeCAD GUI 필요).

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
DOC = os.path.join(HERE, "output", "pen_holder.FCStd")
SIZE = (1600, 1200)

# 부품 색상 — 색은 GUI 속성(ViewObject)이라 헤드리스 pen_holder.py 에서는
# 지정할 수 없다. 여기서 칠하고 문서를 저장해 FCStd 에도 남긴다.
SCREW_COLOR = (0.80, 0.11, 0.11)   # 썸스크류: 빨강

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

    # 썸스크류만 빨강 (나열·조립 뷰의 두 인스턴스 모두)
    for o in doc.Objects:
        if "screw" in o.Name.lower():
            o.ViewObject.ShapeColor = SCREW_COLOR
            o.ViewObject.DiffuseColor = [SCREW_COLOR]
            print("색상:", o.Name, "→ 빨강")

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
