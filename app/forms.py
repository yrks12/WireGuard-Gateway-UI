from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, BooleanField, TextAreaField, PasswordField
from wtforms.validators import DataRequired, Length, EqualTo, Email, Optional, NumberRange

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('new_password', message='Passwords must match')
    ])

class CreateUserForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=3, max=80, message='Username must be between 3 and 80 characters')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    must_change_password = BooleanField('Require password change on first login', default=True)

class EmailSettingsForm(FlaskForm):
    """Form for configuring email alert settings."""
    
    smtp_host = StringField('SMTP Host', validators=[DataRequired()])
    smtp_port = IntegerField('SMTP Port', validators=[DataRequired(), NumberRange(min=1, max=65535)])
    smtp_username = StringField('SMTP Username', validators=[DataRequired()])
    smtp_password = PasswordField('SMTP Password', validators=[DataRequired()])
    smtp_from = StringField('From Email', validators=[DataRequired(), Email()])
    smtp_use_tls = BooleanField('Use TLS', default=True)
    alert_recipients = TextAreaField('Alert Recipients', validators=[DataRequired()],
                                   description='Enter email addresses separated by commas') 