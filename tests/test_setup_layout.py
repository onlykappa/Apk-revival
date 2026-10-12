"""Regression for overlapping Setup controls at Deck-sized viewports."""
import os,pathlib,tempfile,unittest

@unittest.skipUnless(os.getenv('QT_QPA_PLATFORM')=='offscreen','Qt offscreen layout checks')
class SetupLayoutTests(unittest.TestCase):
    def test_controls_do_not_overlap_and_focus_scrolls(self):
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QApplication,QPushButton,QComboBox,QLineEdit
        from apk_revival.launcher.ui import Window
        from apk_revival.launcher.style import STYLE
        from apk_revival.store import Store
        app=QApplication.instance() or QApplication([]);app.setStyleSheet(STYLE)
        for size in [(1280,800),(1000,650)]:
            with self.subTest(size=size),tempfile.TemporaryDirectory() as temp:
                w=Window(Store(pathlib.Path(temp)));w.resize(*size);w.show();app.processEvents();w.updates_button.click();app.processEvents();self.assertIs(w.stack.currentWidget(),w.setup);w.setup_scroll.verticalScrollBar().setValue(0);app.processEvents()
                content=w.setup_scroll.widget();controls=content.findChildren(QPushButton)+content.findChildren(QComboBox)+content.findChildren(QLineEdit)
                rectangles=[]
                for widget in controls:
                    self.assertGreaterEqual(widget.height(),40)
                    rect=widget.rect();rect.moveTopLeft(widget.mapTo(content,QPoint(0,0)));rectangles.append(rect)
                for index,rect in enumerate(rectangles):
                    for other in rectangles[index+1:]:self.assertFalse(rect.intersects(other),'Setup controls overlap')
                self.assertGreater(w.setup_scroll.verticalScrollBar().maximum(),0)
                last=next(b for b in controls if isinstance(b,QPushButton) and b.text()=='Add to Steam');last.setFocus();app.processEvents()
                self.assertGreater(w.setup_scroll.verticalScrollBar().value(),0)
                mapped=last.mapTo(w.setup_scroll.viewport(),QPoint(0,0));self.assertGreaterEqual(mapped.y(),0);self.assertLessEqual(mapped.y()+last.height(),w.setup_scroll.viewport().height())
                w.close();app.processEvents()
