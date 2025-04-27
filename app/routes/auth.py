from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models.user import User, db
from app.forms import LoginForm, ChangePasswordForm, CreateUserForm
from werkzeug.security import generate_password_hash, check_password_hash

bp = Blueprint('auth', __name__)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.must_change_password:
            return redirect(url_for('auth.change_password'))
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            if user.must_change_password:
                return redirect(url_for('auth.change_password'))
            return redirect(url_for('main.index'))
        flash('Invalid username or password', 'error')
    
    return render_template('auth/login.html', form=form)

@bp.route('/profile')
@login_required
def profile():
    """Show user profile page."""
    return render_template('auth/profile.html')

@bp.route('/users')
@login_required
def users():
    """Show user management page."""
    users = User.query.all()
    return render_template('auth/users.html', users=users)

@bp.route('/users/create', methods=['GET', 'POST'])
@login_required
def create_user():
    """Create a new user."""
    form = CreateUserForm()
    if form.validate_on_submit():
        # Check if username already exists
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists', 'error')
            return redirect(url_for('auth.create_user'))
        
        # Create new user
        user = User(
            username=form.username.data,
            password=generate_password_hash(form.password.data),
            must_change_password=form.must_change_password.data
        )
        db.session.add(user)
        db.session.commit()
        flash('User created successfully', 'success')
        return redirect(url_for('auth.users'))
    
    return render_template('auth/create_user.html', form=form)

@bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not check_password_hash(current_user.password, form.current_password.data):
            flash('Current password is incorrect', 'error')
            return redirect(url_for('auth.change_password'))
        
        current_user.password = generate_password_hash(form.new_password.data)
        current_user.must_change_password = False
        db.session.commit()
        flash('Password changed successfully', 'success')
        return redirect(url_for('main.index'))
    
    return render_template('auth/change_password.html', form=form)

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login')) 