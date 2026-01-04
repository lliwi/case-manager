"""
Report Service for generating forensic investigation reports.

Handles PDF generation, digital signatures, and report management.
"""
from app.models.report import Report, ReportType, ReportStatus
from app.models.case import Case
from app.models.evidence import Evidence
from app.models.timeline import TimelineEvent
from app.models.audit import AuditLog
from app.extensions import db
from app.utils.hashing import calculate_file_hashes
from flask import current_app
from datetime import datetime
import os
import json

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
            status=ReportStatus.DRAFT
        )

        db.session.add(report)
        db.session.commit()

        # Log creation
        AuditLog.log(
            action='REPORT_CREATED',
            resource_type='report',
            resource_id=report.id,
            user_id=created_by_id,
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
            AuditLog.log(
                action='REPORT_GENERATED',
                resource_type='report',
                resource_id=report.id,
                user_id=user_id,
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

        # Introduction
        if report.introduction:
            story.append(Paragraph('1. INTRODUCCIÓN', heading_style))
            story.append(Paragraph(report.introduction, body_style))
            story.append(Spacer(1, 0.5*cm))

        # Methodology
        if report.methodology:
            story.append(Paragraph('2. METODOLOGÍA', heading_style))
            story.append(Paragraph(report.methodology, body_style))
            story.append(Spacer(1, 0.5*cm))

        # Findings
        if report.findings:
            story.append(Paragraph('3. HALLAZGOS', heading_style))
            story.append(Paragraph(report.findings, body_style))
            story.append(Spacer(1, 0.5*cm))

        # Evidence list
        if report.include_evidence_list:
            story.append(PageBreak())
            story.append(Paragraph('4. RELACIÓN DE EVIDENCIAS', heading_style))

            evidence_list = Evidence.query.filter_by(
                case_id=report.case_id,
                is_deleted=False
            ).all()

            if evidence_list:
                evidence_data = [['#', 'Tipo', 'Descripción', 'Fecha', 'SHA-256']]
                for idx, evidence in enumerate(evidence_list, 1):
                    evidence_data.append([
                        str(idx),
                        evidence.evidence_type.value,
                        evidence.description[:50] + '...' if len(evidence.description) > 50 else evidence.description,
                        evidence.acquired_at.strftime('%d/%m/%Y') if evidence.acquired_at else '-',
                        evidence.hash_sha256[:16] + '...' if evidence.hash_sha256 else '-'
                    ])

                evidence_table = Table(evidence_data, colWidths=[1*cm, 3*cm, 7*cm, 2.5*cm, 4*cm])
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
            else:
                story.append(Paragraph('No se encontraron evidencias asociadas.', body_style))

            story.append(Spacer(1, 0.5*cm))

        # Timeline
        if report.include_timeline:
            story.append(PageBreak())
            story.append(Paragraph('5. CRONOLOGÍA DE EVENTOS', heading_style))

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

        # Conclusions
        if report.conclusions:
            story.append(PageBreak())
            story.append(Paragraph('6. CONCLUSIONES', heading_style))
            story.append(Paragraph(report.conclusions, body_style))
            story.append(Spacer(1, 0.5*cm))

        # Recommendations
        if report.recommendations:
            story.append(Paragraph('7. RECOMENDACIONES', heading_style))
            story.append(Paragraph(report.recommendations, body_style))
            story.append(Spacer(1, 0.5*cm))

        # Digital signature section
        story.append(PageBreak())
        story.append(Paragraph('VERIFICACIÓN DIGITAL', heading_style))
        story.append(Paragraph(
            f'Este informe ha sido generado digitalmente y puede ser verificado mediante su hash SHA-256:',
            body_style
        ))
        story.append(Spacer(1, 0.3*cm))

        # Placeholder for hash (will be calculated after PDF generation)
        story.append(Paragraph(
            '<font name="Courier" size="8">[El hash será calculado tras la generación del PDF]</font>',
            body_style
        ))

        # Build PDF
        doc.build(story)

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
                'titulo': report.case.titulo,
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
        AuditLog.log(
            action='REPORT_EXPORTED_JSON',
            resource_type='report',
            resource_id=report.id,
            user_id=user_id
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
        AuditLog.log(
            action='REPORT_DELETED',
            resource_type='report',
            resource_id=report.id,
            user_id=user_id
        )

        return True
