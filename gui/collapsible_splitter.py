from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QSplitter, QSplitterHandle
from PyQt5.QtGui import QColor, QPainter

class CollapsibleSplitterHandle(QSplitterHandle):
    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(5)

    def paintEvent(self, event):
        painter = QPainter(self)
        color = QColor(100, 100, 100)
        painter.fillRect(self.rect(), color)

    def mousePressEvent(self, event):
        splitter = self.splitter()
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
    def createHandle(self):
        return CollapsibleSplitterHandle(self.orientation(), self)
