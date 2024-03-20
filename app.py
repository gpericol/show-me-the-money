from datetime import datetime
from functools import wraps
import uuid
from flask import Flask, flash, redirect, render_template, request, url_for, session
from werkzeug.security import check_password_hash, generate_password_hash
from models import *
from forms import *
import config
from flask_wtf.csrf import CSRFProtect

app = Flask(__name__)

app.config['SECRET_KEY'] = config.SECRET_KEY
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///expenses.db"

csrf = CSRFProtect(app)
db.init_app(app)

with app.app_context():
    db.create_all()

def flash_errors(form):
    for field, errors in form.errors.items():
        for error in errors:
            flash(f'Error in field "{getattr(form, field).label.text}": {error}', 'error')

def check_role(required_roles):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if 'id' not in session or 'role' not in session:
                return redirect(url_for('login'))
            elif session['role'] not in required_roles:
                return redirect(url_for('login'))
            return func(*args, **kwargs)
        return wrapper
    return decorator    

@app.route('/install', methods=['GET'])
def install():
    existing_user = User.query.first()
    if not existing_user:
        admin_user = User(email='admin@admin.it', password=generate_password_hash('admin'), active=True, role=config.ADMIN_ROLE)
        db.session.add(admin_user)
        db.session.commit()
    
    return redirect(url_for('login'))

@app.route('/')
@check_role(['admin', 'user'])
def index():
    return redirect(url_for('my_groups'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'id' in session:
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        user = User.query.filter_by(email=email, active=True).first()
        if user and check_password_hash(user.password, password):
            session['id'] = user.id
            session['email'] = user.email
            session['role'] = user.role
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password', 'error')
            return redirect(url_for('login'))
    return render_template('login.html', form=form)

@app.route('/logout', methods=['GET'])
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/users', methods=['GET'])
@check_role(['admin'])
def users():
    users = User.query.all()
    return render_template('users.html', users=users)

# todo CSRF protection here!!!
@app.route('/activate_user/<int:user_id>', methods=['GET'])
@check_role(['admin'])
def activate_user(user_id):
    user = User.query.get_or_404(user_id)
    user.active = True
    db.session.commit()
    return redirect(url_for('users'))

@app.route('/change_password/<int:user_id>', methods=['GET', 'POST'])
@check_role(['admin'])
def change_password(user_id):
    user = User.query.get_or_404(user_id)
    form = ChangePasswordForm()
    if form.validate_on_submit():
        new_password = form.new_password.data
        user.password = generate_password_hash(new_password)
        db.session.commit()
        return redirect(url_for('users'))
    else:
        flash_errors(form)

    return render_template('change_password.html', form=form, user=user)

@app.route('/create_user', methods=['GET', 'POST'])
def create_user():
    form = CreateUserForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        password = generate_password_hash(password)
        new_user = User(email=email, password=password, active=False, role=config.USER_ROLE)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('users'))
    else:
        flash_errors(form)
    return render_template('create_user.html', form=form)

@app.route('/groups', methods=['GET'])
@check_role(['admin'])
def groups():
    groups = Group.query.all()
    return render_template('groups.html', groups=groups)

@app.route('/create_group', methods=['GET', 'POST'])
@check_role(['admin'])
def create_group():
    form = CreateGroupForm()
    if form.validate_on_submit():
        name = form.name.data
        code = uuid.uuid4().hex[:6].upper()
        new_group = Group(name=name, code=code)
        db.session.add(new_group)
        db.session.commit()
        new_group_member = GroupMember(user_id=session.get('id'), group_id=new_group.id)
        db.session.add(new_group_member)
        db.session.commit()
        return redirect(url_for('groups'))
    else:
        flash_errors(form)
    return render_template('create_group.html', form=form)


# todo CSRF protection here!!!
@app.route('/delete_group/<int:group_id>', methods=['GET'])
@check_role(['admin'])
def delete_group(group_id):
    group = Group.query.get_or_404(group_id)
    related_expenses = Expense.query.filter_by(group_id=group_id).all()
    for expense in related_expenses:
        db.session.delete(expense)
        
    related_members = GroupMember.query.filter_by(group_id=group_id).all()
    for member in related_members:
         db.session.delete(member)
        
    db.session.delete(group)
    db.session.commit()
    return redirect(url_for('groups'))

@app.route('/my_groups', methods=['GET'])
@check_role(['admin', 'user'])
def my_groups():
    user_id = session.get('id')
    user = User.query.get_or_404(user_id)
    groups = user.groups
    form = JoinGroupForm()
    return render_template('my_groups.html', groups=groups, form=form)

@app.route('/join_group', methods=['POST'])
@check_role(['user'])
def join_group():
    form = JoinGroupForm()
    if form.validate_on_submit():
        code = form.code.data
        group = Group.query.filter_by(code=code).first()
        user = User.query.filter_by(id=session.get('id')).first()
    else:
        flash_errors(form)
    
    if not group or user in group.members:
        return redirect(url_for('my_groups'))
    
    user.groups.append(group)
    db.session.commit()
    return redirect(url_for('my_groups'))

@app.route('/show_group/<int:group_id>', methods=['GET'])
@check_role(['admin', 'user'])
def show_group(group_id):
    user = User.query.get_or_404(session.get('id'))
    group = Group.query.get_or_404(group_id)
    if session.get('id') not in [member.id for member in group.members]:
        return redirect(url_for('my_groups'))
    
    total_expenses = sum([expense.amount for expense in group.expenses])
    return render_template('show_group.html', group=group, user=user, total_expenses=total_expenses)

@app.route('/add_expense/<int:group_id>', methods=['GET', 'POST'])
@check_role(['admin', 'user'])
def add_expense(group_id):
    group = Group.query.get_or_404(group_id)
    if session.get('id') not in [member.id for member in group.members]:
        return redirect(url_for('my_groups'))

    form = AddExpenseForm()
    if form.validate_on_submit():
        amount = form.amount.data
        description = form.description.data
        new_expense = Expense(amount=amount, description=description, group_id=group_id, user_id=session.get('id'))
        db.session.add(new_expense)
        db.session.commit()
        return redirect(url_for('show_group', group_id=group_id))
    else:
        flash_errors(form)
    return render_template('add_expense.html', form=form, group=group)

@app.route('/delete_expense/<int:expense_id>', methods=['GET'])
@check_role(['admin', 'user'])
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)

    if expense.user_id != session.get('id'):
        db.session.delete(expense)
        db.session.commit()
    return redirect(url_for('show_group', group_id=expense.group_id))

@app.route('/debts/<int:group_id>', methods=['GET'])
@check_role(['admin', 'user'])
def debts(group_id):
    group = Group.query.get_or_404(group_id)
    if session.get('id') not in [member.id for member in group.members]:
        return redirect(url_for('my_groups'))

    total_expenses = sum(expense.amount for expense in group.expenses)
    average_expense = total_expenses / len(group.members)

    debts = {}
    
    for member in group.members:
        expenses = sum([expense.amount for expense in member.expenses if expense.group_id == group_id])
        debts[member.email] = round(expenses - average_expense, 2)

    suggestions = []
    
    for debtor, amount_owed in debts.items():
        # Check if the current member owes money (positive debt).
        if amount_owed > 0:
            # Iterate over each member's debt again to find potential creditors (negative debt).
            for creditor, amount_due in debts.items():
                # Check if the potential creditor is owed money (negative debt).
                if amount_due < 0:
                    # Determine the suggested payment amount by taking the minimum between the owed amount and the owed money.
                    suggested_payment = min(abs(amount_due), amount_owed)
                    # Add the suggestion to the list of suggestions.
                    suggestions.append((debtor, creditor, suggested_payment))
                    # Update the debt for the debtor and creditor accordingly.
                    amount_owed -= suggested_payment
                    debts[debtor] = round(amount_owed, 2)
                    debts[creditor] += suggested_payment

    return render_template('debts.html', group=group, debts=debts, suggestions=suggestions)
