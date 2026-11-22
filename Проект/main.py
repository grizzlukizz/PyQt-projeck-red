"""Главное окно планировщика и окна добавления объектов."""
import sys
import sqlite3
import colorsys
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap, QColor, QKeySequence, QShortcut, QPalette
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QFrame, QMessageBox, QInputDialog, QFileDialog, QMenu,
    QTreeWidget, QTreeWidgetItem, QDialog, QFormLayout, QLineEdit,
    QDoubleSpinBox, QDialogButtonBox, QGridLayout
)
from database import (db_path, create_tables, get_rows, run_sql, get_houses,
                      get_floors, get_objects, save_object, delete_object)
from plan import PlanWidget

class FloorDialog(QDialog):
    def __init__(self, parent=None, item=None):
        super().__init__(parent)
        self.setWindowTitle('Этаж')
        self.setMinimumWidth(310)
        box = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(item['name'] if item else 'Новый этаж')
        self.w, self.h = QDoubleSpinBox(), QDoubleSpinBox()
        for spin, key, val in [(self.w, 'width', 12), (self.h, 'height', 9)]:
            spin.setRange(3, 100)
            spin.setValue(item[key] if item else val)
            spin.setSuffix(' м')
        form.addRow('Название:', self.name)
        form.addRow('Ширина:', self.w)
        form.addRow('Длина:', self.h)
        box.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.check)
        buttons.rejected.connect(self.reject)
        box.addWidget(buttons)

    def check(self):
        if self.name.text().strip():
            self.accept()
        else:
            QMessageBox.warning(self, 'Ошибка', 'Введите название')

    def result_data(self):
        return self.name.text().strip(), self.w.value(), self.h.value()


def palette_100():
    # Десять оттенков серого и девяносто цветных оттенков.
    colors = [f'#{v:02x}{v:02x}{v:02x}' for v in (255, 232, 210, 188, 166, 144, 112, 80, 48, 20)]
    for sat, val in [(65, 255), (105, 255), (145, 255), (185, 255),
                     (225, 255), (245, 235), (245, 205), (215, 175), (185, 145)]:
        for hue in range(10):
            r, g, b = colorsys.hsv_to_rgb(hue / 10, sat / 255, val / 255)
            colors.append(f'#{round(r * 255):02x}{round(g * 255):02x}{round(b * 255):02x}')
    return colors


class ColorsDialog(QDialog):
    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.setWindowTitle('100 цветов')
        self.color = color
        self.setFixedWidth(405)
        box = QVBoxLayout(self)
        box.setSpacing(10)
        grid = QGridLayout()
        grid.setSpacing(4)
        for i, col in enumerate(palette_100()):
            btn = QPushButton()
            btn.setFixedSize(32, 32)
            btn.setToolTip(col)
            border = '3px solid #ff8a00' if col == color else '1px solid #9aaec2'
            btn.setStyleSheet(f'QPushButton {{background:{col}; border:{border}; padding:0; border-radius:0}}')
            btn.clicked.connect(lambda checked=False, c=col: self.pick(c))
            grid.addWidget(btn, i // 10, i % 10)
        box.addLayout(grid)
        cancel = QPushButton('Отмена')
        cancel.clicked.connect(self.reject)
        box.addWidget(cancel)

    def pick(self, color):
        self.color = color
        self.accept()


class ObjectDialog(QDialog):
    def __init__(self, table, floor, parent=None, item=None):
        super().__init__(parent)
        self.floor = floor
        self.setWindowTitle('Комната' if table == 'rooms' else 'Мебель')
        self.setMinimumWidth(320)
        self.color = item['color'] if item else ('#cbeaff' if table == 'rooms' else '#e1d1b9')
        box = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(item['name'] if item else ('Новая комната' if table == 'rooms' else 'Мебель'))
        form.addRow('Название:', self.name)
        for key, title, value in [('x', 'X:', 0.5), ('y', 'Y:', 0.5),
                                  ('w', 'Ширина:', 4 if table == 'rooms' else 1),
                                  ('h', 'Длина:', 3 if table == 'rooms' else 1)]:
            spin = QDoubleSpinBox()
            spin.setRange(0.5 if key in ('w', 'h') else 0, 100)
            spin.setSingleStep(0.5)
            spin.setSuffix(' м')
            spin.setValue(item[key] if item else value)
            setattr(self, key, spin)
            form.addRow(title, spin)
        self.color_button = QPushButton('Цвет')
        self.color_button.clicked.connect(self.choose_color)
        self.update_color()
        form.addRow('Цвет:', self.color_button)
        box.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.check)
        buttons.rejected.connect(self.reject)
        box.addWidget(buttons)

    def update_color(self):
        # Показываем выбранный оттенок прямо на кнопке.
        c = QColor(self.color)
        text = '#ffffff' if c.lightness() < 130 else '#203450'
        self.color_button.setStyleSheet(f'background:{self.color};color:{text};border:1px solid #9aaec2')
        self.color_button.setText('Выбрать из 100 цветов')

    def choose_color(self):
        dlg = ColorsDialog(self.color, self)
        if dlg.exec():
            self.color = dlg.color
            self.update_color()

    def check(self):
        if not self.name.text().strip():
            QMessageBox.warning(self, 'Ошибка', 'Введите название')
        elif self.x.value() + self.w.value() > self.floor['width'] or \
             self.y.value() + self.h.value() > self.floor['height']:
            QMessageBox.warning(self, 'Ошибка', 'Объект не помещается на этаже')
        else:
            self.accept()

    def result_data(self):
        data = {k: getattr(self, k).value() for k in ('x', 'y', 'w', 'h')}
        data.update(name=self.name.text().strip(), color=self.color)
        return data


# Главное окно: кнопки слева, рабочая область занимает всё остальное.
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Планировщик домов')
        self.resize(1140, 730)
        self.setMinimumSize(780, 540)
        self.house_id = None
        self.floor = None
        self.selected = None
        # Явные цвета, чтобы Windows в тёмной теме не окрашивала панели в чёрный.
        self.setStyleSheet('''
            QMainWindow, QWidget#main, QFrame#panel {
                background-color:#f0f5fb; color:#203450;
            }
            QLabel {background-color:transparent; color:#203450; font-size:13px}
            QPushButton {
                background-color:#ffffff; color:#203450;
                padding:10px; border:1px solid #bdd0e5; border-radius:0;
            }
            QPushButton:hover {background-color:#dbeafe}
            QPushButton:disabled {background-color:#e8edf5; color:#8694a8}
            QTreeWidget {
                background-color:#ffffff; color:#203450;
                border:1px solid #bdd0e5; border-radius:0;
                selection-background-color:#cbe4ff; selection-color:#102b45;
                font-size:14px;
            }
            QTreeWidget::item {padding:10px 6px; color:#203450;}
            QTreeWidget::item:selected {background-color:#cbe4ff; color:#102b45}
            QScrollBar:vertical {background:#edf3fa; width:10px}
            QScrollBar::handle:vertical {background:#bbcee2; min-height:20px}
            QMenu {background:#ffffff; color:#203450; border:1px solid #bdd0e5;}
            QMenu::item {padding:8px 18px; background:#ffffff; color:#203450;}
            QMenu::item:selected {background:#dbeafe;}
            QLineEdit, QDoubleSpinBox {
                border:1px solid #bdd0e5; border-radius:0;
                padding:5px; background-color:white; color:#203450;
            }
        ''')

        base = QWidget()
        base.setObjectName('main')
        base.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        root = QVBoxLayout(base)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)
        self.setCentralWidget(base)

        body = QHBoxLayout()
        body.setSpacing(14)
        root.addLayout(body, 1)

        # Слева компактное дерево домов и этажей.
        sidebar = QFrame()
        sidebar.setObjectName('panel')
        sidebar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        sidebar.setFixedWidth(292)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(8, 8, 8, 8)
        side.setSpacing(10)
        title = QLabel('Дома и этажи')
        title.setStyleSheet('font-weight:600; color:#203450; background:transparent;')
        side.addWidget(title)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setColumnCount(1)
        # Стрелка у дома позволяет скрывать и показывать его этажи.
        self.tree.setRootIsDecorated(True)
        self.tree.setItemsExpandable(True)
        self.tree.setExpandsOnDoubleClick(True)
        self.tree.setIndentation(18)
        self.tree.setAlternatingRowColors(False)
        # Список занимает всё свободное место до кнопок внизу.
        self.tree.setMinimumHeight(150)
        self.tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        side.addWidget(self.tree, 1)

        controls = QWidget()
        left = QVBoxLayout(controls)
        left.setContentsMargins(2, 2, 2, 2)
        left.setSpacing(10)
        self.b_house = self.button('+ Дом', self.add_house, 'primary')
        self.b_floor = self.button('+ Этаж', self.add_floor)
        line = QHBoxLayout()
        line.addWidget(self.b_house)
        line.addWidget(self.b_floor)
        line.setSpacing(8)
        left.addLayout(line)
        self.b_room = self.button('+ Комната', lambda: self.add_object('rooms'), 'primary')
        self.b_furn = self.button('+ Мебель', lambda: self.add_object('furniture'))
        line = QHBoxLayout()
        line.addWidget(self.b_room)
        line.addWidget(self.b_furn)
        line.setSpacing(8)
        left.addLayout(line)

        # Одна кнопка вместо отдельных «Изменить» и «Удалить».
        self.b_actions = QPushButton('Изменить / удалить')
        menu = QMenu(self.b_actions)
        menu.addAction('Изменить выбранное', self.edit_chosen)
        menu.addAction('Удалить выбранное', self.delete_chosen)
        self.b_actions.setMenu(menu)
        left.addWidget(self.b_actions)

        self.b_png = self.button('Сохранить PNG', self.save_png)
        left.addWidget(self.b_png)

        # Масштаб без ползунка: только кнопки и процент.
        self.zoom_value = 100
        self.zoom_text = QLabel('100%')
        self.zoom_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        minus = self.button('−', lambda: self.change_zoom(-5))
        plus = self.button('+', lambda: self.change_zoom(5))
        line = QHBoxLayout()
        line.addWidget(minus)
        line.addWidget(self.zoom_text, 1)
        line.addWidget(plus)
        left.addLayout(line)

        # Блок кнопок закреплён внизу, дерево растягивается над ним.
        side.addWidget(controls)
        body.addWidget(sidebar)

        # Справа план автоматически занимает всё свободное место.
        self.canvas = PlanWidget()
        self.canvas.selected_changed.connect(self.select_on_plan)
        self.canvas.object_changed.connect(self.save_object_on_plan)
        self.canvas.zoom_requested.connect(self.change_zoom)
        self.canvas.edit_requested.connect(self.edit_object)
        body.addWidget(self.canvas, 1)

        self.tree.currentItemChanged.connect(lambda *_: self.show_objects())
        QShortcut(QKeySequence('Ctrl+S'), self, activated=self.save_png)
        QShortcut(QKeySequence('Delete'), self, activated=self.remove_object)
        try:
            self.show_houses()
        except sqlite3.Error as err:
            QMessageBox.critical(self, 'Ошибка базы данных',
                                 f'Не удалось загрузить дома и этажи: {err}\nБаза: {db_path}')

    def button(self, text, action, style=None):
        b = QPushButton(text)
        if style:
            b.setObjectName(style)
        b.clicked.connect(action)
        return b

    def show_houses(self, house_id=None, floor_id=None):
        # Перечитываем список из базы после любого изменения.
        # Запомним, какие дома пользователь свернул.
        opened = {}
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data:
                opened[data[1]] = item.isExpanded()
        self.tree.blockSignals(True)
        self.tree.clear()
        chosen = None
        first_floor = None
        try:
            houses = get_houses()
            for house in houses:
                h = QTreeWidgetItem(self.tree, [house['name'] or 'Без названия'])
                h.setData(0, Qt.ItemDataRole.UserRole, ('house', house['id']))
                if house['id'] == house_id and floor_id is None:
                    chosen = h
                for floor in get_floors(house['id']):
                    f = QTreeWidgetItem(h, [floor['name'] or 'Этаж'])
                    f.setData(0, Qt.ItemDataRole.UserRole, ('floor', floor['id']))
                    if first_floor is None:
                        first_floor = f
                    if floor['id'] == floor_id:
                        chosen = f
                h.setExpanded(opened.get(house['id'], True))
            # Дом может быть выбран, но его первый этаж всё равно откроется справа.
            self.tree.setCurrentItem(chosen or first_floor)
        finally:
            self.tree.blockSignals(False)
        self.show_objects()

    def current_floor(self):
        row = self.tree.currentItem()
        if not row:
            return None, None
        kind, ident = row.data(0, Qt.ItemDataRole.UserRole)
        if kind == 'house':
            floors = get_floors(ident)
            return ident, floors[0] if floors else None
        floors = get_rows('SELECT * FROM floors WHERE id=?', (ident,))
        if floors:
            return floors[0]['project_id'], floors[0]
        return None, None

    def show_objects(self, chosen=None):
        self.house_id, self.floor = self.current_floor()
        rooms = get_objects('rooms', self.floor['id']) if self.floor else []
        furniture = get_objects('furniture', self.floor['id']) if self.floor else []
        self.selected = chosen
        self.canvas.selected = chosen
        self.canvas.load(self.floor, rooms, furniture)
        self.update_buttons()

    def update_buttons(self):
        have_house = bool(self.house_id)
        have_floor = bool(self.floor)
        self.b_floor.setEnabled(have_house)
        self.b_actions.setEnabled(have_house or bool(self.selected))
        for b in (self.b_room, self.b_furn, self.b_png):
            b.setEnabled(have_floor)

    def edit_chosen(self):
        if self.selected:
            self.edit_object()
        else:
            self.change_selected()

    def delete_chosen(self):
        if self.selected:
            self.remove_object()
        else:
            self.delete_selected()

    def confirm(self, text):
        return QMessageBox.question(self, 'Удаление', text) == QMessageBox.StandardButton.Yes

    def add_house(self):
        name, ok = QInputDialog.getText(self, 'Новый дом', 'Название дома:')
        if ok and name.strip():
            ident = run_sql('INSERT INTO projects(name) VALUES(?)', (name.strip(),))
            fid = run_sql('INSERT INTO floors(project_id,name,width,height) VALUES(?,?,?,?)',
                          (ident, 'Первый этаж', 12, 9))
            self.show_houses(ident, fid)

    def add_floor(self):
        if not self.house_id:
            return
        dlg = FloorDialog(self)
        if dlg.exec():
            name, w, h = dlg.result_data()
            ident = run_sql('INSERT INTO floors(project_id,name,width,height) VALUES(?,?,?,?)',
                            (self.house_id, name, w, h))
            self.show_houses(self.house_id, ident)

    def change_selected(self):
        if not self.house_id:
            return
        row = self.tree.currentItem()
        typ = row.data(0, Qt.ItemDataRole.UserRole)[0] if row else ''
        if typ == 'house':
            old = get_rows('SELECT name FROM projects WHERE id=?', (self.house_id,))[0]['name']
            name, ok = QInputDialog.getText(self, 'Дом', 'Новое название:', text=old)
            if ok and name.strip():
                run_sql('UPDATE projects SET name=? WHERE id=?', (name.strip(), self.house_id))
                self.show_houses(self.house_id)
            return
        dlg = FloorDialog(self, self.floor)
        if dlg.exec():
            name, w, h = dlg.result_data()
            objects = get_objects('rooms', self.floor['id']) + get_objects('furniture', self.floor['id'])
            if any(o['x'] + o['w'] > w or o['y'] + o['h'] > h for o in objects):
                QMessageBox.warning(self, 'Этаж', 'Объекты не помещаются в новые размеры.')
                return
            run_sql('UPDATE floors SET name=?,width=?,height=? WHERE id=?',
                    (name, w, h, self.floor['id']))
            self.show_houses(self.house_id, self.floor['id'])

    def delete_selected(self):
        if not self.house_id:
            return
        row = self.tree.currentItem()
        typ = row.data(0, Qt.ItemDataRole.UserRole)[0] if row else ''
        if typ == 'house':
            if self.confirm('Удалить дом со всеми этажами?'):
                run_sql('DELETE FROM projects WHERE id=?', (self.house_id,))
                self.show_houses()
        elif self.floor and self.confirm('Удалить этаж вместе со всеми комнатами и мебелью?'):
            ident = self.house_id
            run_sql('DELETE FROM floors WHERE id=?', (self.floor['id'],))
            self.show_houses(ident)

    def room_overlaps(self, obj, skip=None):
        # Проверяем пересечения, чтобы комнаты не накладывались друг на друга.
        for room in get_objects('rooms', self.floor['id']):
            if room['id'] == skip:
                continue
            if obj['x'] < room['x'] + room['w'] and obj['x'] + obj['w'] > room['x'] and \
               obj['y'] < room['y'] + room['h'] and obj['y'] + obj['h'] > room['y']:
                return True
        return False

    def add_object(self, table):
        if not self.floor:
            return
        dlg = ObjectDialog(table, self.floor, self)
        if dlg.exec():
            obj = dlg.result_data()
            if table == 'rooms' and self.room_overlaps(obj):
                QMessageBox.warning(self, 'Комната', 'Здесь уже находится другая комната.')
                return
            ident = save_object(table, self.floor['id'], obj)
            self.show_objects((table, ident))

    def edit_object(self):
        if not self.floor or not self.selected:
            return
        table, ident = self.selected
        old = next((o for o in get_objects(table, self.floor['id']) if o['id'] == ident), None)
        if not old:
            return
        dlg = ObjectDialog(table, self.floor, self, old)
        if dlg.exec():
            obj = dlg.result_data()
            if table == 'rooms' and self.room_overlaps(obj, ident):
                QMessageBox.warning(self, 'Комната', 'Комнаты не должны пересекаться.')
                return
            save_object(table, self.floor['id'], obj, ident)
            self.show_objects((table, ident))

    def remove_object(self):
        if self.selected and self.confirm('Удалить выбранный объект?'):
            table, ident = self.selected
            delete_object(table, ident)
            self.show_objects()

    def select_on_plan(self, table, ident):
        self.selected = (table, ident) if table and ident else None
        self.canvas.selected = self.selected
        self.update_buttons()
        self.canvas.update()

    def save_object_on_plan(self, table, ident, x, y, w, h):
        # После перемещения сохраняем координаты в базе.
        if table not in ('rooms', 'furniture') or not self.floor:
            return
        if table == 'rooms':
            obj = {'x': x, 'y': y, 'w': w, 'h': h}
            if self.room_overlaps(obj, ident):
                self.show_objects((table, ident))  # Вернём старые размеры и положение.
                QMessageBox.information(self, 'Комната', 'Комнаты не должны пересекаться.')
                return
        run_sql(f'UPDATE {table} SET x=?,y=?,w=?,h=? WHERE id=?', (x, y, w, h, ident))
        self.show_objects((table, ident))

    def change_zoom(self, step):
        self.zoom(max(0, min(100, self.zoom_value + step)))

    def zoom(self, value):
        # 100%: этаж помещается целиком в доступное окно.
        self.zoom_value = value
        self.canvas.zoom(value)
        self.zoom_text.setText(f'{value}%')

    def save_png(self):
        if not self.floor:
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Сохранить план', 'plan.png', 'PNG (*.png)')
        if not path:
            return
        if not path.lower().endswith('.png'):
            path += '.png'
        # Экспорт рисуем отдельно, не меняя масштаб на экране.
        fw = self.floor['width']
        fh = self.floor['height']
        longest = max(fw, fh)
        pw = max(220, round(1500 * fw / longest) + 100)
        ph = max(220, round(1500 * fh / longest) + 100)
        copy = PlanWidget()
        copy.resize(pw, ph)
        copy.load(self.floor, self.canvas.rooms, self.canvas.furniture)
        copy.zoom(100)
        pic = QPixmap(pw, ph)
        pic.fill(QColor('white'))
        copy.render(pic)
        if not pic.save(path, 'PNG'):
            QMessageBox.warning(self, 'PNG', 'Не удалось сохранить изображение.')



def run():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor('#f0f5fb'))
    pal.setColor(QPalette.ColorRole.WindowText, QColor('#203450'))
    pal.setColor(QPalette.ColorRole.Base, QColor('#ffffff'))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor('#f4f7fc'))
    pal.setColor(QPalette.ColorRole.Text, QColor('#203450'))
    pal.setColor(QPalette.ColorRole.Button, QColor('#ffffff'))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor('#203450'))
    pal.setColor(QPalette.ColorRole.Highlight, QColor('#cbe4ff'))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor('#102b45'))
    app.setPalette(pal)
    app.setStyleSheet('''
        QDialog, QMessageBox, QInputDialog {background:#f0f5fb}
        QDialog QPushButton, QMessageBox QPushButton, QInputDialog QPushButton {
            background:white; color:#203450; border:1px solid #bdd0e5;
            border-radius:0; padding:6px 12px}
        QDialog QLineEdit, QDialog QDoubleSpinBox {
            background:white; color:#203450; border:1px solid #bdd0e5;
            border-radius:0; padding:5px}
    ''')
    try:
        create_tables()
    except sqlite3.Error as err:
        QMessageBox.critical(None, 'Ошибка базы данных',
                             f'Не удалось открыть базу данных:\n{err}\n{db_path}')
        return
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    app.setWindowIcon(QIcon(str(base / 'flag_ru.png')))
    win = MainWindow()
    win.setWindowIcon(QIcon(str(base / 'flag_ru.png')))
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    run()
