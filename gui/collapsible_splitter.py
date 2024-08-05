from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QSplitter, QSplitterHandle
from PyQt5.QtGui import QColor, QPainter
import logger

class CollapsibleSplitterHandle(QSplitterHandle):
    def __init__(self, orientation, parent, handle_thickness, is_bottom_handle=False):
        super().__init__(orientation, parent)
        self.is_bottom_handle = is_bottom_handle
        self.handle_thickness = handle_thickness
        self.setCursor(Qt.PointingHandCursor)
        self.setContentsMargins(0, 0, 0, 0)  # Ensure no margins

    def paintEvent(self, event):
        painter = QPainter(self)
        color = QColor(100, 100, 100)
        painter.fillRect(self.rect(), color)
        logger.debug(f"[CollapsibleSplitterHandle] Handle geometry: {self.geometry()}")

    def sizeHint(self):
        size = super().sizeHint()
        size.setHeight(self.handle_thickness)
        size.setWidth(self.handle_thickness)
        logger.debug(f"[CollapsibleSplitterHandle] Size hint: {size}")
        return size

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
        self.setContentsMargins(0, 0, 0, 0)  # Ensure no margins
        self.setHandleWidth(handle_thickness)  # Explicitly set the handle width

    def setBottomSplitter(self, is_bottom):
        self.is_bottom_splitter = is_bottom

    def createHandle(self):
        return CollapsibleSplitterHandle(self.orientation(), self, self.handle_thickness, self.is_bottom_splitter)

    def handleWidth(self):
        logger.info(f"[CollapsibleSplitter] Handle width: {self.handle_thickness}")
        return self.handle_thickness
