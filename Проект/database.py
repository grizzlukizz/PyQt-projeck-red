"""Сохранение домов, этажей, комнат и мебели в SQLite."""
import os
import sqlite3
import shutil
from pathlib import Path

# Данные хранятся в папке пользователя, а не в распакованном архиве.
# Поэтому обновление программы не создаёт каждый раз новую базу.
folder = Path(__file__).resolve().parent
user_dir = Path(os.environ.get('LOCALAPPDATA') or Path.home()) / 'DomPlan'
old_db = folder / 'doma.db'
try:
    user_dir.mkdir(parents=True, exist_ok=True)
    db_path = str(user_dir / 'doma.db')
    if old_db.exists() and not Path(db_path).exists():
        shutil.copy2(old_db, db_path)  # Старую базу перенесём, если она есть.
except OSError:
    db_path = str(old_db)


def get_rows(sql, a=()):
    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        return [dict(r) for r in db.execute(sql, a)]


def run_sql(sql, a=()):
    with sqlite3.connect(db_path) as db:
        db.execute('PRAGMA foreign_keys=ON')
        cur = db.execute(sql, a)
        return cur.lastrowid


def create_tables():
    with sqlite3.connect(db_path) as db:
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY, name TEXT)')
        db.execute('''CREATE TABLE IF NOT EXISTS floors(
            id INTEGER PRIMARY KEY, project_id INTEGER, name TEXT,
            width REAL, height REAL,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE)''')
        db.execute('''CREATE TABLE IF NOT EXISTS rooms(
            id INTEGER PRIMARY KEY, floor_id INTEGER, name TEXT,
            x REAL, y REAL, w REAL, h REAL, color TEXT,
            FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE)''')
        db.execute('''CREATE TABLE IF NOT EXISTS furniture(
            id INTEGER PRIMARY KEY, floor_id INTEGER, name TEXT,
            x REAL, y REAL, w REAL, h REAL, color TEXT,
            FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE)''')
        # Если в старой базе дом есть, но этажи отсутствуют, добавим первый.
        for (hid,) in db.execute('SELECT id FROM projects').fetchall():
            count = db.execute('SELECT COUNT(*) FROM floors WHERE project_id=?', (hid,)).fetchone()[0]
            if count == 0:
                db.execute('INSERT INTO floors(project_id,name,width,height) VALUES(?,?,?,?)',
                           (hid, 'Первый этаж', 12, 9))
        if db.execute('SELECT COUNT(*) FROM projects').fetchone()[0] == 0:
            # Если список пуст, создаём дом с этажом для примера.
            a = db.execute("INSERT INTO projects(name) VALUES('Мой дом')").lastrowid
            b = db.execute('INSERT INTO floors(project_id,name,width,height) VALUES(?,?,?,?)',
                           (a, 'Первый этаж', 12, 9)).lastrowid
            for name, x, y, w, h, c in [
                ('Гостиная', 0.5, 0.5, 6, 4, '#b9e4ff'),
                ('Спальня', 6.5, 0.5, 5, 4, '#e8cbff'),
                ('Кухня', 0.5, 4.5, 5, 4, '#fff0aa')
            ]:
                db.execute('INSERT INTO rooms(floor_id,name,x,y,w,h,color) VALUES(?,?,?,?,?,?,?)',
                           (b, name, x, y, w, h, c))
            db.execute('''INSERT INTO furniture(floor_id,name,x,y,w,h,color)
                          VALUES(?,?,?,?,?,?,?)''',
                       (b, 'Диван', 2, 2, 2, 1, '#9cbbef'))


def get_houses():
    return get_rows('SELECT * FROM projects ORDER BY id')


def get_floors(item_id):
    return get_rows('SELECT * FROM floors WHERE project_id=? ORDER BY id', (item_id,))


def get_objects(table, item_id):
    if table not in ('rooms', 'furniture'):
        return []
    return get_rows(f'SELECT * FROM {table} WHERE floor_id=? ORDER BY id', (item_id,))


def save_object(table, floor_id, item, item_id=None):
    if table == 'rooms':
        a = (item['name'], item['x'], item['y'], item['w'], item['h'], item['color'])
        if item_id:
            run_sql('UPDATE rooms SET name=?,x=?,y=?,w=?,h=?,color=? WHERE id=?', a + (item_id,))
        else:
            item_id = run_sql('INSERT INTO rooms(floor_id,name,x,y,w,h,color) VALUES(?,?,?,?,?,?,?)',
                       (floor_id,) + a)
    elif table == 'furniture':
        a = (item['name'], item['x'], item['y'], item['w'], item['h'], item['color'])
        if item_id:
            run_sql('UPDATE furniture SET name=?,x=?,y=?,w=?,h=?,color=? WHERE id=?', a + (item_id,))
        else:
            item_id = run_sql('INSERT INTO furniture(floor_id,name,x,y,w,h,color) VALUES(?,?,?,?,?,?,?)',
                              (floor_id,) + a)
    return item_id


def delete_object(table, item_id):
    if table in ('rooms', 'furniture'):
        run_sql(f'DELETE FROM {table} WHERE id=?', (item_id,))
