from flask import Blueprint, request, render_template, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User
from utils import init_defaults

users_bp = Blueprint('users', __name__)

@users_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        if not username or not password:
            flash("Имя и пароль обязательны", "danger")
            return redirect(url_for('users.register'))
        if User.query.filter_by(username=username).first():
            flash("Пользователь уже существует", "danger")
            return redirect(url_for('users.register'))
        user = User(username=username, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        init_defaults(user.id)
        flash("Регистрация успешна. Войдите в аккаунт", "success")
        return redirect(url_for('users.login'))
    return render_template('register.html')

@users_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password_hash, request.form['password']):
            session.pop('_flashes', None)
            login_user(user)
            return redirect(url_for('views.home'))
        flash("Неверный логин или пароль", "danger")
    return render_template('login.html')

@users_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Вы успешно вышли", "success")
    return redirect(url_for('users.login'))
