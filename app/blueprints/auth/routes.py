"""
Authentication routes.
"""
from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user, login_required
from app.blueprints.auth import auth_bp
from app.blueprints.auth.forms import LoginForm, MFAVerificationForm, SetupMFAForm, ProfileForm, ChangePasswordForm
from app.models.user import User
from app.models.audit import AuditLog
from app.extensions import db, limiter
import qrcode
import io
import base64


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    """User login."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        if user is None or not user.check_password(form.password.data):
            flash('Email o contraseña incorrectos.', 'danger')
            AuditLog.log(
                action='LOGIN_FAILED',
                resource_type='user',
                user=user if user else User(id=0, email=form.email.data),
                description=f'Failed login attempt for {form.email.data}',
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )
            return redirect(url_for('auth.login'))

        if not user.is_active:
            flash('Su cuenta está desactivada. Contacte con el administrador.', 'warning')
            return redirect(url_for('auth.login'))

        # If MFA is enabled, redirect to MFA verification
        if user.mfa_enabled:
            session['pending_user_id'] = user.id
            session['pending_remember_me'] = form.remember_me.data
            return redirect(url_for('auth.verify_mfa'))

        # Login user
        login_user(user, remember=form.remember_me.data)
        user.update_last_login()

        # Log successful login
        AuditLog.log(
            action='LOGIN_SUCCESS',
            resource_type='user',
            user=user,
            description='User logged in successfully',
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )

        flash('Bienvenido de nuevo.', 'success')

        # Redirect to next page or dashboard
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect(url_for('dashboard.index'))

    return render_template('auth/login.html', form=form)


@auth_bp.route('/verify-mfa', methods=['GET', 'POST'])
def verify_mfa():
    """Verify MFA token."""
    pending_user_id = session.get('pending_user_id')

    if not pending_user_id:
        flash('Sesión inválida. Por favor, inicie sesión de nuevo.', 'warning')
        return redirect(url_for('auth.login'))

    user = User.query.get(pending_user_id)
    if not user:
        session.pop('pending_user_id', None)
        flash('Usuario no encontrado.', 'danger')
        return redirect(url_for('auth.login'))

    form = MFAVerificationForm()

    if form.validate_on_submit():
        if user.verify_totp(form.token.data):
            # MFA verification successful
            remember_me = session.pop('pending_remember_me', False)
            session.pop('pending_user_id', None)

            login_user(user, remember=remember_me)
            user.update_last_login()
            session['mfa_verified'] = True

            # Log successful MFA verification
            AuditLog.log(
                action='MFA_VERIFIED',
                resource_type='user',
                user=user,
                description='MFA verification successful',
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )

            flash('Verificación MFA exitosa. Bienvenido.', 'success')

            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('dashboard.index'))
        else:
            flash('Código de verificación incorrecto.', 'danger')

            # Log failed MFA attempt
            AuditLog.log(
                action='MFA_FAILED',
                resource_type='user',
                user=user,
                description='MFA verification failed',
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )

    return render_template('auth/verify_mfa.html', form=form)


@auth_bp.route('/setup-mfa', methods=['GET', 'POST'])
@login_required
def setup_mfa():
    """Setup MFA for current user."""
    if current_user.mfa_enabled:
        flash('MFA ya está activado para su cuenta.', 'info')
        return redirect(url_for('dashboard.index'))

    form = SetupMFAForm()

    # Generate QR code
    if not current_user.mfa_secret:
        current_user.generate_mfa_secret()
        db.session.commit()

    totp_uri = current_user.get_totp_uri()

    # Generate QR code image
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(totp_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to base64 for display
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()

    if form.validate_on_submit():
        if current_user.verify_totp(form.token.data):
            current_user.mfa_enabled = True
            db.session.commit()

            # Log MFA setup
            AuditLog.log(
                action='MFA_ENABLED',
                resource_type='user',
                user=current_user._get_current_object(),
                description='MFA enabled for user',
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )

            flash('MFA activado exitosamente. Su cuenta ahora está más segura.', 'success')
            return redirect(url_for('dashboard.index'))
        else:
            flash('Código de verificación incorrecto. Inténtelo de nuevo.', 'danger')

    return render_template('auth/setup_mfa.html', form=form, qr_code=qr_code_base64, secret=current_user.mfa_secret)


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile page."""
    form = ProfileForm(obj=current_user)
    password_form = ChangePasswordForm()

    if form.validate_on_submit() and 'profile_submit' in request.form:
        current_user.nombre = form.nombre.data
        current_user.apellidos = form.apellidos.data
        current_user.despacho = form.despacho.data
        current_user.telefono = form.telefono.data
        db.session.commit()

        AuditLog.log(
            action='PROFILE_UPDATED',
            resource_type='user',
            user=current_user._get_current_object(),
            description='User profile updated',
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )

        flash('Perfil actualizado correctamente.', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('auth/profile.html', form=form, password_form=password_form)


@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """Change user password."""
    form = ChangePasswordForm()

    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('La contraseña actual es incorrecta.', 'danger')
            return redirect(url_for('auth.profile'))

        current_user.set_password(form.new_password.data)
        db.session.commit()

        AuditLog.log(
            action='PASSWORD_CHANGED',
            resource_type='user',
            user=current_user._get_current_object(),
            description='User password changed',
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )

        flash('Contraseña cambiada correctamente.', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{error}', 'danger')

    return redirect(url_for('auth.profile'))


@auth_bp.route('/logout')
@login_required
def logout():
    """User logout."""
    # Log logout
    AuditLog.log(
        action='LOGOUT',
        resource_type='user',
        user=current_user._get_current_object(),
        description='User logged out',
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent')
    )

    logout_user()
    session.clear()
    flash('Ha cerrado sesión correctamente.', 'info')
    return redirect(url_for('auth.login'))
