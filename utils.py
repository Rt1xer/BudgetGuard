from models import Budget, Category, db

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
