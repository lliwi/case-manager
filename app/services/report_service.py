"""
Report Service for generating forensic investigation reports.

Handles PDF generation, digital signatures, and report management.
"""
from app.models.report import Report, ReportType, ReportStatus
from app.models.case import Case
from app.models.evidence import Evidence
from app.models.timeline import TimelineEvent
from app.models.audit import AuditLog
from app.models.user import User
from app.models.evidence_analysis import EvidenceAnalysis
from app.extensions import db
from app.utils.hashing import calculate_file_hashes
from app.services.graph_service import GraphService
from flask import current_app
from datetime import datetime
import os
import json
import tempfile

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
        Image as RLImage
    )
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    import networkx as nx
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    import matplotlib.pyplot as plt
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False


class ReportService:
    """Service for report generation and management."""

    @staticmethod
    def create_report(case_id, created_by_id, report_type, title, **kwargs):
        """
        Create a new report.

        Args:
            case_id: Case ID
            created_by_id: User ID creating the report
            report_type: ReportType enum
            title: Report title
            **kwargs: Additional report fields

        Returns:
            Report instance
        """
        report = Report(
            case_id=case_id,
            created_by_id=created_by_id,
            report_type=report_type,
            title=title,
            description=kwargs.get('description'),
            introduction=kwargs.get('introduction'),
            methodology=kwargs.get('methodology'),
            findings=kwargs.get('findings'),
            conclusions=kwargs.get('conclusions'),
            recommendations=kwargs.get('recommendations'),
            include_evidence_list=kwargs.get('include_evidence_list', True),
            include_timeline=kwargs.get('include_timeline', True),
            include_graph=kwargs.get('include_graph', False),
            include_chain_of_custody=kwargs.get('include_chain_of_custody', True),
            include_plugin_results=kwargs.get('include_plugin_results', False),
            include_evidence_thumbnails=kwargs.get('include_evidence_thumbnails', False),
            status=ReportStatus.DRAFT
        )

        db.session.add(report)
        db.session.commit()

        # Log creation
        user = User.query.get(created_by_id)
        if user:
            AuditLog.log(
                action='REPORT_CREATED',
                resource_type='report',
                resource_id=report.id,
                user=user,
                extra_data={
                    'case_id': case_id,
                    'report_type': report_type.value,
                    'title': title
                }
            )

        return report

    @staticmethod
    def generate_pdf(report_id, user_id):
        """
        Generate PDF for a report.

        Args:
            report_id: Report ID
            user_id: User ID requesting generation

        Returns:
            dict: Generation result
        """
        if not REPORTLAB_AVAILABLE:
            return {
                'success': False,
                'error': 'ReportLab library not available'
            }

        report = Report.query.get(report_id)
        if not report:
            return {
                'success': False,
                'error': 'Report not found'
            }

        # Update status
        report.status = ReportStatus.GENERATING
        db.session.commit()

        try:
            # Generate PDF
            pdf_path = ReportService._create_pdf_document(report)

            # Calculate file size and hashes
            file_size = os.path.getsize(pdf_path)
            hashes = calculate_file_hashes(pdf_path)

            # Update report
            report.mark_as_generated(
                file_path=pdf_path,
                file_size=file_size,
                sha256_hash=hashes['sha256'],
                sha512_hash=hashes['sha512']
            )

            # Log generation
            user = User.query.get(user_id)
            if user:
                AuditLog.log(
                    action='REPORT_GENERATED',
                    resource_type='report',
                    resource_id=report.id,
                    user=user,
                    extra_data={
                        'file_size': file_size,
                        'sha256': hashes['sha256']
                    }
                )

            return {
                'success': True,
                'report_id': report.id,
                'file_path': pdf_path,
                'file_size': file_size,
                'sha256': hashes['sha256']
            }

        except Exception as e:
            report.status = ReportStatus.FAILED
            db.session.commit()

            return {
                'success': False,
                'error': str(e)
            }

    @staticmethod
    def _generate_graph_image(graph_data):
        """
        Generate a visualization image of the graph.

        Args:
            graph_data: Dictionary with 'nodes' and 'relationships'

        Returns:
            str: Path to temporary image file, or None if generation fails
        """
        if not NETWORKX_AVAILABLE:
            current_app.logger.warning('NetworkX not available for graph visualization')
            return None

        if not graph_data.get('nodes'):
            current_app.logger.warning('No nodes in graph data')
            return None

        try:
            current_app.logger.info(f'Generating graph image with {len(graph_data["nodes"])} nodes')

            # Create NetworkX graph
            G = nx.DiGraph()

            # Node colors by type
            node_colors_map = {
                'Person': '#FF6B6B',
                'Company': '#4ECDC4',
                'Phone': '#45B7D1',
                'Email': '#96CEB4',
                'Vehicle': '#FFEAA7',
                'Address': '#DFE6E9',
                'SocialProfile': '#A29BFE',
                'Evidence': '#FD79A8'
            }

            # Add nodes
            node_labels = {}
            node_colors = []
            for node in graph_data['nodes']:
                node_id = node['id']
                props = node['properties']
                label_type = node['label']

                # Extract identifier for label
                identifier = (props.get('name') or
                            props.get('number') or
                            props.get('address') or
                            props.get('plate') or
                            props.get('username') or
                            props.get('dni_cif') or
                            f"ID:{node_id}")

                G.add_node(node_id, label=label_type)
                node_labels[node_id] = f"{label_type}\n{str(identifier)[:20]}"
                node_colors.append(node_colors_map.get(label_type, '#B2BEC3'))

            # Add edges
            edge_labels = {}
            for rel in graph_data.get('relationships', []):
                from_id = rel['from']
                to_id = rel['to']
                rel_type = rel['type']

                # Only add edge if both nodes exist
                if from_id in G.nodes and to_id in G.nodes:
                    G.add_edge(from_id, to_id, label=rel_type)
                    edge_labels[(from_id, to_id)] = rel_type

            # Create visualization
            fig = plt.figure(figsize=(12, 8))
            plt.title('Grafo de Relaciones del Caso', fontsize=16, fontweight='bold')

            # Use spring layout for better visualization
            pos = nx.spring_layout(G, k=2, iterations=50, seed=42)

            # Draw nodes
            nx.draw_networkx_nodes(G, pos,
                                 node_color=node_colors,
                                 node_size=2000,
                                 alpha=0.9,
                                 linewidths=2,
                                 edgecolors='black')

            # Draw edges
            if len(G.edges) > 0:
                nx.draw_networkx_edges(G, pos,
                                     edge_color='#636E72',
                                     arrows=True,
                                     arrowsize=20,
                                     width=2,
                                     alpha=0.6,
                                     arrowstyle='->')

            # Draw labels
            nx.draw_networkx_labels(G, pos,
                                  labels=node_labels,
                                  font_size=8,
                                  font_weight='bold',
                                  font_color='black')

            # Draw edge labels
            if edge_labels:
                nx.draw_networkx_edge_labels(G, pos,
                                           edge_labels=edge_labels,
                                           font_size=7,
                                           font_color='#2D3436')

            plt.axis('off')
            plt.tight_layout()

            # Save to temporary file in /tmp (always writable)
            temp_filename = f'graph_temp_{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}.png'
            temp_path = os.path.join('/tmp', temp_filename)

            current_app.logger.info(f'Saving graph image to: {temp_path}')
            plt.savefig(temp_path, format='png', dpi=150, bbox_inches='tight', facecolor='white')
            plt.close(fig)

            # Verify file was created
            if os.path.exists(temp_path):
                file_size = os.path.getsize(temp_path)
                current_app.logger.info(f'Graph image created successfully: {temp_path} ({file_size} bytes)')
                return temp_path
            else:
                current_app.logger.error(f'Graph image file not found after save: {temp_path}')
                return None

        except Exception as e:
            current_app.logger.error(f'Error generating graph image: {e}', exc_info=True)
            try:
                plt.close('all')
            except:
                pass
            return None

    @staticmethod
    def _create_pdf_document(report):
        """
        Create the actual PDF document.

        Args:
            report: Report instance

        Returns:
            str: Path to generated PDF
        """
        # Create reports directory if it doesn't exist
        reports_dir = current_app.config.get('REPORTS_PATH', 'data/reports')
        os.makedirs(reports_dir, exist_ok=True)

        # Generate file path
        filename = report.get_file_name()
        file_path = os.path.join(reports_dir, filename)

        # Create PDF
        doc = SimpleDocTemplate(file_path, pagesize=A4,
                                rightMargin=2*cm, leftMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)

        # Story (content)
        story = []
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
            alignment=TA_CENTER
        )

        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=12,
            spaceBefore=12
        )

        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['BodyText'],
            fontSize=10,
            alignment=TA_JUSTIFY,
            spaceAfter=12
        )

        # Title page
        story.append(Spacer(1, 3*cm))
        story.append(Paragraph(report.get_full_title(), title_style))
        story.append(Spacer(1, 1*cm))

        # Report metadata table
        metadata = [
            ['Caso:', report.case.numero_orden],
            ['Tipo de Informe:', report.report_type.value],
            ['Versión:', f'v{report.version}'],
            ['Fecha de Generación:', datetime.now().strftime('%d/%m/%Y %H:%M:%S')],
            ['Investigador:', report.created_by.nombre],
            ['TIP:', report.created_by.tip_number],
        ]

        metadata_table = Table(metadata, colWidths=[5*cm, 10*cm])
        metadata_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica', 9),
            ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 9),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(metadata_table)
        story.append(PageBreak())

        # Section counter for dynamic numbering
        section_num = 1

        # Introduction
        if report.introduction:
            story.append(Paragraph(f'{section_num}. INTRODUCCIÓN', heading_style))
            story.append(Paragraph(report.introduction, body_style))
            story.append(Spacer(1, 0.5*cm))
            section_num += 1

        # Methodology
        if report.methodology:
            story.append(Paragraph(f'{section_num}. METODOLOGÍA', heading_style))
            story.append(Paragraph(report.methodology, body_style))
            story.append(Spacer(1, 0.5*cm))
            section_num += 1

        # Findings
        if report.findings:
            story.append(Paragraph(f'{section_num}. HALLAZGOS', heading_style))
            story.append(Paragraph(report.findings, body_style))
            story.append(Spacer(1, 0.5*cm))
            section_num += 1

        # Get evidence list (needed for multiple sections)
        evidence_list = Evidence.query.filter_by(
            case_id=report.case_id,
            is_deleted=False
        ).all()

        # Evidence list
        if report.include_evidence_list:
            story.append(PageBreak())
            story.append(Paragraph(f'{section_num}. RELACIÓN DE EVIDENCIAS', heading_style))

            if evidence_list:
                # Create evidence table with basic info
                evidence_data = [['#', 'Tipo', 'Descripción', 'Fecha']]
                for idx, evidence in enumerate(evidence_list, 1):
                    evidence_data.append([
                        str(idx),
                        evidence.evidence_type.value,
                        evidence.description[:60] + '...' if len(evidence.description) > 60 else evidence.description,
                        evidence.uploaded_at.strftime('%d/%m/%Y') if evidence.uploaded_at else '-'
                    ])

                evidence_table = Table(evidence_data, colWidths=[1*cm, 2.5*cm, 9*cm, 2.5*cm])
                evidence_table.setStyle(TableStyle([
                    ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 9),
                    ('FONT', (0, 1), (-1, -1), 'Helvetica', 8),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ]))
                story.append(evidence_table)
                story.append(Spacer(1, 0.3*cm))

                # Add SHA-256 hashes below the table
                story.append(Paragraph('<b>Hashes SHA-256 de Evidencias:</b>', body_style))
                story.append(Spacer(1, 0.2*cm))

                for idx, evidence in enumerate(evidence_list, 1):
                    hash_text = f'<b>[{idx}]</b> <font name="Courier" size="7">{evidence.sha256_hash if evidence.sha256_hash else "N/A"}</font>'
                    story.append(Paragraph(hash_text, body_style))
                    story.append(Spacer(1, 0.1*cm))

                # Add image thumbnails if enabled
                if report.include_evidence_thumbnails:
                    story.append(Spacer(1, 0.5*cm))
                    story.append(Paragraph('<b>Miniaturas de Evidencias (Imágenes):</b>', body_style))
                    story.append(Spacer(1, 0.3*cm))

                    image_evidences = [e for e in evidence_list if e.is_image()]

                    if image_evidences:
                        # Create a grid of thumbnails (2 per row)
                        thumb_data = []
                        thumb_row = []

                        for idx, evidence in enumerate(image_evidences, 1):
                            try:
                                # Get decrypted path
                                img_path = evidence.get_decrypted_path()

                                # Create thumbnail
                                from PIL import Image
                                img = Image.open(img_path)

                                # Resize maintaining aspect ratio
                                img.thumbnail((150, 150), Image.Resampling.LANCZOS)

                                # Save thumbnail to temp
                                thumb_filename = f'thumb_{evidence.id}_{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}.jpg'
                                thumb_path = os.path.join('/tmp', thumb_filename)
                                img.convert('RGB').save(thumb_path, 'JPEG', quality=85)

                                # Add to report
                                thumb_img = RLImage(thumb_path, width=4*cm, height=4*cm, kind='proportional')

                                # Create cell with image and caption
                                cell_content = [
                                    thumb_img,
                                    Paragraph(f'<font size="7">[{idx}] {evidence.original_filename[:20]}...</font>', body_style)
                                ]

                                thumb_row.append(cell_content)

                                # Store for cleanup
                                if not hasattr(report, '_temp_files'):
                                    report._temp_files = []
                                report._temp_files.append(thumb_path)

                                # Clean decrypted temp if different from original
                                if evidence.is_encrypted and img_path != evidence.file_path:
                                    try:
                                        os.remove(img_path)
                                    except:
                                        pass

                                # Add row when we have 2 images or it's the last one
                                if len(thumb_row) == 2 or idx == len(image_evidences):
                                    # Pad row if necessary (add empty cell with Paragraph instead of string)
                                    while len(thumb_row) < 2:
                                        thumb_row.append([Paragraph('', body_style)])
                                    thumb_data.append(thumb_row)
                                    thumb_row = []

                            except Exception as e:
                                current_app.logger.error(f'Error creating thumbnail for evidence {evidence.id}: {e}')
                                continue

                        if thumb_data:
                            # Create table with thumbnails
                            thumb_table = Table(thumb_data, colWidths=[8*cm, 8*cm])
                            thumb_table.setStyle(TableStyle([
                                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                                ('TOPPADDING', (0, 0), (-1, -1), 5),
                                ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
                            ]))
                            story.append(thumb_table)
                    else:
                        story.append(Paragraph('<i>No hay evidencias de tipo imagen.</i>', body_style))

            else:
                story.append(Paragraph('No se encontraron evidencias asociadas.', body_style))

            story.append(Spacer(1, 0.5*cm))
            section_num += 1

        # Timeline
        if report.include_timeline:
            story.append(PageBreak())
            story.append(Paragraph(f'{section_num}. CRONOLOGÍA DE EVENTOS', heading_style))

            timeline_events = TimelineEvent.query.filter_by(
                case_id=report.case_id,
                is_deleted=False
            ).order_by(TimelineEvent.event_date.asc()).all()

            if timeline_events:
                for event in timeline_events[:20]:  # Limit to first 20 events
                    event_text = f"<b>{event.event_date.strftime('%d/%m/%Y %H:%M')}</b> - {event.title}"
                    if event.description:
                        event_text += f": {event.description[:100]}"
                    story.append(Paragraph(event_text, body_style))
            else:
                story.append(Paragraph('No se encontraron eventos en el timeline.', body_style))

            story.append(Spacer(1, 0.5*cm))
            section_num += 1

        # Plugin analysis results
        if report.include_plugin_results:
            story.append(PageBreak())
            story.append(Paragraph('ANEXO A: RESULTADOS DE ANÁLISIS FORENSE', heading_style))

            # Get all analyses for evidence in this case
            if evidence_list:
                evidence_ids = [e.id for e in evidence_list]
                analyses = EvidenceAnalysis.query.filter(
                    EvidenceAnalysis.evidence_id.in_(evidence_ids),
                    EvidenceAnalysis.success == True
                ).order_by(EvidenceAnalysis.analyzed_at.desc()).all()
            else:
                analyses = []

            if analyses:
                for analysis in analyses:
                    # Get evidence info
                    evidence = Evidence.query.get(analysis.evidence_id)

                    story.append(Spacer(1, 0.3*cm))
                    story.append(Paragraph(
                        f'<b>Evidencia:</b> {evidence.original_filename}',
                        body_style
                    ))
                    story.append(Paragraph(
                        f'<b>Plugin:</b> {analysis.plugin_name} (v{analysis.plugin_version or "N/A"})',
                        body_style
                    ))
                    story.append(Paragraph(
                        f'<b>Analista:</b> {analysis.analyzed_by.nombre}',
                        body_style
                    ))
                    story.append(Paragraph(
                        f'<b>Fecha:</b> {analysis.analyzed_at.strftime("%d/%m/%Y %H:%M:%S")}',
                        body_style
                    ))
                    story.append(Spacer(1, 0.2*cm))

                    # Add key results from plugin analysis
                    if analysis.result_data:
                        result_text = '<b>Resultados:</b><br/>'

                        # Format metadata results
                        if 'metadata' in analysis.result_data:
                            metadata = analysis.result_data['metadata']
                            if metadata:
                                result_text += '<br/>Metadatos extraídos:<br/>'
                                for key, value in list(metadata.items())[:10]:  # Limit to first 10 fields
                                    if value:
                                        result_text += f'  • {key}: {str(value)[:100]}<br/>'

                        # Format date info
                        if 'date_info' in analysis.result_data:
                            date_info = analysis.result_data['date_info']
                            if date_info:
                                result_text += '<br/>Información temporal:<br/>'
                                if date_info.get('creation_date'):
                                    result_text += f'  • Fecha de creación: {date_info["creation_date"]}<br/>'
                                if date_info.get('modification_date'):
                                    result_text += f'  • Última modificación: {date_info["modification_date"]}<br/>'

                        # Format author info
                        if 'author_info' in analysis.result_data:
                            author_info = analysis.result_data['author_info']
                            if any(author_info.values()):
                                result_text += '<br/>Información de autoría:<br/>'
                                if author_info.get('author'):
                                    result_text += f'  • Autor: {author_info["author"]}<br/>'
                                if author_info.get('creator'):
                                    result_text += f'  • Creador: {author_info["creator"]}<br/>'

                        # Format software info
                        if 'software_info' in analysis.result_data:
                            software_info = analysis.result_data['software_info']
                            if any(software_info.values()):
                                result_text += '<br/>Software utilizado:<br/>'
                                if software_info.get('producer'):
                                    result_text += f'  • Productor: {software_info["producer"]}<br/>'
                                if software_info.get('creator_tool'):
                                    result_text += f'  • Herramienta: {software_info["creator_tool"]}<br/>'

                        story.append(Paragraph(result_text, body_style))

                    story.append(Spacer(1, 0.3*cm))
            else:
                story.append(Paragraph('No se encontraron análisis forenses realizados.', body_style))

            story.append(Spacer(1, 0.5*cm))

        # Graph relationships
        if report.include_graph:
            story.append(PageBreak())
            story.append(Paragraph('ANEXO B: GRAFO DE RELACIONES', heading_style))

            try:
                graph_service = GraphService()
                graph_data = graph_service.get_case_graph(report.case_id)

                if graph_data['nodes'] or graph_data['relationships']:
                    # Summary statistics
                    story.append(Paragraph(
                        f'<b>Resumen del grafo:</b>',
                        body_style
                    ))
                    story.append(Paragraph(
                        f'  • Total de nodos: {len(graph_data["nodes"])}<br/>'
                        f'  • Total de relaciones: {len(graph_data["relationships"])}',
                        body_style
                    ))
                    story.append(Spacer(1, 0.5*cm))

                    # Generate and include graph visualization
                    graph_image_path = ReportService._generate_graph_image(graph_data)
                    if graph_image_path and os.path.exists(graph_image_path):
                        try:
                            current_app.logger.info(f'Adding graph image to PDF: {graph_image_path}')
                            # Add graph image
                            img = RLImage(graph_image_path, width=16*cm, height=10.67*cm, kind='proportional')
                            story.append(img)
                            story.append(Spacer(1, 0.5*cm))

                            # Store path for cleanup after PDF is built
                            # We'll clean it up later in the function
                            if not hasattr(report, '_temp_files'):
                                report._temp_files = []
                            report._temp_files.append(graph_image_path)

                        except Exception as e:
                            current_app.logger.error(f'Error adding graph image to PDF: {e}', exc_info=True)
                            story.append(Paragraph(
                                '<i>No se pudo generar la visualización del grafo</i>',
                                body_style
                            ))
                            # Clean up failed image
                            try:
                                if os.path.exists(graph_image_path):
                                    os.remove(graph_image_path)
                            except:
                                pass
                    else:
                        current_app.logger.warning('Graph image not available or not found')
                        story.append(Paragraph(
                            '<i>Visualización del grafo no disponible</i>',
                            body_style
                        ))
                        story.append(Spacer(1, 0.3*cm))

                    # List nodes by type
                    nodes_by_type = {}
                    for node in graph_data['nodes']:
                        node_type = node['label']
                        if node_type not in nodes_by_type:
                            nodes_by_type[node_type] = []
                        nodes_by_type[node_type].append(node)

                    story.append(Paragraph('<b>Nodos del grafo:</b>', body_style))
                    story.append(Spacer(1, 0.2*cm))

                    for node_type, nodes in nodes_by_type.items():
                        story.append(Paragraph(f'<b>{node_type}:</b>', body_style))
                        for node in nodes[:20]:  # Limit to first 20 nodes per type
                            props = node['properties']
                            # Extract relevant identifier based on node type
                            identifier = (props.get('name') or
                                        props.get('number') or
                                        props.get('address') or
                                        props.get('plate') or
                                        props.get('username') or
                                        props.get('dni_cif') or
                                        'N/A')
                            story.append(Paragraph(f'  • {identifier}', body_style))
                        if len(nodes) > 20:
                            story.append(Paragraph(f'  ... y {len(nodes) - 20} más', body_style))
                        story.append(Spacer(1, 0.2*cm))

                    # List relationships
                    if graph_data['relationships']:
                        story.append(Spacer(1, 0.3*cm))
                        story.append(Paragraph('<b>Relaciones identificadas:</b>', body_style))
                        story.append(Spacer(1, 0.2*cm))

                        # Group by relationship type
                        rels_by_type = {}
                        for rel in graph_data['relationships']:
                            rel_type = rel['type']
                            if rel_type not in rels_by_type:
                                rels_by_type[rel_type] = []
                            rels_by_type[rel_type].append(rel)

                        for rel_type, rels in rels_by_type.items():
                            story.append(Paragraph(
                                f'  • {rel_type}: {len(rels)} relación(es)',
                                body_style
                            ))

                else:
                    story.append(Paragraph('No se encontraron nodos o relaciones en el grafo.', body_style))

                graph_service.close()

            except Exception as e:
                current_app.logger.error(f'Error al obtener grafo: {e}')
                story.append(Paragraph(
                    f'Error al generar grafo de relaciones: {str(e)}',
                    body_style
                ))

            story.append(Spacer(1, 0.5*cm))

        # Conclusions
        if report.conclusions:
            story.append(PageBreak())
            story.append(Paragraph(f'{section_num}. CONCLUSIONES', heading_style))
            story.append(Paragraph(report.conclusions, body_style))
            story.append(Spacer(1, 0.5*cm))
            section_num += 1

        # Recommendations
        if report.recommendations:
            story.append(Paragraph(f'{section_num}. RECOMENDACIONES', heading_style))
            story.append(Paragraph(report.recommendations, body_style))
            story.append(Spacer(1, 0.5*cm))
            section_num += 1

        # Build PDF
        doc.build(story)

        # Clean up temporary files (like graph images)
        if hasattr(report, '_temp_files'):
            for temp_file in report._temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        current_app.logger.info(f'Cleaned up temporary file: {temp_file}')
                except Exception as e:
                    current_app.logger.warning(f'Failed to clean up temp file {temp_file}: {e}')

        return file_path

    @staticmethod
    def export_json(report_id, user_id):
        """
        Export report as JSON.

        Args:
            report_id: Report ID
            user_id: User ID requesting export

        Returns:
            dict: Export result with JSON data
        """
        report = Report.query.get(report_id)
        if not report:
            return {
                'success': False,
                'error': 'Report not found'
            }

        # Build JSON structure
        data = {
            'report': report.to_dict(),
            'case': {
                'numero_orden': report.case.numero_orden,
                'objeto_investigacion': report.case.objeto_investigacion,
                'cliente_nombre': report.case.cliente_nombre
            },
            'created_by': {
                'nombre': report.created_by.nombre,
                'tip_number': report.created_by.tip_number
            },
            'content': {
                'introduction': report.introduction,
                'methodology': report.methodology,
                'findings': report.findings,
                'conclusions': report.conclusions,
                'recommendations': report.recommendations
            }
        }

        # Include evidence if requested
        if report.include_evidence_list:
            evidence_list = Evidence.query.filter_by(
                case_id=report.case_id,
                is_deleted=False
            ).all()
            data['evidence'] = [e.to_dict() for e in evidence_list]

        # Include timeline if requested
        if report.include_timeline:
            timeline_events = TimelineEvent.query.filter_by(
                case_id=report.case_id,
                is_deleted=False
            ).order_by(TimelineEvent.event_date.asc()).all()
            data['timeline'] = [e.to_dict() for e in timeline_events]

        # Log export
        user = User.query.get(user_id)
        if user:
            AuditLog.log(
                action='REPORT_EXPORTED_JSON',
                resource_type='report',
                resource_id=report.id,
                user=user
            )

        return {
            'success': True,
            'data': data
        }

    @staticmethod
    def delete_report(report_id, user_id):
        """
        Soft delete a report.

        Args:
            report_id: Report ID
            user_id: User ID performing deletion

        Returns:
            bool: Success status
        """
        report = Report.query.get(report_id)
        if not report:
            return False

        report.is_deleted = True
        report.deleted_at = datetime.utcnow()
        db.session.commit()

        # Log deletion
        user = User.query.get(user_id)
        if user:
            AuditLog.log(
                action='REPORT_DELETED',
                resource_type='report',
                resource_id=report.id,
                user=user
            )

        return True
