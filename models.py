from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String, unique=True)
    password = db.Column(db.String)
    active = db.Column(db.Boolean, default=True)
    role = db.Column(db.String)

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    code = db.Column(db.String)
    members = db.relationship("User", secondary="group_member", backref="groups")
    expenses = db.relationship("Expense", backref="group", order_by="Expense.date.desc()")

class GroupMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"))

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float)
    description = db.Column(db.String)
    date = db.Column(db.DateTime, default=datetime.now)
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    user = db.relationship("User", backref="expenses")

    def formatted_date(self):
        return self.date.strftime("%Y-%m-%d")
