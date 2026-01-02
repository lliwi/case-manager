"""
Libro-registro service.

Manages the official case registry (libro-registro) required by
Ley 5/2014 de Seguridad Privada, Art. 25.
"""
from app.models.case import Case
from app.extensions import db
from datetime import datetime, timedelta
from sqlalchemy import and_, or_, extract
import csv
import io


class LibroRegistroService:
    """Service for managing and exporting the libro-registro."""

    @staticmethod
    def get_registro_entries(
        detective_id=None,
        year=None,
        status=None,
        start_date=None,
        end_date=None,
        include_deleted=False
    ):
        """
        Get libro-registro entries with filters.

        Args:
            detective_id: Filter by detective
            year: Filter by year
            status: Filter by case status
            start_date: Filter by start date (from)
            end_date: Filter by start date (to)
            include_deleted: Include soft-deleted cases

        Returns:
            Query object with filtered cases
        """
        query = Case.query

        # Filter by detective
        if detective_id:
            query = query.filter(Case.detective_id == detective_id)

        # Filter by year
        if year:
            query = query.filter(extract('year', Case.fecha_inicio) == year)

        # Filter by status
        if status:
            query = query.filter(Case.status == status)

        # Filter by date range
        if start_date:
            query = query.filter(Case.fecha_inicio >= start_date)
        if end_date:
            query = query.filter(Case.fecha_inicio <= end_date)

        # Exclude deleted unless specified
        if not include_deleted:
            query = query.filter(Case.is_deleted == False)

        # Order by numero_orden (chronological)
        query = query.order_by(Case.numero_orden.asc())

        return query

    @staticmethod
    def export_to_csv(cases, include_personal_data=True):
        """
        Export cases to CSV format (libro-registro oficial).

        Args:
            cases: List of Case instances
            include_personal_data: Include client personal data (default True)

        Returns:
            CSV string
        """
        output = io.StringIO()

        # Define columns per Ley 5/2014 requirements
        if include_personal_data:
            fieldnames = [
                'Número de Orden',
                'Fecha Inicio',
                'Fecha Cierre',
                'Cliente (Nombre)',
                'Cliente (DNI/CIF)',
                'Sujeto Investigado',
                'Objeto Investigación',
                'Detective (TIP)',
                'Estado',
            ]
        else:
            # Anonymized version
            fieldnames = [
                'Número de Orden',
                'Fecha Inicio',
                'Fecha Cierre',
                'Tipo de Legitimidad',
                'Objeto Investigación',
                'Detective (TIP)',
                'Estado',
            ]

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for case in cases:
            if include_personal_data:
                row = {
                    'Número de Orden': case.numero_orden,
                    'Fecha Inicio': case.fecha_inicio.strftime('%d/%m/%Y'),
                    'Fecha Cierre': case.fecha_cierre.strftime('%d/%m/%Y') if case.fecha_cierre else '',
                    'Cliente (Nombre)': case.cliente_nombre,
                    'Cliente (DNI/CIF)': case.cliente_dni_cif,
                    'Sujeto Investigado': case.sujeto_nombres or '',
                    'Objeto Investigación': case.objeto_investigacion,
                    'Detective (TIP)': case.detective_tip,
                    'Estado': case.status.value if case.status else '',
                }
            else:
                row = {
                    'Número de Orden': case.numero_orden,
                    'Fecha Inicio': case.fecha_inicio.strftime('%d/%m/%Y'),
                    'Fecha Cierre': case.fecha_cierre.strftime('%d/%m/%Y') if case.fecha_cierre else '',
                    'Tipo de Legitimidad': case.legitimacy_type.value if case.legitimacy_type else '',
                    'Objeto Investigación': case.objeto_investigacion[:100] + '...' if len(case.objeto_investigacion) > 100 else case.objeto_investigacion,
                    'Detective (TIP)': case.detective_tip,
                    'Estado': case.status.value if case.status else '',
                }

            writer.writerow(row)

        return output.getvalue()

    @staticmethod
    def get_statistics(detective_id=None, year=None):
        """
        Get statistics for libro-registro.

        Args:
            detective_id: Filter by detective
            year: Filter by year (default current year)

        Returns:
            dict with statistics
        """
        if year is None:
            year = datetime.utcnow().year

        # Build base query
        query = Case.query.filter(
            extract('year', Case.fecha_inicio) == year,
            Case.is_deleted == False
        )

        if detective_id:
            query = query.filter(Case.detective_id == detective_id)

        # Total cases
        total_cases = query.count()

        # Cases by status
        from app.models.case import CaseStatus
        cases_by_status = {}
        for status in CaseStatus:
            count = query.filter(Case.status == status).count()
            cases_by_status[status.value] = count

        # Cases by legitimacy type
        from app.models.case import LegitimacyType
        cases_by_legitimacy = {}
        for leg_type in LegitimacyType:
            count = query.filter(Case.legitimacy_type == leg_type).count()
            cases_by_legitimacy[leg_type.value] = count

        # Average case duration
        closed_cases = query.filter(Case.fecha_cierre.isnot(None)).all()
        if closed_cases:
            total_duration = sum(case.get_duration_days() for case in closed_cases)
            avg_duration = total_duration / len(closed_cases)
        else:
            avg_duration = 0

        # Legitimacy validation rate
        validated_cases = query.filter(Case.legitimacy_validated == True).count()
        validation_rate = (validated_cases / total_cases * 100) if total_cases > 0 else 0

        # Crime detection rate
        crime_detected_cases = query.filter(Case.crime_detected == True).count()
        crime_detection_rate = (crime_detected_cases / total_cases * 100) if total_cases > 0 else 0

        return {
            'year': year,
            'total_cases': total_cases,
            'cases_by_status': cases_by_status,
            'cases_by_legitimacy': cases_by_legitimacy,
            'avg_duration_days': round(avg_duration, 1),
            'validation_rate': round(validation_rate, 1),
            'crime_detection_rate': round(crime_detection_rate, 1),
            'validated_cases': validated_cases,
            'crime_detected_cases': crime_detected_cases,
        }

    @staticmethod
    def generate_official_report(year, detective_id=None):
        """
        Generate official libro-registro report for authorities.

        Args:
            year: Year to report
            detective_id: Optional filter by detective

        Returns:
            dict with report data
        """
        cases = LibroRegistroService.get_registro_entries(
            detective_id=detective_id,
            year=year,
            include_deleted=False
        ).all()

        stats = LibroRegistroService.get_statistics(
            detective_id=detective_id,
            year=year
        )

        return {
            'year': year,
            'generated_at': datetime.utcnow(),
            'total_entries': len(cases),
            'statistics': stats,
            'cases': [case.to_libro_registro_dict() for case in cases],
        }

    @staticmethod
    def verify_compliance():
        """
        Verify compliance with Ley 5/2014 registro requirements.

        Returns:
            dict with compliance check results
        """
        issues = []

        # Check for cases without numero_orden
        cases_without_number = Case.query.filter(
            or_(Case.numero_orden == None, Case.numero_orden == '')
        ).count()
        if cases_without_number > 0:
            issues.append(f"{cases_without_number} cases without número de orden")

        # Check for cases without legitimacy validation
        cases_pending_validation = Case.query.filter(
            Case.legitimacy_validated == False,
            Case.is_deleted == False
        ).count()
        if cases_pending_validation > 0:
            issues.append(f"{cases_pending_validation} cases pending legitimacy validation")

        # Check for cases with detected crimes not reported
        cases_crime_not_reported = Case.query.filter(
            Case.crime_detected == True,
            Case.crime_reported == False,
            Case.is_deleted == False
        ).count()
        if cases_crime_not_reported > 0:
            issues.append(f"{cases_crime_not_reported} cases with detected crimes not reported to authorities")

        # Check for duplicate numero_orden
        from sqlalchemy import func
        duplicates = db.session.query(
            Case.numero_orden,
            func.count(Case.id)
        ).group_by(Case.numero_orden).having(func.count(Case.id) > 1).all()

        if duplicates:
            issues.append(f"{len(duplicates)} duplicate número de orden found")

        return {
            'compliant': len(issues) == 0,
            'issues': issues,
            'checked_at': datetime.utcnow()
        }
