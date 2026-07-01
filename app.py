from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from functools import wraps
import json
import sys
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'

# ---------- НАСТРОЙКА БАЗЫ ДАННЫХ ----------
if '--production' in sys.argv:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://reestr_user:uQCasRd#ZRQO@localhost/reestr_db'
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 10,
        'max_overflow': 20,
        'pool_pre_ping': True,
        'pool_recycle': 3600,
        'connect_args': {
            'connect_timeout': 10,
            'keepalives': 1,
            'keepalives_idle': 30,
            'keepalives_interval': 10,
            'keepalives_count': 5,
        }
    }
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///reestr.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------- МОДЕЛИ БАЗЫ ДАННЫХ ----------
class Shipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20), nullable=False)
    time = db.Column(db.String(10), default='')
    contractor = db.Column(db.String(200), default='')
    address = db.Column(db.String(300), default='')
    mark = db.Column(db.String(200), default='')
    volume = db.Column(db.Float, default=0.0)
    contact = db.Column(db.String(100), default='')
    phone = db.Column(db.String(50), default='')
    shipped = db.Column(db.String(10), default='НЕТ')
    payment = db.Column(db.String(50), default='')

class Contractor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    addresses = db.Column(db.Text, default='[]')

class Mark(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='user')

# ---------- СОЗДАНИЕ ТАБЛИЦ И НАЧАЛЬНЫХ ДАННЫХ ----------
with app.app_context():
    db.create_all()
    
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password='admin123', role='admin')
        db.session.add(admin)
    
    if not User.query.filter_by(username='user').first():
        user = User(username='user', password='user123', role='user')
        db.session.add(user)
    
    if not User.query.filter_by(username='editor').first():
        editor = User(username='editor', password='editor123', role='editor')
        db.session.add(editor)
    
    if not User.query.filter_by(username='manager').first():
        manager = User(username='manager', password='hMeaW*', role='admin')
        db.session.add(manager)
    
    if Mark.query.count() == 0:
        default_marks = [
            "Бетон В7,5 (М100) на ПГС",
            "Бетон В12,5 (М150) на ПГС",
            "Бетон В15 (М200) на ПГС",
            "Бетон В20 (М250) на ПГС",
            "Бетон В7,5 (М100) на щебне",
            "Бетон В12,5 (М150) на щебне",
            "Бетон В15 (М200) на щебне",
            "Бетон В20 (М250) на щебне",
            "Бетон В22,5 (М300) на щебне",
            "Бетон В25 (М350) на щебне",
            "Бетон В30 (М400) на щебне",
            "Бетон В35 (М450) на щебне",
            "Раствор цементный М100",
            "Раствор цементный М150",
            "Раствор цементный М200"
        ]
        for mark_name in default_marks:
            mark = Mark(name=mark_name)
            db.session.add(mark)
    
    if Contractor.query.count() == 0:
        default_contractors = {
            "ООО СтройМаркет": ["ул. Ленина, 15", "ул. Строителей, 8"],
            "ИП Петров А.А.": ["пр. Мира, 7"],
            "АО Завод ЖБИ": ["ул. Строителей, 3", "ш. Южное, 22"],
            "ООО ДорСнаб": ["ш. Южное, 22", "ул. Промышленная, 5"],
            "ЗАО Монолит": ["пер. Речной, 8"]
        }
        for name, addresses in default_contractors.items():
            contractor = Contractor(
                name=name,
                addresses=json.dumps(addresses)
            )
            db.session.add(contractor)
    
    db.session.commit()

# ---------- АВТОРИЗАЦИЯ ----------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ---------- МАРШРУТЫ ----------
@app.route('/')
def index():
    if 'user' in session:
        return render_template('index.html', user=session['user'], role=session.get('role', 'user'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user'] = user.username
            session['role'] = user.role
            return redirect(url_for('index'))
        return render_template('login.html', error='Неверный логин или пароль')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ---------- УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ (ТОЛЬКО ДЛЯ ADMIN) ----------
@app.route('/users')
@login_required
def users_page():
    if session.get('role') != 'admin':
        return redirect(url_for('index'))
    return render_template('users.html', user=session['user'])

@app.route('/api/admin/users', methods=['GET'])
@login_required
def get_users():
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Доступ запрещён'}), 403
    
    users = User.query.all()
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'role': u.role
    } for u in users])

@app.route('/api/admin/users', methods=['POST'])
@login_required
def create_user():
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Доступ запрещён'}), 403
    
    data = request.json
    username = data.get('username')
    password = data.get('password')
    role = data.get('role', 'user')
    
    if not username or not password:
        return jsonify({'status': 'error', 'message': 'Логин и пароль обязательны'}), 400
    
    if User.query.filter_by(username=username).first():
        return jsonify({'status': 'error', 'message': 'Пользователь уже существует'}), 400
    
    new_user = User(username=username, password=password, role=role)
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({'status': 'ok', 'message': f'Пользователь {username} создан'})

@app.route('/api/admin/users/<int:user_id>', methods=['PUT'])
@login_required
def update_user(user_id):
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Доступ запрещён'}), 403
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'status': 'error', 'message': 'Пользователь не найден'}), 404
    
    data = request.json
    if 'username' in data:
        user.username = data['username']
    if 'password' in data and data['password']:
        user.password = data['password']
    if 'role' in data:
        user.role = data['role']
    
    db.session.commit()
    return jsonify({'status': 'ok', 'message': 'Пользователь обновлён'})

@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@login_required
def delete_user(user_id):
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Доступ запрещён'}), 403
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'status': 'error', 'message': 'Пользователь не найден'}), 404
    
    if user.username == session['user']:
        return jsonify({'status': 'error', 'message': 'Нельзя удалить самого себя'}), 400
    
    db.session.delete(user)
    db.session.commit()
    return jsonify({'status': 'ok', 'message': f'Пользователь {user.username} удалён'})

# ---------- API ----------
@app.route('/api/shipments', methods=['GET'])
@login_required
def get_shipments():
    shipments = Shipment.query.order_by(Shipment.id).all()
    return jsonify([{
        'id': s.id,
        'date': s.date,
        'time': s.time,
        'contractor': s.contractor,
        'address': s.address,
        'mark': s.mark,
        'volume': s.volume,
        'contact': s.contact,
        'phone': s.phone,
        'shipped': s.shipped,
        'payment': s.payment
    } for s in shipments])

@app.route('/api/shipments', methods=['POST'])
@login_required
def save_shipments():
    role = session.get('role', 'user')
    
    if role not in ['admin', 'editor']:
        return jsonify({'status': 'error', 'message': 'У вас нет прав на редактирование'}), 403
    
    data = request.json
    Shipment.query.delete()
    for item in data:
        shipment = Shipment(
            date=item.get('date', ''),
            time=item.get('time', ''),
            contractor=item.get('contractor', ''),
            address=item.get('address', ''),
            mark=item.get('mark', ''),
            volume=float(item.get('volume', 0)),
            contact=item.get('contact', ''),
            phone=item.get('phone', ''),
            shipped=item.get('shipped', 'НЕТ'),
            payment=item.get('payment', '')
        )
        db.session.add(shipment)
    db.session.commit()
    return jsonify({'status': 'ok', 'message': 'Данные сохранены'})

@app.route('/api/shipments/delete/<int:index>', methods=['DELETE'])
@login_required
def delete_shipment(index):
    role = session.get('role', 'user')
    
    if role not in ['admin', 'editor']:
        return jsonify({'status': 'error', 'message': 'У вас нет прав на удаление записей'}), 403
    
    shipments = Shipment.query.order_by(Shipment.id).all()
    if 0 <= index < len(shipments):
        shipment = shipments[index]
        db.session.delete(shipment)
        db.session.commit()
        return jsonify({'status': 'ok', 'message': 'Запись удалена'})
    return jsonify({'status': 'error', 'message': 'Запись не найдена'}), 404

@app.route('/api/contractors', methods=['GET'])
@login_required
def get_contractors():
    contractors = Contractor.query.all()
    result = {}
    for c in contractors:
        result[c.name] = json.loads(c.addresses)
    return jsonify(result)

@app.route('/api/contractors', methods=['POST'])
@login_required
def save_contractors_route():
    role = session.get('role', 'user')
    
    if role not in ['admin', 'editor']:
        return jsonify({'status': 'error', 'message': 'У вас нет прав на редактирование'}), 403
    
    data = request.json
    Contractor.query.delete()
    for name, addresses in data.items():
        contractor = Contractor(
            name=name,
            addresses=json.dumps(addresses)
        )
        db.session.add(contractor)
    db.session.commit()
    return jsonify({'status': 'ok', 'message': 'Контрагенты сохранены'})

@app.route('/api/marks', methods=['GET'])
@login_required
def get_marks():
    marks = Mark.query.order_by(Mark.id).all()
    return jsonify([m.name for m in marks])

@app.route('/api/marks', methods=['POST'])
@login_required
def save_marks_route():
    role = session.get('role', 'user')
    
    if role not in ['admin', 'editor']:
        return jsonify({'status': 'error', 'message': 'У вас нет прав на редактирование'}), 403
    
    data = request.json
    Mark.query.delete()
    for name in data:
        mark = Mark(name=name)
        db.session.add(mark)
    db.session.commit()
    return jsonify({'status': 'ok', 'message': 'Марки сохранены'})

@app.route('/api/change-password', methods=['POST'])
@login_required
def change_password():
    data = request.json
    username = data.get('username')
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'status': 'error', 'message': 'Пользователь не найден'}), 404
    if user.password != current_password:
        return jsonify({'status': 'error', 'message': 'Неверный текущий пароль'}), 403
    user.password = new_password
    db.session.commit()
    return jsonify({'status': 'ok', 'message': 'Пароль изменён'})

if __name__ == '__main__':
    if '--production' in sys.argv:
        app.run(host='0.0.0.0', port=5000, debug=False)
    else:
        app.run(debug=True, port=5000)