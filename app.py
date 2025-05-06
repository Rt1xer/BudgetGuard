from flask import Flask
from flask_login import LoginManager
import os
from dotenv import load_dotenv
from models import db, User, Budget, Category
from users import users_bp
from views import views_bp
from utils import init_defaults

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'default-fallback')


app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'  # ← фиктивная
app.config['SQLALCHEMY_BINDS'] = {
    'budget': 'sqlite:///budget.db',
    'users': 'sqlite:///users.db'
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


db.init_app(app)
login_manager = LoginManager()
login_manager.login_view = 'users.login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ─── Blueprint маршруты ───────────────────────────────
app.register_blueprint(users_bp)
app.register_blueprint(views_bp)

# ─── Начальная инициализация ──────────────────────────
def init_defaults(user_id):
    if not Budget.query.filter_by(user_id=user_id).first():
        db.session.add(Budget(user_id=user_id, total=0))

    income_cats = ['Зарплата', 'Фриланс', 'Подарок', 'Проценты']
    expense_cats = ['Супермаркеты', 'Такси', 'Развлечения', 'Коммунальные']

    for name in income_cats:
        if not Category.query.filter_by(name=name, kind='income', user_id=user_id).first():
            db.session.add(Category(name=name, kind='income', user_id=user_id))

    for name in expense_cats:
        if not Category.query.filter_by(name=name, kind='expense', user_id=user_id).first():
            db.session.add(Category(name=name, kind='expense', user_id=user_id))

    db.session.commit()


# ─── Запуск ────────────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Создаём все бинды
        # можно вручную вызвать init_defaults() после регистрации пользователя
    app.run(debug=True)
