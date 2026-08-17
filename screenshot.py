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

# 뷰 이름 → (표시할 객체 이름 목록, 카메라 메서드)
VIEWS = [
    ("parts-axo", ["tier1", "module2", "module3", "thumbscrew"],
     "viewAxonometric"),
    ("assembly-axo", ["asm_tier1", "asm_module3", "asm_screw"],
     "viewAxonometric"),
    ("assembly-front", ["asm_tier1", "asm_module3", "asm_screw"],
     "viewFront"),
    ("assembly-right", ["asm_tier1", "asm_module3", "asm_screw"],
     "viewRight"),
]


def shoot():
    doc = App.openDocument(DOC)
    Gui.updateGui()
    Gui.ActiveDocument = Gui.getDocument(doc.Name)
    view = Gui.activeDocument().activeView()
    for name, visible, cam in VIEWS:
        for o in doc.Objects:
            o.ViewObject.Visibility = o.Name in visible
        getattr(view, cam)()
        Gui.SendMsgToActiveView("ViewFit")
        Gui.updateGui()
        path = os.path.join(HERE, "output", "shot-%s.png" % name)
        view.saveImage(path, SIZE[0], SIZE[1], "White")
        print("PNG:", path)
    App.closeDocument(doc.Name)
    Gui.getMainWindow().close()


# GUI 이벤트 루프가 준비된 뒤 실행하고, 끝나면 앱을 종료한다
QtCore.QTimer.singleShot(1200, shoot)
QtCore.QTimer.singleShot(9000, Gui.getMainWindow().close)
