import os
import io
import time
import requests
import csv
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from collections import defaultdict
from werkzeug.security import check_password_hash
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from app import app
from models import db, User, Budget, Transaction, Category
from datetime import datetime

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
URL = f'https://api.telegram.org/bot{TOKEN}/'
last_update_id = 0

user_sessions = {}
add_steps = {}
pending_transactions = {}

def get_updates():
    global last_update_id
    try:
        res = requests.get(URL + 'getUpdates', params={'offset': last_update_id + 1, 'timeout': 10})
        return res.json().get('result', [])
    except Exception as e:
        print("Ошибка получения сообщений:", e)
        return []

def send_message(chat_id, text, reply_markup=None):
    data = {'chat_id': chat_id, 'text': text}
    if reply_markup:
        data['reply_markup'] = reply_markup
    try:
        requests.post(URL + 'sendMessage', json=data)
    except Exception as e:
        print("Ошибка отправки сообщения:", e)

def send_report(chat_id, user_id):
    with app.app_context():
        transactions = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.date.desc()).all()
        if not transactions:
            send_message(chat_id, "📭 У вас нет операций для отчёта.")
            return

        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')  # ← важное изменение!
        writer.writerow(["Дата", "Категория", "Сумма", "Тип"])

        for tx in transactions:
            kind = 'Доход' if tx.kind == 'income' else 'Расход'
            writer.writerow([tx.date, tx.category, f"{tx.amount:.2f}", kind])

        content = output.getvalue()
        output.close()

        files = {'document': ('report.csv', content.encode('utf-8-sig'))}
        data = {'chat_id': chat_id}
        requests.post(f"{URL}sendDocument", data=data, files=files)
def send_chart(chat_id, user_id):
    with app.app_context():
        data = defaultdict(float)
        txs = Transaction.query.filter_by(user_id=user_id, kind='expense').all()
        if not txs:
            send_message(chat_id, "📭 Нет данных для построения диаграммы.")
            return
        for tx in txs:
            data[tx.category] += tx.amount

        labels = list(data.keys())
        values = list(data.values())

        fig, ax = plt.subplots()
        ax.pie(values, labels=labels, autopct='%1.1f%%')
        ax.set_title("Расходы по категориям")
        plt.savefig("chart.png")
        plt.close()

        with open("chart.png", "rb") as f:
            files = {'photo': f}
            data = {'chat_id': chat_id}
            requests.post(URL + 'sendPhoto', data=data, files=files)

def get_categories_markup(kind):
    with app.app_context():
        cats = Category.query.filter_by(kind=kind).order_by(Category.name).all()
        buttons = [[InlineKeyboardButton(c.name, callback_data=f"cat:{c.name}")] for c in cats]
        buttons.append([InlineKeyboardButton("➕ Своя категория", callback_data="cat:custom")])
        return InlineKeyboardMarkup(buttons).to_dict()

def process_message(msg):
    global user_sessions, add_steps, pending_transactions
    chat_id = msg['message']['chat']['id']
    text = msg['message'].get('text', '').strip()

    if chat_id not in user_sessions:
        with app.app_context():
            user = User.query.filter_by(telegram_id=chat_id).first()
            if user:
                user_sessions[chat_id] = {'user_id': user.id}
                keyboard = ReplyKeyboardMarkup(
                    keyboard=[["💰 Баланс", "📄 Отчёт", "📊 Диаграмма"], ["🚪 Выход"]],
                    resize_keyboard=True
                ).to_dict()
                send_message(chat_id, f"👋 Добро пожаловать обратно, {user.username}!", reply_markup=keyboard)
                return

    if chat_id in add_steps and add_steps[chat_id].get('step') == 'custom_category':
        custom = text
        tx = pending_transactions.get(chat_id)
        if tx:
            with app.app_context():
                existing = Category.query.filter_by(name=custom, kind=tx['kind']).first()
                if not existing:
                    db.session.add(Category(
                        name=custom,
                        kind=tx['kind'],
                        user_id=user_sessions[chat_id]['user_id']
                    ))
                    db.session.commit()
                user_id = user_sessions[chat_id]['user_id']
                t = Transaction(
                    user_id=user_id,
                    amount=tx['amount'],
                    category=custom,
                    kind=tx['kind'],
                    date=datetime.utcnow().date()
                )
                db.session.add(t)
                budget = Budget.query.filter_by(user_id=user_id).first()
                budget.total += t.amount if tx['kind'] == 'income' else -t.amount
                db.session.commit()
            sign = '+' if tx['kind'] == 'income' else '-'
            label = 'Доход' if tx['kind'] == 'income' else 'Расход'
            send_message(chat_id, f"✅ {label}: {sign}{tx['amount']:.2f} ₽ в категорию \"{category}\"")
            add_steps.pop(chat_id, None)
            pending_transactions.pop(chat_id, None)
        return

    if text.startswith('+') or text.startswith('-'):
        try:
            amount = float(text)
            kind = 'income' if amount > 0 else 'expense'
            pending_transactions[chat_id] = {'amount': abs(amount), 'kind': kind}
            send_message(chat_id,
                         f"{'💰 Доход' if kind == 'income' else '💸 Расход'} — выберите категорию:",
                         reply_markup=get_categories_markup(kind))
        except:
            send_message(chat_id, "⚠️ Неверный формат суммы. Используйте + или - перед числом.")
        return

    if text == '/start' or text == '🔐 Вход':
        send_message(chat_id, "👋 Введите логин:")
        user_sessions[chat_id] = {'step': 'login'}
        return

    if text in ['/logout', '🚪 Выход']:
        with app.app_context():
            session = user_sessions.pop(chat_id, None)
            if session:
                user = User.query.get(session['user_id'])
                if user:
                    user.telegram_id = None
                    db.session.commit()
        keyboard = {"keyboard": [["🔐 Вход"]], "resize_keyboard": True}
        send_message(chat_id, "🚪 Вы вышли из аккаунта.", reply_markup=keyboard)
        return

    if chat_id in user_sessions and user_sessions[chat_id].get('step') == 'login':
        user_sessions[chat_id]['login'] = text
        user_sessions[chat_id]['step'] = 'password'
        send_message(chat_id, "🔐 Введите пароль:")
        return

    if chat_id in user_sessions and user_sessions[chat_id].get('step') == 'password':
        login = user_sessions[chat_id]['login']
        password = text
        with app.app_context():
            user = User.query.filter_by(username=login).first()
            if user and check_password_hash(user.password_hash, password):
                if not user.telegram_id:
                    user.telegram_id = chat_id
                    db.session.commit()
                user_sessions[chat_id] = {'user_id': user.id}
                keyboard = ReplyKeyboardMarkup(
                    keyboard=[["💰 Баланс", "📄 Отчёт", "📊 Диаграмма"], ["🚪 Выход"]],
                    resize_keyboard=True
                ).to_dict()
                send_message(chat_id, f"✅ Добро пожаловать, {login}!\nВыберите действие:", reply_markup=keyboard)
            else:
                send_message(chat_id, "❌ Неверный логин или пароль. Попробуйте снова: /start")
                user_sessions.pop(chat_id, None)
        return

    if text in ['📄 Отчёт', '/report']:
        session = user_sessions.get(chat_id)
        if session:
            send_report(chat_id, session['user_id'])
        return

    if text in ['📊 Диаграмма', '/chart']:
        session = user_sessions.get(chat_id)
        if session:
            send_chart(chat_id, session['user_id'])
        return

    if text in ['💰 Баланс', '/balance']:
        session = user_sessions.get(chat_id)
        if session:
            with app.app_context():
                b = Budget.query.filter_by(user_id=session['user_id']).first()
                send_message(chat_id, f"💰 Баланс: {b.total:.2f} ₽" if b else "Бюджет не найден.")
        return

def process_callback(callback):
    chat_id = callback['message']['chat']['id']
    data = callback['data']

    if data.startswith("cat:"):
        category = data[4:]
        if category == "custom":
            send_message(chat_id, "✍️ Введите название новой категории:")
            add_steps[chat_id] = {"step": "custom_category"}
            return

        tx = pending_transactions.get(chat_id)
        if tx:
            with app.app_context():
                user_id = user_sessions[chat_id]['user_id']
                t = Transaction(
                    user_id=user_id,
                    amount=tx['amount'],
                    category=category,
                    kind=tx['kind'],
                    date=datetime.utcnow().date()
                )
                db.session.add(t)
                budget = Budget.query.filter_by(user_id=user_id).first()
                if tx['kind'] == 'income':
                    budget.total += t.amount
                else:
                    budget.total -= t.amount
                db.session.commit()
            sign = '+' if tx['kind'] == 'income' else '-'
            label = 'Доход' if tx['kind'] == 'income' else 'Расход'
            send_message(chat_id, f"✅ {label}: {sign}{tx['amount']:.2f} ₽ в категорию \"{category}\"")
            pending_transactions.pop(chat_id, None)
        return

def run():
    global last_update_id
    print("🤖 Бот запущен!")
    while True:
        updates = get_updates()
        for msg in updates:
            if 'message' in msg:
                process_message(msg)
            if 'callback_query' in msg:
                process_callback(msg['callback_query'])
            last_update_id = msg['update_id']
        time.sleep(1)

if __name__ == '__main__':
    run()