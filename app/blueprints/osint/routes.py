"""
OSINT Routes
Handles CRUD operations for OSINT contacts and validations
"""
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.blueprints.osint import osint
from app.blueprints.osint.forms import OSINTContactForm, ValidateContactForm, SearchContactForm
from app.models import OSINTContact, OSINTValidation, Case, ApiKey
from app.plugins.osint.ipqualityscore_validator import IPQualityScoreValidatorPlugin
from app.utils.decorators import require_detective
from app import db
from datetime import datetime


@osint.route('/')
@login_required
def index():
    """List all OSINT contacts with filtering"""
    # Initialize forms
    search_form = SearchContactForm(request.args)

    # Populate case choices for filter
    cases = Case.query.filter_by(is_deleted=False).order_by(Case.created_at.desc()).all()
    search_form.case_id.choices = [(0, 'Todos los casos')] + [(c.id, f"{c.numero_orden} - {c.objeto_investigacion[:50]}") for c in cases]

    # Build query
    query = OSINTContact.query.filter_by(is_deleted=False)

    # Apply filters
    if search_form.search_term.data:
        search_term = search_form.search_term.data
        query = OSINTContact.search(search_term)

    if search_form.contact_type.data:
        query = query.filter_by(contact_type=search_form.contact_type.data)

    if search_form.status.data:
        query = query.filter_by(status=search_form.status.data)

    if search_form.validation_status.data:
        if search_form.validation_status.data == 'validated':
            query = query.filter_by(is_validated=True)
        elif search_form.validation_status.data == 'not_validated':
            query = query.filter_by(is_validated=False)

    if search_form.case_id.data and search_form.case_id.data != 0:
        query = query.filter_by(case_id=search_form.case_id.data)

    # Get results
    contacts = query.order_by(OSINTContact.created_at.desc()).all()

    # Calculate statistics
    stats = {
        'total': OSINTContact.query.filter_by(is_deleted=False).count(),
        'validated': OSINTContact.query.filter_by(is_deleted=False, is_validated=True).count(),
        'high_risk': OSINTContact.query.filter_by(
            is_deleted=False,
            is_validated=True
        ).filter(
            db.or_(
                OSINTContact.risk_level == 'high',
                OSINTContact.risk_level == 'very_high'
            )
        ).count(),
        'by_type': {}
    }

    # Count by type
    for contact_type in ['email', 'phone', 'social_profile', 'username', 'other']:
        stats['by_type'][contact_type] = OSINTContact.query.filter_by(
            is_deleted=False,
            contact_type=contact_type
        ).count()

    return render_template('osint/index.html',
                          contacts=contacts,
                          search_form=search_form,
                          stats=stats)


@osint.route('/case/<int:case_id>/create', methods=['GET', 'POST'])
@login_required
@require_detective()
def create(case_id):
    """Create a new OSINT contact for a case"""
    case = Case.query.get_or_404(case_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permiso para modificar este caso.', 'danger')
        return redirect(url_for('cases.index'))

    if case.is_deleted:
        flash('Este caso ha sido eliminado.', 'warning')
        return redirect(url_for('cases.index'))

    form = OSINTContactForm()

    if form.validate_on_submit():
        try:
            # Create contact associated with this case
            contact = OSINTContact.create(
                contact_type=form.contact_type.data,
                contact_value=form.contact_value.data,
                created_by_id=current_user.id,
                name=form.name.data,
                description=form.description.data,
                source=form.source.data,
                case_id=case_id,
                tags=form.tags.data
            )

            flash(f'Contacto OSINT "{contact.contact_value}" creado exitosamente.', 'success')
            return redirect(url_for('osint.detail', case_id=case_id, contact_id=contact.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear el contacto: {str(e)}', 'danger')

    return render_template('osint/form.html', form=form, case=case, title='Nuevo Contacto OSINT')


@osint.route('/create', methods=['GET', 'POST'])
@login_required
def create_no_case():
    """Create a new OSINT contact without case association (global view)"""
    form = OSINTContactForm()

    # Populate case choices
    cases = Case.query.filter_by(is_deleted=False).order_by(Case.created_at.desc()).all()
    form.case_id.choices = [(0, 'Sin caso asociado')] + [(c.id, f"{c.numero_orden} - {c.objeto_investigacion[:50]}") for c in cases]

    if form.validate_on_submit():
        try:
            # Prepare case_id (0 means no case)
            case_id_value = form.case_id.data if form.case_id.data != 0 else None

            # Create contact
            contact = OSINTContact.create(
                contact_type=form.contact_type.data,
                contact_value=form.contact_value.data,
                created_by_id=current_user.id,
                name=form.name.data,
                description=form.description.data,
                source=form.source.data,
                case_id=case_id_value,
                tags=form.tags.data
            )

            flash(f'Contacto OSINT "{contact.contact_value}" creado exitosamente.', 'success')

            # Redirect based on whether it has a case
            if contact.case_id:
                return redirect(url_for('osint.detail', case_id=contact.case_id, contact_id=contact.id))
            else:
                return redirect(url_for('osint.detail_no_case', contact_id=contact.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear el contacto: {str(e)}', 'danger')

    return render_template('osint/form.html', form=form, title='Nuevo Contacto OSINT')


@osint.route('/case/<int:case_id>/<int:contact_id>')
@login_required
@require_detective()
def detail(case_id, contact_id):
    """View OSINT contact details within case context"""
    case = Case.query.get_or_404(case_id)
    contact = OSINTContact.query.get_or_404(contact_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permiso para ver este caso.', 'danger')
        return redirect(url_for('cases.index'))

    if case.is_deleted or contact.is_deleted:
        flash('El caso o contacto ha sido eliminado.', 'warning')
        return redirect(url_for('cases.index'))

    # Verify contact belongs to case
    if contact.case_id != case_id:
        flash('El contacto no pertenece a este caso.', 'warning')
        return redirect(url_for('osint.case_contacts', case_id=case_id))

    # Create validation form
    validate_form = ValidateContactForm()
    validate_form.contact_id.data = contact.id

    # Get validation history for this contact
    validations = OSINTValidation.query.filter_by(
        contact_value=contact.contact_value,
        contact_type=contact.contact_type
    ).order_by(OSINTValidation.validation_date.desc()).all()

    return render_template('osint/detail.html',
                          case=case,
                          contact=contact,
                          validate_form=validate_form,
                          validations=validations)


@osint.route('/<int:contact_id>')
@login_required
def detail_no_case(contact_id):
    """View OSINT contact details (global view)"""
    contact = OSINTContact.query.get_or_404(contact_id)

    if contact.is_deleted:
        flash('Este contacto ha sido eliminado.', 'warning')
        return redirect(url_for('osint.index'))

    # Create validation form
    validate_form = ValidateContactForm()
    validate_form.contact_id.data = contact.id

    # Get validation history for this contact
    validations = OSINTValidation.query.filter_by(
        contact_value=contact.contact_value,
        contact_type=contact.contact_type
    ).order_by(OSINTValidation.validation_date.desc()).all()

    return render_template('osint/detail.html',
                          contact=contact,
                          validate_form=validate_form,
                          validations=validations)


@osint.route('/case/<int:case_id>/<int:contact_id>/edit', methods=['GET', 'POST'])
@login_required
@require_detective()
def edit(case_id, contact_id):
    """Edit an OSINT contact within case context"""
    case = Case.query.get_or_404(case_id)
    contact = OSINTContact.query.get_or_404(contact_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permiso para modificar este caso.', 'danger')
        return redirect(url_for('cases.index'))

    if case.is_deleted or contact.is_deleted:
        flash('El caso o contacto ha sido eliminado.', 'warning')
        return redirect(url_for('cases.index'))

    # Verify contact belongs to case
    if contact.case_id != case_id:
        flash('El contacto no pertenece a este caso.', 'warning')
        return redirect(url_for('osint.case_contacts', case_id=case_id))

    form = OSINTContactForm(obj=contact)

    if form.validate_on_submit():
        try:
            # Update contact
            contact.contact_type = form.contact_type.data
            contact.contact_value = form.contact_value.data
            contact.name = form.name.data
            contact.description = form.description.data
            contact.source = form.source.data
            contact.tags = form.tags.data
            # Case association doesn't change

            db.session.commit()

            flash(f'Contacto OSINT "{contact.contact_value}" actualizado exitosamente.', 'success')
            return redirect(url_for('osint.detail', case_id=case_id, contact_id=contact.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el contacto: {str(e)}', 'danger')

    return render_template('osint/form.html',
                          case=case,
                          form=form,
                          title='Editar Contacto OSINT',
                          contact=contact)


@osint.route('/<int:contact_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_no_case(contact_id):
    """Edit an OSINT contact (global view)"""
    contact = OSINTContact.query.get_or_404(contact_id)

    if contact.is_deleted:
        flash('Este contacto ha sido eliminado.', 'warning')
        return redirect(url_for('osint.index'))

    form = OSINTContactForm(obj=contact)

    # Populate case choices
    cases = Case.query.filter_by(is_deleted=False).order_by(Case.created_at.desc()).all()
    form.case_id.choices = [(0, 'Sin caso asociado')] + [(c.id, f"{c.numero_orden} - {c.objeto_investigacion[:50]}") for c in cases]

    if request.method == 'GET':
        # Pre-populate form
        form.case_id.data = contact.case_id if contact.case_id else 0

    if form.validate_on_submit():
        try:
            # Update contact
            contact.contact_type = form.contact_type.data
            contact.contact_value = form.contact_value.data
            contact.name = form.name.data
            contact.description = form.description.data
            contact.source = form.source.data
            contact.tags = form.tags.data
            contact.case_id = form.case_id.data if form.case_id.data != 0 else None

            db.session.commit()

            flash(f'Contacto OSINT "{contact.contact_value}" actualizado exitosamente.', 'success')

            # Redirect based on whether it has a case
            if contact.case_id:
                return redirect(url_for('osint.detail', case_id=contact.case_id, contact_id=contact.id))
            else:
                return redirect(url_for('osint.detail_no_case', contact_id=contact.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el contacto: {str(e)}', 'danger')

    return render_template('osint/form.html',
                          form=form,
                          title='Editar Contacto OSINT',
                          contact=contact)


@osint.route('/case/<int:case_id>/<int:contact_id>/delete', methods=['POST'])
@login_required
@require_detective()
def delete(case_id, contact_id):
    """Soft delete an OSINT contact within case context"""
    case = Case.query.get_or_404(case_id)
    contact = OSINTContact.query.get_or_404(contact_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permiso para modificar este caso.', 'danger')
        return redirect(url_for('cases.index'))

    if contact.is_deleted:
        flash('Este contacto ya ha sido eliminado.', 'warning')
        return redirect(url_for('osint.case_contacts', case_id=case_id))

    try:
        contact.soft_delete(current_user.id)
        flash(f'Contacto OSINT "{contact.contact_value}" eliminado exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el contacto: {str(e)}', 'danger')

    return redirect(url_for('osint.case_contacts', case_id=case_id))


@osint.route('/<int:contact_id>/delete', methods=['POST'])
@login_required
def delete_no_case(contact_id):
    """Soft delete an OSINT contact (global view)"""
    contact = OSINTContact.query.get_or_404(contact_id)

    if contact.is_deleted:
        flash('Este contacto ya ha sido eliminado.', 'warning')
        return redirect(url_for('osint.index'))

    try:
        contact.soft_delete(current_user.id)
        flash(f'Contacto OSINT "{contact.contact_value}" eliminado exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el contacto: {str(e)}', 'danger')

    return redirect(url_for('osint.index'))


@osint.route('/case/<int:case_id>/<int:contact_id>/validate', methods=['POST'])
@login_required
@require_detective()
def validate_contact(case_id, contact_id):
    """Validate a contact using IPQualityScore plugin within case context"""
    case = Case.query.get_or_404(case_id)
    contact = OSINTContact.query.get_or_404(contact_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        return jsonify({'success': False, 'error': 'No tiene permiso para modificar este caso.'}), 403

    if contact.is_deleted:
        return jsonify({'success': False, 'error': 'Este contacto ha sido eliminado.'}), 404

    # Check if contact type is supported
    if contact.contact_type not in ['email', 'phone']:
        return jsonify({
            'success': False,
            'error': 'Solo se pueden validar emails y teléfonos con IPQualityScore.'
        }), 400

    try:
        # Get active API key
        api_key = ApiKey.get_active_key('ipqualityscore')
        if not api_key:
            return jsonify({
                'success': False,
                'error': 'No hay una API Key activa configurada para IPQualityScore.'
            }), 400

        # Initialize plugin
        plugin = IPQualityScoreValidatorPlugin()

        # Perform validation
        result = plugin.lookup(contact.contact_value, query_type=contact.contact_type)

        # Create validation record
        validation = OSINTValidation.create_from_plugin_result(
            contact_value=contact.contact_value,
            contact_type=contact.contact_type,
            plugin_result=result,
            user_id=current_user.id,
            case_id=contact.case_id,
            api_key_id=api_key.id,
            notes=request.form.get('notes')
        )

        # Update contact with validation results
        contact.update_from_validation(validation)

        return jsonify({
            'success': True,
            'message': 'Validación completada exitosamente.',
            'validation': validation.to_dict(),
            'summary': validation.get_summary()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error al validar el contacto: {str(e)}'
        }), 500


@osint.route('/<int:contact_id>/validate', methods=['POST'])
@login_required
def validate_contact_no_case(contact_id):
    """Validate a contact using IPQualityScore plugin (global view)"""
    contact = OSINTContact.query.get_or_404(contact_id)

    if contact.is_deleted:
        return jsonify({'success': False, 'error': 'Este contacto ha sido eliminado.'}), 404

    # Check if contact type is supported
    if contact.contact_type not in ['email', 'phone']:
        return jsonify({
            'success': False,
            'error': 'Solo se pueden validar emails y teléfonos con IPQualityScore.'
        }), 400

    try:
        # Get active API key
        api_key = ApiKey.get_active_key('ipqualityscore')
        if not api_key:
            return jsonify({
                'success': False,
                'error': 'No hay una API Key activa configurada para IPQualityScore.'
            }), 400

        # Initialize plugin
        plugin = IPQualityScoreValidatorPlugin()

        # Perform validation
        result = plugin.lookup(contact.contact_value, query_type=contact.contact_type)

        # Create validation record
        validation = OSINTValidation.create_from_plugin_result(
            contact_value=contact.contact_value,
            contact_type=contact.contact_type,
            plugin_result=result,
            user_id=current_user.id,
            case_id=contact.case_id,
            api_key_id=api_key.id,
            notes=request.form.get('notes')
        )

        # Update contact with validation results
        contact.update_from_validation(validation)

        return jsonify({
            'success': True,
            'message': 'Validación completada exitosamente.',
            'validation': validation.to_dict(),
            'summary': validation.get_summary()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error al validar el contacto: {str(e)}'
        }), 500


@osint.route('/case/<int:case_id>/<int:contact_id>/archive', methods=['POST'])
@login_required
@require_detective()
def archive(case_id, contact_id):
    """Archive a contact within case context"""
    case = Case.query.get_or_404(case_id)
    contact = OSINTContact.query.get_or_404(contact_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permiso para modificar este caso.', 'danger')
        return redirect(url_for('cases.index'))

    if contact.is_deleted:
        flash('Este contacto ha sido eliminado.', 'warning')
        return redirect(url_for('osint.case_contacts', case_id=case_id))

    try:
        contact.status = 'archived' if contact.status == 'active' else 'active'
        db.session.commit()

        status_text = 'archivado' if contact.status == 'archived' else 'activado'
        flash(f'Contacto "{contact.contact_value}" {status_text} exitosamente.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error al cambiar el estado: {str(e)}', 'danger')

    return redirect(url_for('osint.detail', case_id=case_id, contact_id=contact.id))


@osint.route('/<int:contact_id>/archive', methods=['POST'])
@login_required
def archive_no_case(contact_id):
    """Archive a contact (global view)"""
    contact = OSINTContact.query.get_or_404(contact_id)

    if contact.is_deleted:
        flash('Este contacto ha sido eliminado.', 'warning')
        return redirect(url_for('osint.index'))

    try:
        contact.status = 'archived' if contact.status == 'active' else 'active'
        db.session.commit()

        status_text = 'archivado' if contact.status == 'archived' else 'activado'
        flash(f'Contacto "{contact.contact_value}" {status_text} exitosamente.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error al cambiar el estado: {str(e)}', 'danger')

    # Redirect based on whether it has a case
    if contact.case_id:
        return redirect(url_for('osint.detail', case_id=contact.case_id, contact_id=contact.id))
    else:
        return redirect(url_for('osint.detail_no_case', contact_id=contact.id))


@osint.route('/validation/<int:validation_id>')
@login_required
def validation_detail(validation_id):
    """View validation details"""
    validation = OSINTValidation.query.get_or_404(validation_id)

    return render_template('osint/validation_detail.html', validation=validation)


@osint.route('/export')
@login_required
def export():
    """Export OSINT contacts to CSV"""
    # This will be implemented later with proper CSV export
    flash('Funcionalidad de exportación en desarrollo.', 'info')
    return redirect(url_for('osint.index'))


@osint.route('/case/<int:case_id>')
@login_required
@require_detective()
def case_contacts(case_id):
    """View all OSINT contacts for a specific case"""
    case = Case.query.get_or_404(case_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permiso para ver este caso.', 'danger')
        return redirect(url_for('cases.index'))

    if case.is_deleted:
        flash('Este caso ha sido eliminado.', 'warning')
        return redirect(url_for('cases.index'))

    # Get search form
    search_form = SearchContactForm(request.args)

    # Build query
    query = OSINTContact.query.filter_by(case_id=case_id, is_deleted=False)

    # Apply filters
    if search_form.search_term.data:
        search_term = search_form.search_term.data
        search_pattern = f'%{search_term}%'
        query = query.filter(
            db.or_(
                OSINTContact.contact_value.ilike(search_pattern),
                OSINTContact.name.ilike(search_pattern),
                OSINTContact.description.ilike(search_pattern),
                OSINTContact.tags.ilike(search_pattern)
            )
        )

    if search_form.contact_type.data:
        query = query.filter_by(contact_type=search_form.contact_type.data)

    if search_form.status.data:
        query = query.filter_by(status=search_form.status.data)

    if search_form.validation_status.data:
        if search_form.validation_status.data == 'validated':
            query = query.filter_by(is_validated=True)
        elif search_form.validation_status.data == 'not_validated':
            query = query.filter_by(is_validated=False)

    contacts = query.order_by(OSINTContact.created_at.desc()).all()

    # Calculate case-specific stats
    stats = {
        'total': OSINTContact.query.filter_by(case_id=case_id, is_deleted=False).count(),
        'validated': OSINTContact.query.filter_by(case_id=case_id, is_deleted=False, is_validated=True).count(),
        'high_risk': OSINTContact.query.filter_by(
            case_id=case_id,
            is_deleted=False,
            is_validated=True
        ).filter(
            db.or_(
                OSINTContact.risk_level == 'high',
                OSINTContact.risk_level == 'very_high'
            )
        ).count(),
        'by_type': {}
    }

    for contact_type in ['email', 'phone', 'social_profile', 'username', 'other']:
        stats['by_type'][contact_type] = OSINTContact.query.filter_by(
            case_id=case_id,
            is_deleted=False,
            contact_type=contact_type
        ).count()

    return render_template('osint/case_contacts.html',
                          case=case,
                          contacts=contacts,
                          search_form=search_form,
                          stats=stats)
