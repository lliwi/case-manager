"""
Case management routes.
"""
from flask import render_template, redirect, url_for, flash, request, send_file
from flask_login import login_required, current_user
from app.blueprints.cases import cases_bp
from app.blueprints.cases.forms import (
    CaseCreateForm, CaseEditForm, LegitimacyValidationForm,
    CaseCloseForm, CaseSearchForm
)
from app.models.case import Case, CaseStatus, LegitimacyType
from app.models.user import User
from app.models.audit import AuditLog
from app.services.legitimacy_service import LegitimacyService
from app.services.libro_registro_service import LibroRegistroService
from app.extensions import db
from app.utils.decorators import require_detective, audit_action
from werkzeug.utils import secure_filename
import os
from datetime import datetime


@cases_bp.route('/')
@login_required
@require_detective()
def index():
    """List all cases for current detective."""
    page = request.args.get('page', 1, type=int)
    per_page = 20

    # Get cases for current detective (or all if admin)
    if current_user.is_admin():
        cases_query = Case.query.filter_by(is_deleted=False)
    else:
        cases_query = Case.query.filter_by(
            detective_id=current_user.id,
            is_deleted=False
        )

    # Apply status filter if provided
    status_filter = request.args.get('status')
    if status_filter:
        try:
            status_enum = CaseStatus[status_filter]
            cases_query = cases_query.filter_by(status=status_enum)
        except KeyError:
            pass

    cases_pagination = cases_query.order_by(
        Case.numero_orden.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        'cases/index.html',
        cases=cases_pagination.items,
        pagination=cases_pagination,
        CaseStatus=CaseStatus
    )


@cases_bp.route('/create', methods=['GET', 'POST'])
@login_required
@require_detective()
def create():
    """Create new case."""
    form = CaseCreateForm()

    if form.validate_on_submit():
        # Create new case
        case = Case(
            numero_orden=Case.generate_numero_orden(),
            cliente_nombre=form.cliente_nombre.data,
            cliente_dni_cif=form.cliente_dni_cif.data,
            cliente_direccion=form.cliente_direccion.data,
            cliente_telefono=form.cliente_telefono.data,
            cliente_email=form.cliente_email.data,
            sujeto_nombres=form.sujeto_nombres.data,
            sujeto_dni_nie=form.sujeto_dni_nie.data,
            sujeto_descripcion=form.sujeto_descripcion.data,
            objeto_investigacion=form.objeto_investigacion.data,
            descripcion_detallada=form.descripcion_detallada.data,
            legitimacy_type=LegitimacyType[form.legitimacy_type.data],
            legitimacy_description=form.legitimacy_description.data,
            ubicacion_principal=form.ubicacion_principal.data,
            priority=form.priority.data,
            presupuesto_estimado=form.presupuesto_estimado.data,
            confidencial=form.confidencial.data,
            notas_internas=form.notas_internas.data,
            detective_id=current_user.id,
            detective_tip=current_user.tip_number,
            despacho=current_user.despacho,
            status=CaseStatus.PENDIENTE_VALIDACION
        )

        # Handle legitimacy document upload
        if form.legitimacy_document.data:
            file = form.legitimacy_document.data
            filename = secure_filename(f"{case.numero_orden}_legitimacy_{file.filename}")
            upload_folder = os.path.join(os.getcwd(), 'data', 'uploads', 'legitimacy')
            os.makedirs(upload_folder, exist_ok=True)
            filepath = os.path.join(upload_folder, filename)
            file.save(filepath)
            case.legitimacy_document_path = filepath

        # Scan for crime indicators
        crime_scan = LegitimacyService.scan_case_for_crimes(case)
        if crime_scan['detected']:
            flash(
                f'¡ATENCIÓN! Se han detectado posibles indicadores de delitos perseguibles de oficio: '
                f'{", ".join(crime_scan["keywords"])}. El caso ha sido bloqueado para revisión.',
                'warning'
            )

        db.session.add(case)
        db.session.commit()

        # Log creation
        AuditLog.log(
            action='CASE_CREATED',
            resource_type='case',
            resource_id=case.id,
            user=current_user._get_current_object(),
            description=f'Created case {case.numero_orden}',
            extra_data={'legitimacy_type': case.legitimacy_type.value}
        )

        flash(f'Caso {case.numero_orden} creado exitosamente.', 'success')
        return redirect(url_for('cases.detail', case_id=case.id))

    return render_template('cases/create.html', form=form)


@cases_bp.route('/<int:case_id>')
@login_required
@require_detective()
@audit_action('VIEWED', 'case')
def detail(case_id):
    """View case details."""
    case = Case.query.get_or_404(case_id)

    # Check permissions
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permisos para ver este caso.', 'danger')
        return redirect(url_for('cases.index'))

    # Get legitimacy requirements
    legitimacy_reqs = LegitimacyService.get_legitimacy_requirements(case.legitimacy_type)

    return render_template(
        'cases/detail.html',
        case=case,
        legitimacy_reqs=legitimacy_reqs
    )


@cases_bp.route('/<int:case_id>/edit', methods=['GET', 'POST'])
@login_required
@require_detective()
def edit(case_id):
    """Edit case (limited fields)."""
    case = Case.query.get_or_404(case_id)

    # Check permissions
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permisos para editar este caso.', 'danger')
        return redirect(url_for('cases.index'))

    form = CaseEditForm(obj=case)

    if form.validate_on_submit():
        # Update editable fields
        case.descripcion_detallada = form.descripcion_detallada.data
        case.status = CaseStatus[form.status.data]
        case.priority = form.priority.data
        case.ubicacion_principal = form.ubicacion_principal.data
        case.presupuesto_estimado = form.presupuesto_estimado.data
        case.honorarios = form.honorarios.data
        case.notas_internas = form.notas_internas.data

        db.session.commit()

        # Log update
        AuditLog.log(
            action='CASE_UPDATED',
            resource_type='case',
            resource_id=case.id,
            user=current_user._get_current_object(),
            description=f'Updated case {case.numero_orden}'
        )

        flash('Caso actualizado exitosamente.', 'success')
        return redirect(url_for('cases.detail', case_id=case.id))

    return render_template('cases/edit.html', form=form, case=case)


@cases_bp.route('/<int:case_id>/validate', methods=['GET', 'POST'])
@login_required
@require_detective()
def validate_legitimacy(case_id):
    """Validate case legitimacy."""
    case = Case.query.get_or_404(case_id)

    # Only admin or assigned detective can validate
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permisos para validar este caso.', 'danger')
        return redirect(url_for('cases.index'))

    if case.legitimacy_validated:
        flash('La legitimidad ya ha sido validada para este caso.', 'info')
        return redirect(url_for('cases.detail', case_id=case.id))

    form = LegitimacyValidationForm()

    if form.validate_on_submit():
        LegitimacyService.validate_legitimacy(
            case=case,
            user=current_user._get_current_object(),
            approved=form.approved.data,
            notes=form.validation_notes.data
        )

        if form.approved.data:
            flash('Legitimidad validada. El caso puede proceder.', 'success')
        else:
            flash('Legitimidad rechazada. El caso permanece pendiente.', 'warning')

        return redirect(url_for('cases.detail', case_id=case.id))

    # Get legitimacy requirements
    legitimacy_reqs = LegitimacyService.get_legitimacy_requirements(case.legitimacy_type)

    return render_template(
        'cases/validate.html',
        form=form,
        case=case,
        legitimacy_reqs=legitimacy_reqs
    )


@cases_bp.route('/<int:case_id>/close', methods=['GET', 'POST'])
@login_required
@require_detective()
def close(case_id):
    """Close case."""
    case = Case.query.get_or_404(case_id)

    # Check permissions
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permisos para cerrar este caso.', 'danger')
        return redirect(url_for('cases.index'))

    if case.status == CaseStatus.CERRADO:
        flash('Este caso ya está cerrado.', 'info')
        return redirect(url_for('cases.detail', case_id=case.id))

    form = CaseCloseForm()

    if form.validate_on_submit():
        # Add closure notes
        if form.closure_notes.data:
            case.notas_internas = (case.notas_internas or '') + \
                f"\n\n[CIERRE - {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}]\n{form.closure_notes.data}"

        case.close(current_user._get_current_object())

        flash(f'Caso {case.numero_orden} cerrado exitosamente.', 'success')
        return redirect(url_for('cases.detail', case_id=case.id))

    return render_template('cases/close.html', form=form, case=case)


@cases_bp.route('/<int:case_id>/delete', methods=['POST'])
@login_required
@require_detective()
def delete(case_id):
    """Soft delete case."""
    case = Case.query.get_or_404(case_id)

    # Only admin can delete
    if not current_user.is_admin():
        flash('Solo los administradores pueden eliminar casos.', 'danger')
        return redirect(url_for('cases.index'))

    case.soft_delete(current_user._get_current_object())

    flash(f'Caso {case.numero_orden} eliminado (soft delete).', 'success')
    return redirect(url_for('cases.index'))


@cases_bp.route('/search', methods=['GET', 'POST'])
@login_required
@require_detective()
def search():
    """Search cases."""
    form = CaseSearchForm()

    # Populate detective choices for admins
    if current_user.is_admin():
        detectives = User.query.filter(
            User.roles.any(name='detective')
        ).all()
        form.detective.choices = [('', 'Todos')] + [
            (str(d.id), f"{d.nombre} (TIP: {d.tip_number})") for d in detectives
        ]

    # Build query
    query = Case.query.filter_by(is_deleted=False)

    # Apply filters if form submitted
    if form.validate_on_submit():
        if form.numero_orden.data:
            query = query.filter(Case.numero_orden.like(f"%{form.numero_orden.data}%"))

        if form.cliente_nombre.data:
            query = query.filter(Case.cliente_nombre.like(f"%{form.cliente_nombre.data}%"))

        if form.detective.data and current_user.is_admin():
            query = query.filter_by(detective_id=int(form.detective.data))

        if form.status.data:
            query = query.filter_by(status=CaseStatus[form.status.data])

        if form.legitimacy_type.data:
            query = query.filter_by(legitimacy_type=LegitimacyType[form.legitimacy_type.data])

        if form.fecha_desde.data:
            query = query.filter(Case.fecha_inicio >= form.fecha_desde.data)

        if form.fecha_hasta.data:
            query = query.filter(Case.fecha_inicio <= form.fecha_hasta.data)
    else:
        # If not admin, only show own cases
        if not current_user.is_admin():
            query = query.filter_by(detective_id=current_user.id)

    results = query.order_by(Case.numero_orden.desc()).all()

    return render_template(
        'cases/search.html',
        form=form,
        results=results
    )
