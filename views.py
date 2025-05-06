from flask import Blueprint, request, render_template, jsonify, Response
from flask_login import login_required, current_user
from sqlalchemy import func
from models import db, Transaction, Budget, Category
from datetime import datetime, date
import io, csv

views_bp = Blueprint('views', __name__)

@views_bp.route('/')
@login_required
def home():
    budget = Budget.query.filter_by(user_id=current_user.id).first()
    return render_template('index.html', budget=budget.total if budget else 0)

@views_bp.route('/report')
@login_required
def report_page():
    current_month = date.today().strftime('%Y-%m')
    return render_template('report.html', current_month=current_month)

@views_bp.route('/report_data')
@login_required
def report_data():
    month = request.args.get('month')
    if not month:
        return jsonify({'error': 'month required'}), 400
    result = (
        db.session.query(Transaction.category, func.sum(Transaction.amount))
        .filter_by(user_id=current_user.id, kind='expense')
        .filter(func.strftime('%Y-%m', Transaction.date) == month)
        .group_by(Transaction.category)
        .all()
    )
    by_category = [{'category': c, 'amount': round(a, 2)} for c, a in result]
    total = sum(item['amount'] for item in by_category)
    return jsonify({'total': total, 'by_category': by_category})

@views_bp.route('/export_csv')
@login_required
def export_csv():
    month = request.args.get('month')
    if not month:
        return 'Missing month', 400

    transactions = (
        Transaction.query
        .filter_by(user_id=current_user.id, kind='expense')
        .filter(func.strftime('%Y-%m', Transaction.date) == month)
        .order_by(Transaction.date)
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['Дата', 'Категория', 'Сумма'])
    for t in transactions:
        writer.writerow([t.date.strftime('%Y-%m-%d'), t.category, f'{t.amount:.2f}'])

    return Response('\ufeff' + output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename=expenses_{month}.csv'})

@views_bp.route('/add', methods=['POST'])
@login_required
def add_transaction():
    data = request.get_json()
    tx = Transaction(
        amount=float(data['amount']),
        category=data['category'],
        kind=data['kind'],
        date=datetime.utcnow(),
        user_id=current_user.id
    )
    db.session.add(tx)

    budget = Budget.query.filter_by(user_id=current_user.id).first()
    if not budget:
        budget = Budget(user_id=current_user.id, total=0)
        db.session.add(budget)

    budget.total += float(data['amount']) if data['kind'] == 'income' else -float(data['amount'])
    db.session.commit()
    return jsonify({'success': True})

@views_bp.route('/categories', methods=['GET', 'POST'])
@login_required
def categories():
    if request.method == 'POST':
        name = request.json.get('name')
        kind = request.json.get('kind')
        if not Category.query.filter_by(name=name, kind=kind, user_id=current_user.id).first():
            db.session.add(Category(name=name, kind=kind, user_id=current_user.id))
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Категория уже существует'}), 400

    kind = request.args.get('kind')
    query = Category.query.filter_by(user_id=current_user.id)
    if kind:
        query = query.filter_by(kind=kind)
    return jsonify([c.name for c in query.order_by(Category.name).all()])

@views_bp.route('/transactions')
@login_required
def get_transactions():
    q = request.args.get('q')
    start = request.args.get('start')
    end = request.args.get('end')

    query = Transaction.query.filter_by(user_id=current_user.id)
    if q:
        query = query.filter(func.lower(Transaction.category).like(func.lower(f"%{q}%")))
    if start:
        query = query.filter(Transaction.date >= start)
    if end:
        query = query.filter(Transaction.date <= end)

    result = query.order_by(Transaction.date.desc()).all()
    return jsonify([{
        'id': t.id, 'amount': t.amount, 'category': t.category,
        'date': t.date.strftime('%Y-%m-%d'), 'kind': t.kind
    } for t in result])

@views_bp.route('/budget')
@login_required
def get_budget():
    budget = Budget.query.filter_by(user_id=current_user.id).first()
    return jsonify({'total': budget.total if budget else 0})
