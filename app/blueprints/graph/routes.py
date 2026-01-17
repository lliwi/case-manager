"""
Graph routes for relationship visualization.
"""
from flask import render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from app.blueprints.graph import graph_bp
from app.blueprints.graph.forms import (
    PersonNodeForm, CompanyNodeForm, PhoneNodeForm, EmailNodeForm,
    VehicleNodeForm, AddressNodeForm, SocialProfileNodeForm,
    RelationshipForm, GraphSearchForm
)
from app.models.case import Case
from app.models.graph import (
    NodeType, RelationshipType, PersonNode, CompanyNode, PhoneNode,
    EmailNode, VehicleNode, AddressNode, SocialProfileNode, GraphRelationship,
    EvidenceNode, OsintContactNode
)
from app.models.evidence import Evidence
from app.models.osint_contact import OSINTContact
import json
from app.services.graph_service import GraphService
from app.services.legitimacy_service import LegitimacyService
from app.utils.decorators import require_detective, audit_action
from datetime import datetime


@graph_bp.route('/case/<int:case_id>')
@login_required
@require_detective()
def case_graph(case_id):
    """View the investigation graph for a case."""
    case = Case.query.get_or_404(case_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permiso para ver este caso.', 'danger')
        return redirect(url_for('cases.index'))

    # Get graph statistics
    graph_service = GraphService()
    try:
        stats = graph_service.get_graph_statistics(case_id)
    except Exception as e:
        flash(f'Error al conectar con Neo4j: {str(e)}', 'danger')
        stats = {'total_nodes': 0, 'total_relationships': 0, 'node_types': {}}

    search_form = GraphSearchForm()

    return render_template(
        'graph/view.html',
        case=case,
        stats=stats,
        search_form=search_form
    )


@graph_bp.route('/case/<int:case_id>/nodes/create/<node_type>', methods=['GET', 'POST'])
@login_required
@require_detective()
@audit_action('GRAPH_NODE_CREATE', 'graph')
def create_node(case_id, node_type):
    """Create a new node in the graph."""
    case = Case.query.get_or_404(case_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permiso para modificar este caso.', 'danger')
        return redirect(url_for('cases.index'))

    # Select appropriate form based on node type
    form_classes = {
        'person': PersonNodeForm,
        'company': CompanyNodeForm,
        'phone': PhoneNodeForm,
        'email': EmailNodeForm,
        'vehicle': VehicleNodeForm,
        'address': AddressNodeForm,
        'social': SocialProfileNodeForm
    }

    form_class = form_classes.get(node_type)
    if not form_class:
        flash('Tipo de nodo no válido.', 'danger')
        return redirect(url_for('graph.case_graph', case_id=case_id))

    form = form_class()

    if form.validate_on_submit():
        try:
            # Prepare properties
            properties = {key: value for key, value in form.data.items()
                         if key not in ['csrf_token', 'submit'] and value}

            # Create appropriate node
            if node_type == 'person':
                # Validate DNI if provided
                if properties.get('dni_cif'):
                    validation = LegitimacyService.validate_dni_cif(properties['dni_cif'])
                    if not validation['valid']:
                        flash(f'DNI/NIE no válido: {validation["message"]}', 'danger')
                        return render_template('graph/create_node.html', case=case, form=form, node_type=node_type)

                node = PersonNode(
                    name=properties.get('name'),
                    dni_cif=properties.get('dni_cif'),
                    birth_date=properties.get('birth_date'),
                    properties=properties
                )
            elif node_type == 'company':
                node = CompanyNode(
                    name=properties.get('name'),
                    cif=properties.get('cif'),
                    properties=properties
                )
            elif node_type == 'phone':
                node = PhoneNode(
                    number=properties.get('number'),
                    carrier=properties.get('carrier'),
                    properties=properties
                )
            elif node_type == 'email':
                node = EmailNode(
                    address=properties.get('address'),
                    provider=properties.get('provider'),
                    properties=properties
                )
            elif node_type == 'vehicle':
                node = VehicleNode(
                    plate=properties.get('plate'),
                    make=properties.get('make'),
                    model=properties.get('model'),
                    properties=properties
                )
            elif node_type == 'address':
                node = AddressNode(
                    street=properties.get('street'),
                    city=properties.get('city'),
                    postal_code=properties.get('postal_code'),
                    properties=properties
                )
            elif node_type == 'social':
                node = SocialProfileNode(
                    platform=properties.get('platform'),
                    username=properties.get('username'),
                    url=properties.get('url'),
                    properties=properties
                )

            # Create node in Neo4j
            graph_service = GraphService()
            node_id = graph_service.create_node(node, case_id)

            flash(f'Nodo creado correctamente (ID: {node_id}).', 'success')
            return redirect(url_for('graph.case_graph', case_id=case_id))

        except Exception as e:
            flash(f'Error al crear nodo: {str(e)}', 'danger')

    return render_template(
        'graph/create_node.html',
        case=case,
        form=form,
        node_type=node_type
    )


@graph_bp.route('/case/<int:case_id>/relationships/create', methods=['GET', 'POST'])
@login_required
@require_detective()
@audit_action('GRAPH_RELATIONSHIP_CREATE', 'graph')
def create_relationship(case_id):
    """Create a relationship between two nodes."""
    case = Case.query.get_or_404(case_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permiso para modificar este caso.', 'danger')
        return redirect(url_for('cases.index'))

    form = RelationshipForm()

    # Get node IDs from query parameters if provided
    if request.method == 'GET':
        from_node = request.args.get('from_node')
        to_node = request.args.get('to_node')
        if from_node:
            form.from_node_id.data = from_node
        if to_node:
            form.to_node_id.data = to_node

    if form.validate_on_submit():
        try:
            # Prepare relationship properties
            properties = {
                'confidence': float(form.confidence.data) if form.confidence.data else 1.0,
                'notes': form.notes.data
            }

            if form.start_date.data:
                properties['start_date'] = form.start_date.data.isoformat()
            if form.end_date.data:
                properties['end_date'] = form.end_date.data.isoformat()

            # Determine if relationship type is base or custom
            relationship_type_value = form.relationship_type.data

            # Try to convert to enum if it's a base type
            try:
                relationship_type = RelationshipType(relationship_type_value)
            except ValueError:
                # It's a custom type, use the string directly
                relationship_type = relationship_type_value

            # Create relationship
            relationship = GraphRelationship(
                relationship_id=None,
                relationship_type=relationship_type,
                from_node_id=form.from_node_id.data,
                to_node_id=form.to_node_id.data,
                properties=properties
            )

            # Create in Neo4j
            graph_service = GraphService()
            rel_id = graph_service.create_relationship(relationship)

            flash(f'Relación creada correctamente (ID: {rel_id}).', 'success')
            return redirect(url_for('graph.case_graph', case_id=case_id))

        except Exception as e:
            flash(f'Error al crear relación: {str(e)}', 'danger')

    return render_template(
        'graph/create_relationship.html',
        case=case,
        form=form
    )


@graph_bp.route('/node/<node_id>/delete', methods=['POST'])
@login_required
@require_detective()
@audit_action('GRAPH_NODE_DELETE', 'graph')
def delete_node(node_id):
    """Delete a node from the graph."""
    # Get case_id and node_type from request
    case_id = request.form.get('case_id')
    node_type_str = request.form.get('node_type')

    if not case_id or not node_type_str:
        flash('Parámetros inválidos.', 'danger')
        return redirect(url_for('cases.index'))

    case = Case.query.get_or_404(case_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permiso para modificar este caso.', 'danger')
        return redirect(url_for('cases.index'))

    try:
        node_type = NodeType(node_type_str)
        graph_service = GraphService()
        success = graph_service.delete_node(node_id, node_type)

        if success:
            flash('Nodo eliminado correctamente.', 'success')
        else:
            flash('No se pudo eliminar el nodo.', 'warning')

    except Exception as e:
        flash(f'Error al eliminar nodo: {str(e)}', 'danger')

    return redirect(url_for('graph.case_graph', case_id=case_id))


@graph_bp.route('/api/node/<node_id>/update', methods=['POST'])
@login_required
@require_detective()
@audit_action('GRAPH_NODE_UPDATE', 'graph')
def api_update_node(node_id):
    """API endpoint to update a node's properties."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    case_id = data.get('case_id')
    node_type_str = data.get('node_type')
    properties = data.get('properties', {})

    if not case_id or not node_type_str:
        return jsonify({'error': 'Missing required parameters: case_id, node_type'}), 400

    case = Case.query.get_or_404(case_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        return jsonify({'error': 'No tiene permiso para modificar este caso'}), 403

    try:
        node_type = NodeType(node_type_str)
        graph_service = GraphService()

        # Update the node
        success = graph_service.update_node(node_id, node_type, properties)

        if success:
            return jsonify({
                'success': True,
                'message': 'Nodo actualizado correctamente',
                'node_id': node_id
            })
        else:
            return jsonify({'error': 'No se pudo actualizar el nodo'}), 500

    except ValueError as e:
        return jsonify({'error': f'Tipo de nodo no válido: {node_type_str}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@graph_bp.route('/api/node/<node_id>/delete', methods=['POST'])
@login_required
@require_detective()
@audit_action('GRAPH_NODE_DELETE', 'graph')
def api_delete_node(node_id):
    """API endpoint to delete a node from the graph."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    case_id = data.get('case_id')
    node_type_str = data.get('node_type')

    if not case_id or not node_type_str:
        return jsonify({'error': 'Missing required parameters: case_id, node_type'}), 400

    case = Case.query.get_or_404(case_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        return jsonify({'error': 'No tiene permiso para modificar este caso'}), 403

    try:
        node_type = NodeType(node_type_str)
        graph_service = GraphService()
        success = graph_service.delete_node(node_id, node_type)

        if success:
            return jsonify({
                'success': True,
                'message': 'Nodo eliminado correctamente',
                'node_id': node_id
            })
        else:
            return jsonify({'error': 'No se pudo eliminar el nodo'}), 500

    except ValueError as e:
        return jsonify({'error': f'Tipo de nodo no válido: {node_type_str}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@graph_bp.route('/api/relationship/<relationship_id>/update', methods=['POST'])
@login_required
@require_detective()
@audit_action('GRAPH_RELATIONSHIP_UPDATE', 'graph')
def api_update_relationship(relationship_id):
    """API endpoint to update a relationship's properties."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    case_id = data.get('case_id')
    properties = data.get('properties', {})

    if not case_id:
        return jsonify({'error': 'Missing required parameter: case_id'}), 400

    case = Case.query.get_or_404(case_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        return jsonify({'error': 'No tiene permiso para modificar este caso'}), 403

    try:
        graph_service = GraphService()

        # Update the relationship
        success = graph_service.update_relationship(relationship_id, properties)

        if success:
            return jsonify({
                'success': True,
                'message': 'Relación actualizada correctamente',
                'relationship_id': relationship_id
            })
        else:
            return jsonify({'error': 'No se pudo actualizar la relación'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@graph_bp.route('/api/relationship/<relationship_id>/delete', methods=['POST'])
@login_required
@require_detective()
@audit_action('GRAPH_RELATIONSHIP_DELETE', 'graph')
def api_delete_relationship(relationship_id):
    """API endpoint to delete a relationship from the graph."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    case_id = data.get('case_id')

    if not case_id:
        return jsonify({'error': 'Missing required parameter: case_id'}), 400

    case = Case.query.get_or_404(case_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        return jsonify({'error': 'No tiene permiso para modificar este caso'}), 403

    try:
        graph_service = GraphService()
        success = graph_service.delete_relationship(relationship_id)

        if success:
            return jsonify({
                'success': True,
                'message': 'Relación eliminada correctamente',
                'relationship_id': relationship_id
            })
        else:
            return jsonify({'error': 'No se pudo eliminar la relación'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@graph_bp.route('/relationship/<relationship_id>/delete', methods=['POST'])
@login_required
@require_detective()
@audit_action('GRAPH_RELATIONSHIP_DELETE', 'graph')
def delete_relationship(relationship_id):
    """Delete a relationship from the graph (form-based, legacy)."""
    case_id = request.form.get('case_id')

    if not case_id:
        flash('Parámetros inválidos.', 'danger')
        return redirect(url_for('cases.index'))

    case = Case.query.get_or_404(case_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permiso para modificar este caso.', 'danger')
        return redirect(url_for('cases.index'))

    try:
        graph_service = GraphService()
        success = graph_service.delete_relationship(relationship_id)

        if success:
            flash('Relación eliminada correctamente.', 'success')
        else:
            flash('No se pudo eliminar la relación.', 'warning')

    except Exception as e:
        flash(f'Error al eliminar relación: {str(e)}', 'danger')

    return redirect(url_for('graph.case_graph', case_id=case_id))


# API Endpoints for AJAX/Graph Visualization

@graph_bp.route('/api/case/<int:case_id>/graph-data')
@login_required
@require_detective()
def api_graph_data(case_id):
    """API endpoint to get graph data for visualization."""
    case = Case.query.get_or_404(case_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        abort(403)

    try:
        graph_service = GraphService()
        graph_data = graph_service.get_case_graph(case_id)

        # Format for vis.js
        vis_data = {
            'nodes': [],
            'edges': []
        }

        # Node colors by type
        node_colors = {
            'Person': '#3498db',      # Blue
            'Company': '#e74c3c',     # Red
            'Phone': '#2ecc71',       # Green
            'Email': '#f39c12',       # Orange
            'Vehicle': '#9b59b6',     # Purple
            'Address': '#1abc9c',     # Turquoise
            'Evidence': '#34495e',    # Dark gray
            'SocialProfile': '#e67e22', # Carrot orange
            'OsintContact': '#16a085',  # Sea green
            'BankAccount': '#8e44ad',   # Wisteria purple
            'IpAddress': '#2c3e50'      # Midnight blue
        }

        # Convert nodes to vis.js format
        for node in graph_data['nodes']:
            label_text = ''
            if node['label'] == 'Person':
                label_text = node['properties'].get('name', 'Persona')
            elif node['label'] == 'Company':
                label_text = node['properties'].get('name', 'Empresa')
            elif node['label'] == 'Phone':
                label_text = node['properties'].get('number', 'Teléfono')
            elif node['label'] == 'Email':
                label_text = node['properties'].get('address', 'Email')
            elif node['label'] == 'Vehicle':
                label_text = node['properties'].get('plate', 'Vehículo')
            elif node['label'] == 'Address':
                label_text = node['properties'].get('city', 'Dirección')
            elif node['label'] == 'SocialProfile':
                label_text = f"{node['properties'].get('platform', '')}: {node['properties'].get('username', '')}"
            elif node['label'] == 'Evidence':
                label_text = node['properties'].get('filename', 'Evidencia')
            elif node['label'] == 'OsintContact':
                label_text = node['properties'].get('name', node['properties'].get('identifier', 'Contacto OSINT'))
            elif node['label'] == 'BankAccount':
                label_text = node['properties'].get('iban', 'Cuenta Bancaria')
            elif node['label'] == 'IpAddress':
                label_text = node['properties'].get('ip', 'Dirección IP')
            else:
                label_text = node['label']

            vis_data['nodes'].append({
                'id': node['id'],
                'label': label_text,
                'group': node['label'],
                'color': node_colors.get(node['label'], '#95a5a6'),
                'title': f"{node['label']}<br>{label_text}",  # Tooltip
                'properties': node['properties']
            })

        # Convert relationships to vis.js edges
        for rel in graph_data['relationships']:
            vis_data['edges'].append({
                'id': rel['id'],
                'from': rel['from'],
                'to': rel['to'],
                'label': rel['type'].replace('_', ' '),
                'arrows': 'to',
                'title': rel['type'],  # Tooltip
                'properties': rel.get('properties', {})
            })

        return jsonify(vis_data)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@graph_bp.route('/api/case/<int:case_id>/search')
@login_required
@require_detective()
def api_search_nodes(case_id):
    """API endpoint to search nodes."""
    case = Case.query.get_or_404(case_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        abort(403)

    query = request.args.get('query', '')
    node_type_str = request.args.get('node_type')

    try:
        node_type = NodeType(node_type_str) if node_type_str else None
        graph_service = GraphService()

        # If no query, return all nodes from the case (limit to first 50)
        if not query or query.strip() == '':
            # Get all nodes from case
            graph_data = graph_service.get_case_graph(case_id)
            results = graph_data['nodes'][:50]  # Limit to first 50 nodes
        else:
            # Search with query
            results = graph_service.search_nodes(case_id, query, node_type)

        return jsonify(results)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@graph_bp.route('/api/node/<node_id>/relationships')
@login_required
@require_detective()
def api_node_relationships(node_id):
    """API endpoint to get relationships for a node."""
    try:
        graph_service = GraphService()
        relationships = graph_service.get_relationships(node_id)

        return jsonify([rel.to_dict() for rel in relationships])

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@graph_bp.route('/api/shortest-path')
@login_required
@require_detective()
def api_shortest_path():
    """API endpoint to find shortest path between two nodes."""
    from_node = request.args.get('from')
    to_node = request.args.get('to')

    if not from_node or not to_node:
        return jsonify({'error': 'Missing parameters'}), 400

    try:
        graph_service = GraphService()
        path = graph_service.find_shortest_path(from_node, to_node)

        if path:
            return jsonify(path)
        else:
            return jsonify({'message': 'No path found'}), 404

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@graph_bp.route('/api/common-connections')
@login_required
@require_detective()
def api_common_connections():
    """API endpoint to find common connections between two nodes."""
    node_1 = request.args.get('node1')
    node_2 = request.args.get('node2')

    if not node_1 or not node_2:
        return jsonify({'error': 'Missing parameters'}), 400

    try:
        graph_service = GraphService()
        common = graph_service.find_common_connections(node_1, node_2)

        return jsonify(common)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# Case Elements Import API
# =============================================================================

@graph_bp.route('/api/case/<int:case_id>/case-elements')
@login_required
@require_detective()
def api_case_elements(case_id):
    """API endpoint to get all case elements available for import to graph."""
    case = Case.query.get_or_404(case_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        abort(403)

    try:
        # Get evidences
        evidences = Evidence.query.filter_by(
            case_id=case_id,
            is_deleted=False
        ).all()

        evidences_data = [{
            'id': e.id,
            'type': 'evidence',
            'name': e.original_filename,
            'evidence_type': e.evidence_type.value if e.evidence_type else 'Otros',
            'description': e.description,
            'sha256_hash': e.sha256_hash[:16] + '...' if e.sha256_hash else None,
            'uploaded_at': e.uploaded_at.isoformat() if e.uploaded_at else None,
            'has_node': bool(e.neo4j_node_id)
        } for e in evidences]

        # Get OSINT contacts
        contacts = OSINTContact.get_active_contacts(case_id=case_id).all()

        contacts_data = [{
            'id': c.id,
            'type': 'osint_contact',
            'name': c.name or c.contact_value,
            'contact_type': c.contact_type,
            'contact_value': c.contact_value,
            'risk_level': c.risk_level,
            'is_validated': c.is_validated,
            'extra_data': c.extra_data
        } for c in contacts]

        # Get sujetos (subjects) from case
        sujetos_data = []
        sujeto_nombres = []
        sujeto_dnis = []

        # Parse JSON arrays
        if case.sujeto_nombres:
            try:
                sujeto_nombres = json.loads(case.sujeto_nombres) if isinstance(case.sujeto_nombres, str) else case.sujeto_nombres
            except (json.JSONDecodeError, TypeError):
                sujeto_nombres = [case.sujeto_nombres] if case.sujeto_nombres else []

        if case.sujeto_dni_nie:
            try:
                sujeto_dnis = json.loads(case.sujeto_dni_nie) if isinstance(case.sujeto_dni_nie, str) else case.sujeto_dni_nie
            except (json.JSONDecodeError, TypeError):
                sujeto_dnis = [case.sujeto_dni_nie] if case.sujeto_dni_nie else []

        # Build sujetos list
        for i, nombre in enumerate(sujeto_nombres):
            if nombre:
                sujetos_data.append({
                    'id': f'sujeto_{i}',
                    'type': 'sujeto',
                    'name': nombre,
                    'dni_nie': sujeto_dnis[i] if i < len(sujeto_dnis) else None,
                    'index': i
                })

        return jsonify({
            'evidences': evidences_data,
            'contacts': contacts_data,
            'sujetos': sujetos_data,
            'counts': {
                'evidences': len(evidences_data),
                'contacts': len(contacts_data),
                'sujetos': len(sujetos_data)
            }
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@graph_bp.route('/api/case/<int:case_id>/import-elements', methods=['POST'])
@login_required
@require_detective()
@audit_action('GRAPH_IMPORT_ELEMENTS', 'graph')
def api_import_elements(case_id):
    """API endpoint to import case elements as graph nodes."""
    case = Case.query.get_or_404(case_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        abort(403)

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    elements = data.get('elements', [])
    if not elements:
        return jsonify({'error': 'No elements to import'}), 400

    graph_service = GraphService()
    results = {
        'created': [],
        'skipped': [],
        'errors': []
    }

    for element in elements:
        element_type = element.get('type')
        element_id = element.get('id')

        try:
            if element_type == 'evidence':
                # Convert ID to int if it's a string
                try:
                    evidence_id = int(element_id)
                except (ValueError, TypeError):
                    results['errors'].append({
                        'id': element_id,
                        'type': element_type,
                        'error': f'ID de evidencia inválido: {element_id}'
                    })
                    continue

                evidence = Evidence.query.get(evidence_id)
                if not evidence or evidence.case_id != case_id:
                    results['errors'].append({
                        'id': element_id,
                        'type': element_type,
                        'error': 'Evidencia no encontrada'
                    })
                    continue

                # Check if already has node
                if evidence.neo4j_node_id:
                    results['skipped'].append({
                        'id': element_id,
                        'type': element_type,
                        'reason': 'Ya existe nodo para esta evidencia',
                        'existing_node_id': evidence.neo4j_node_id
                    })
                    continue

                # Create evidence node
                node = EvidenceNode(
                    evidence_id=evidence.id,
                    filename=evidence.original_filename,
                    evidence_type=evidence.evidence_type.value if evidence.evidence_type else 'Otros',
                    properties={
                        'description': evidence.description,
                        'sha256_hash': evidence.sha256_hash,
                        'mime_type': evidence.mime_type,
                        'file_size': evidence.file_size,
                        'uploaded_at': evidence.uploaded_at.isoformat() if evidence.uploaded_at else None,
                        'source': 'case_import'
                    }
                )

                node_id = graph_service.create_node(node, case_id)

                # Update evidence with neo4j_node_id
                evidence.neo4j_node_id = node_id
                from app.extensions import db
                db.session.commit()

                results['created'].append({
                    'id': element_id,
                    'type': element_type,
                    'node_id': node_id,
                    'label': evidence.original_filename
                })

            elif element_type == 'osint_contact':
                # Convert ID to int if it's a string
                try:
                    contact_id = int(element_id)
                except (ValueError, TypeError):
                    results['errors'].append({
                        'id': element_id,
                        'type': element_type,
                        'error': f'ID de contacto inválido: {element_id}'
                    })
                    continue

                contact = OSINTContact.query.get(contact_id)
                if not contact or contact.case_id != case_id:
                    results['errors'].append({
                        'id': element_id,
                        'type': element_type,
                        'error': 'Contacto no encontrado'
                    })
                    continue

                # Determine node type based on contact type
                if contact.contact_type == 'email':
                    node = EmailNode(
                        address=contact.contact_value,
                        properties={
                            'osint_contact_id': contact.id,
                            'name': contact.name,
                            'is_validated': contact.is_validated,
                            'risk_level': contact.risk_level,
                            'source': 'osint_contact'
                        }
                    )
                elif contact.contact_type == 'phone':
                    node = PhoneNode(
                        number=contact.contact_value,
                        properties={
                            'osint_contact_id': contact.id,
                            'name': contact.name,
                            'is_validated': contact.is_validated,
                            'risk_level': contact.risk_level,
                            'source': 'osint_contact'
                        }
                    )
                elif contact.contact_type == 'social_profile':
                    # Extract platform from extra_data if available
                    platform = 'Unknown'
                    extra = contact.extra_data or {}
                    if 'instagram_profile' in extra:
                        platform = 'Instagram'
                    elif 'x_profile' in extra or 'twitter_profile' in extra:
                        platform = 'X/Twitter'

                    node = SocialProfileNode(
                        platform=platform,
                        username=contact.contact_value,
                        properties={
                            'osint_contact_id': contact.id,
                            'name': contact.name,
                            'is_validated': contact.is_validated,
                            'extra_data': extra,
                            'source': 'osint_contact'
                        }
                    )
                else:
                    # Generic OSINT contact node
                    node = OsintContactNode(
                        contact_id=contact.id,
                        name=contact.name or contact.contact_value,
                        identifier=contact.contact_value,
                        contact_type=contact.contact_type,
                        properties={
                            'is_validated': contact.is_validated,
                            'risk_level': contact.risk_level,
                            'source': 'osint_contact'
                        }
                    )

                node_id = graph_service.create_node(node, case_id)

                results['created'].append({
                    'id': element_id,
                    'type': element_type,
                    'node_id': node_id,
                    'label': contact.name or contact.contact_value
                })

            elif element_type == 'sujeto':
                # Sujetos don't have database IDs, use index
                sujeto_index = element.get('index', 0)
                sujeto_name = element.get('name')
                sujeto_dni = element.get('dni_nie')

                if not sujeto_name:
                    results['errors'].append({
                        'id': element_id,
                        'type': element_type,
                        'error': 'Nombre de sujeto no proporcionado'
                    })
                    continue

                node = PersonNode(
                    name=sujeto_name,
                    dni_cif=sujeto_dni,
                    properties={
                        'role': 'Sujeto investigado',
                        'sujeto_index': sujeto_index,
                        'source': 'case_sujeto'
                    }
                )

                node_id = graph_service.create_node(node, case_id)

                results['created'].append({
                    'id': element_id,
                    'type': element_type,
                    'node_id': node_id,
                    'label': sujeto_name
                })

            else:
                results['errors'].append({
                    'id': element_id,
                    'type': element_type,
                    'error': f'Tipo de elemento no soportado: {element_type}'
                })

        except Exception as e:
            results['errors'].append({
                'id': element_id,
                'type': element_type,
                'error': str(e)
            })

    return jsonify({
        'success': True,
        'results': results,
        'summary': {
            'created': len(results['created']),
            'skipped': len(results['skipped']),
            'errors': len(results['errors'])
        }
    })
