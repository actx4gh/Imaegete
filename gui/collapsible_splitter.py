from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QSplitter, QSplitterHandle
from PyQt5.QtGui import QColor, QPainter

class CollapsibleSplitterHandle(QSplitterHandle):
    def __init__(self, orientation, parent, handle_thickness, is_bottom_handle=False):
        super().__init__(orientation, parent)
        self.is_bottom_handle = is_bottom_handle
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(handle_thickness)

    def paintEvent(self, event):
        painter = QPainter(self)
        color = QColor(100, 100, 100)
        painter.fillRect(self.rect(), color)

    def mousePressEvent(self, event):
        splitter = self.splitter()
        if self.is_bottom_handle:
            if splitter.widget(1).isVisible():
                splitter.widget(1).setVisible(False)
                splitter.setSizes([1, 0])
            else:
                splitter.widget(1).setVisible(True)
                splitter.setSizes([1, 1])
        else:
            if splitter.widget(0).isVisible():
                splitter.widget(0).setVisible(False)
                splitter.setSizes([0, 1])
            else:
                splitter.widget(0).setVisible(True)
                splitter.setSizes([1, 1])
        self.update()
        super().mousePressEvent(event)

    def hideEvent(self, event):
        self.show()
        super().hideEvent(event)

class CollapsibleSplitter(QSplitter):
    def __init__(self, orientation, handle_thickness, parent=None):
        super().__init__(orientation, parent)
        self.handle_thickness = handle_thickness
        self.is_bottom_splitter = False

    def setBottomSplitter(self, is_bottom):
        self.is_bottom_splitter = is_bottom

    def createHandle(self):
        return CollapsibleSplitterHandle(self.orientation(), self, self.handle_thickness, self.is_bottom_splitter)
