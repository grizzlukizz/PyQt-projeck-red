"""Отображение этажа и перемещение объектов мышью."""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget, QSizePolicy

# На этом поле рисуем комнаты и мебель.
class PlanWidget(QWidget):
    selected_changed = pyqtSignal(str, int)
    object_changed = pyqtSignal(str, int, float, float, float, float)
    zoom_requested = pyqtSignal(int)
    edit_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.floor = None
        self.rooms = []
        self.furniture = []
        self.selected = None
        self.dragging = None
        self.percent = 100
        self.scale = 1.0
        self.margin = 50
        self.setObjectName('floorPlan')
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(220, 220)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet('background:white')

    def load(self, floor, rooms, furniture):
        self.floor, self.rooms, self.furniture = floor, rooms, furniture
        self.update_scale()

    def update_scale(self):
        # Подбираем размер так, чтобы план занимал доступную область.
        if self.floor:
            w = max(1, self.width() - self.margin * 2)
            h = max(1, self.height() - self.margin * 2)
            self.scale = min(w / self.floor['width'],
                             h / self.floor['height']) * self.percent / 100
        else:
            self.scale = 0
        self.update()

    def resizeEvent(self, event):
        self.update_scale()
        super().resizeEvent(event)

    def origin(self):
        if self.floor:
            x = (self.width() - round(self.floor['width'] * self.scale)) // 2
            y = (self.height() - round(self.floor['height'] * self.scale)) // 2
            return x, y
        return self.margin, self.margin

    def zoom(self, val):
        self.percent = max(0, min(100, val))
        self.update_scale()

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor('#ffffff'))
        if not self.floor:
            p.setPen(QColor('#64748b'))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       'Выберите этаж в списке слева')
            return

        s = self.scale
        if s == 0:
            p.setPen(QColor('#64748b'))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       'Масштаб 0%. Нажмите «+» слева.')
            return
        mx, my = self.origin()
        w = round(self.floor['width'] * s)
        h = round(self.floor['height'] * s)
        p.setBrush(QColor('white'))
        p.setPen(QPen(QColor('#334155'), 2))
        p.drawRect(mx, my, w, h)

        # Сетка показывается всегда, без отдельного переключателя.
        # При сильном уменьшении шаг увеличивается, чтобы линии не сливались.
        step = 1 if s >= 9 else 2 if s >= 4 else 5 if s >= 2 else 10
        p.save()
        p.setClipRect(mx, my, w, h)
        p.setPen(QPen(QColor('#dce7f4'), 1))
        for i in range(1, int(self.floor['width'] // step) + 1):
            x = round(mx + i * step * s)
            if x < mx + w:
                p.drawLine(x, my, x, my + h)
        for i in range(1, int(self.floor['height'] // step) + 1):
            y = round(my + i * step * s)
            if y < my + h:
                p.drawLine(mx, y, mx + w, y)
        p.restore()

        # Подписи метров вокруг плана.
        p.setPen(QColor('#64748b'))
        label_step = 1 if s >= 40 else 5 if s >= 12 else 10
        for x in range(0, int(self.floor['width']) + 1, label_step):
            p.drawText(round(mx + x * s) - 12, my - 21, 30, 16,
                       Qt.AlignmentFlag.AlignCenter, str(x))
        for y in range(0, int(self.floor['height']) + 1, label_step):
            p.drawText(mx - 38, round(my + y * s) - 8, 30, 17,
                       Qt.AlignmentFlag.AlignRight, str(y))

        # Комнаты рисуем первыми, мебель — поверх них.
        for table, data in [('rooms', self.rooms), ('furniture', self.furniture)]:
            for obj in data:
                x = round(mx + obj['x'] * s)
                y = round(my + obj['y'] * s)
                a = round(obj['w'] * s)
                b = round(obj['h'] * s)
                chosen = self.selected == (table, obj['id'])
                p.setPen(QPen(QColor('#f97316' if chosen else '#475569'), 3 if chosen else 1))
                p.setBrush(QColor(obj['color']))
                p.drawRect(x, y, a, b)
                if a >= 48 and b >= 25:
                    p.setPen(QColor('#20344e'))
                    p.drawText(x + 4, y + 3, a - 8, b - 6,
                               Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                               obj['name'])

    def mousePressEvent(self, event):
        if not self.floor or self.scale == 0 or event.button() != Qt.MouseButton.LeftButton:
            return
        self.setFocus()
        mx, my = self.origin()
        px, py = event.position().x(), event.position().y()
        x = (px - mx) / self.scale
        y = (py - my) / self.scale
        self.dragging = None
        self.selected = None
        for table, data in [('furniture', self.furniture), ('rooms', self.rooms)]:
            for obj in reversed(data):
                if obj['x'] <= x <= obj['x'] + obj['w'] and obj['y'] <= y <= obj['y'] + obj['h']:
                    # Предмет можно двигать, а размер меняется через окно изменения.
                    old = (obj['x'], obj['y'], obj['w'], obj['h'])
                    self.dragging = (table, obj, x - obj['x'], y - obj['y'], old)
                    self.selected = (table, obj['id'])
                    break
            if self.dragging:
                break
        if self.selected:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.selected_changed.emit(*self.selected)
        else:
            self.selected_changed.emit('', 0)
        self.update()

    def mouseMoveEvent(self, event):
        if not self.dragging or self.scale == 0:
            return
        table, obj, dx, dy, old = self.dragging
        mx, my = self.origin()
        x = (event.position().x() - mx) / self.scale
        y = (event.position().y() - my) / self.scale
        # Перемещение с шагом 0.5 м, без изменения размера мышью.
        obj['x'] = max(0, min(round((x - dx) * 2) / 2,
                              self.floor['width'] - obj['w']))
        obj['y'] = max(0, min(round((y - dy) * 2) / 2,
                              self.floor['height'] - obj['h']))
        self.update()

    def mouseReleaseEvent(self, event):
        self.unsetCursor()
        if not self.dragging:
            return
        table, obj, dx, dy, old = self.dragging
        self.dragging = None
        if old != (obj['x'], obj['y'], obj['w'], obj['h']):
            self.object_changed.emit(table, obj['id'], obj['x'], obj['y'],
                                     obj['w'], obj['h'])

    def mouseDoubleClickEvent(self, event):
        if self.selected:
            self.edit_requested.emit()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom_requested.emit(5 if event.angleDelta().y() > 0 else -5)
            event.accept()
        else:
            event.ignore()
