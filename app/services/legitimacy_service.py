"""
Legitimacy validation service.

Validates that investigations have legitimate interest (interés legítimo)
as required by Spanish law (Ley 5/2014).
"""
from app.models.case import Case, LegitimacyType, CaseStatus
from app.extensions import db
from datetime import datetime
import re


# Keywords that may indicate crimes prosecutable ex officio
# (delitos perseguibles de oficio)
CRIME_KEYWORDS = [
    # Violent crimes
    'asesinato', 'homicidio', 'violación', 'agresión sexual', 'secuestro',
    'violencia de género', 'maltrato', 'lesiones graves', 'tortura',

    # Serious crimes
    'terrorismo', 'narcotráfico', 'tráfico de drogas', 'trata de personas',
    'explotación sexual', 'pornografía infantil', 'pederastia',

    # Organized crime
    'blanqueo de capitales', 'lavado de dinero', 'organización criminal',
    'crimen organizado', 'corrupción política',

    # Serious fraud
    'estafa piramidal', 'delito contra la hacienda pública',

    # Others requiring official investigation
    'desaparición forzada', 'genocidio', 'crímenes de guerra',
]


class LegitimacyService:
    """Service for validating case legitimacy."""

    @staticmethod
    def validate_legitimacy(case, user, approved=True, notes=None):
        """
        Validate case legitimacy.

        Args:
            case: Case instance
            user: User validating (must have admin/supervisor role)
            approved: Whether legitimacy is approved
            notes: Optional validation notes

        Returns:
            Case instance

        Raises:
            ValueError: If validation fails
        """
        if not user.has_role('admin') and not user.has_role('detective'):
            raise ValueError("Only admins or detectives can validate legitimacy")

        if approved:
            case.legitimacy_validated = True
            case.legitimacy_validated_by_id = user.id
            case.legitimacy_validated_at = datetime.utcnow()

            # If no crimes detected, case can be activated
            if not case.crime_detected:
                case.status = CaseStatus.EN_INVESTIGACION
        else:
            case.legitimacy_validated = False
            case.status = CaseStatus.PENDIENTE_VALIDACION

        if notes:
            case.notas_internas = (case.notas_internas or '') + f"\n[{datetime.utcnow()}] Validación: {notes}"

        db.session.commit()

        # Log validation
        from app.models.audit import AuditLog
        AuditLog.log(
            action='LEGITIMACY_VALIDATED' if approved else 'LEGITIMACY_REJECTED',
            resource_type='case',
            resource_id=case.id,
            user=user,
            description=f"Legitimacy {'approved' if approved else 'rejected'} for case {case.numero_orden}",
            extra_data={'notes': notes}
        )

        return case

    @staticmethod
    def check_for_crimes(text):
        """
        Check text for keywords indicating crimes prosecutable ex officio.

        Args:
            text: Text to check (case description, investigation purpose, etc.)

        Returns:
            dict with 'detected' (bool) and 'keywords' (list of found keywords)
        """
        if not text:
            return {'detected': False, 'keywords': []}

        text_lower = text.lower()
        found_keywords = []

        for keyword in CRIME_KEYWORDS:
            if keyword in text_lower:
                found_keywords.append(keyword)

        return {
            'detected': len(found_keywords) > 0,
            'keywords': found_keywords
        }

    @staticmethod
    def scan_case_for_crimes(case):
        """
        Scan entire case for crime indicators.

        Args:
            case: Case instance

        Returns:
            dict with scan results
        """
        # Combine all text fields
        combined_text = ' '.join(filter(None, [
            case.objeto_investigacion,
            case.descripcion_detallada,
            case.legitimacy_description,
            case.sujeto_descripcion,
        ]))

        result = LegitimacyService.check_for_crimes(combined_text)

        if result['detected']:
            case.crime_detected = True
            case.crime_keywords_found = ','.join(result['keywords'])
            case.crime_description = f"Detected keywords: {', '.join(result['keywords'])}"
            case.status = db.Enum('CaseStatus').PENDIENTE_VALIDACION
            db.session.commit()

        return result

    @staticmethod
    def validate_dni_cif(dni_cif):
        """
        Validate Spanish DNI/NIE/CIF format.

        DNI and NIE are validated via the DNIValidatorPlugin (modulo 23).
        CIF validation (company tax ID) is handled locally.

        Args:
            dni_cif: DNI/NIE/CIF string

        Returns:
            dict with 'valid' (bool), 'type' (str) and 'error' (str, optional)
        """
        if not dni_cif:
            return {'valid': False, 'type': None, 'error': 'Empty value'}

        dni_cif = dni_cif.strip().upper()

        # CIF: Letter + 7 digits + control (digit or letter)
        cif_pattern = r'^[A-W]\d{7}[0-9A-J]$'
        if re.match(cif_pattern, dni_cif):
            return {'valid': True, 'type': 'CIF'}

        # DNI / NIE — delegate to plugin
        from app.plugins import plugin_manager
        result = plugin_manager.validate_dni_nie(dni_cif)
        # Normalise error key so callers can always use result.get('error')
        if not result['valid'] and 'error' not in result:
            result['error'] = result.get('message', 'Formato incorrecto')
        return result

    @staticmethod
    def get_legitimacy_requirements(legitimacy_type):
        """
        Get documentation requirements for each legitimacy type.

        Args:
            legitimacy_type: LegitimacyType enum value

        Returns:
            dict with requirements
        """
        requirements = {
            LegitimacyType.BAJAS_LABORALES: {
                'required_docs': ['Contrato laboral', 'Baja médica', 'Autorización empresa'],
                'description': 'Verificación de incapacidad temporal. Empresa debe acreditar interés legítimo.',
                'legal_basis': 'Art. 20.3 Estatuto de los Trabajadores'
            },
            LegitimacyType.COMPETENCIA_DESLEAL: {
                'required_docs': ['Estatutos de la empresa', 'Evidencia preliminar de competencia'],
                'description': 'Investigación de prácticas comerciales desleales.',
                'legal_basis': 'Ley 3/1991 de Competencia Desleal'
            },
            LegitimacyType.CUSTODIA_MENORES: {
                'required_docs': ['Sentencia provisional o convenio regulador', 'DNI del progenitor'],
                'description': 'Verificación de cumplimiento de régimen de visitas.',
                'legal_basis': 'Código Civil Art. 94'
            },
            LegitimacyType.INVESTIGACION_PATRIMONIAL: {
                'required_docs': ['Resolución judicial o contrato de préstamo'],
                'description': 'Localización de bienes para procedimientos ejecutivos.',
                'legal_basis': 'Ley de Enjuiciamiento Civil'
            },
            LegitimacyType.FRAUDE_SEGUROS: {
                'required_docs': ['Póliza de seguro', 'Parte de siniestro'],
                'description': 'Verificación de veracidad de reclamaciones.',
                'legal_basis': 'Ley 50/1980 de Contrato de Seguro'
            },
            LegitimacyType.INFIDELIDAD_CONYUGAL: {
                'required_docs': ['Libro de familia o certificado de matrimonio'],
                'description': 'Verificación de infidelidad para procedimiento de separación/divorcio.',
                'legal_basis': 'Código Civil Art. 81-89'
            },
            LegitimacyType.LOCALIZACION_PERSONAS: {
                'required_docs': ['Acreditación de vínculo familiar o comercial'],
                'description': 'Localización de personas con interés legítimo.',
                'legal_basis': 'Art. 48 Ley 5/2014'
            },
            LegitimacyType.SOLVENCIA_PATRIMONIAL: {
                'required_docs': ['Contrato o acuerdo comercial preliminar'],
                'description': 'Verificación de solvencia previo a relación comercial.',
                'legal_basis': 'Código de Comercio'
            },
            LegitimacyType.OTROS: {
                'required_docs': ['Documentación que acredite interés legítimo'],
                'description': 'Otros casos con interés legítimo acreditado.',
                'legal_basis': 'Art. 48 Ley 5/2014'
            },
        }

        return requirements.get(legitimacy_type, requirements[LegitimacyType.OTROS])
