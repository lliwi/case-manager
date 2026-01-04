"""
DNI/NIE Validator Plugin.

Validates Spanish DNI and NIE identifiers using the modulo 23 algorithm
as required by Spanish law.
"""
import re
import pluggy

hookimpl = pluggy.HookimplMarker("casemanager")


class DNIValidatorPlugin:
    """Plugin for validating Spanish DNI and NIE identifiers."""

    # Modulo 23 letter table
    DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"

    # Valid NIE prefix letters
    NIE_PREFIXES = ['X', 'Y', 'Z']

    # NIE prefix number mapping
    NIE_PREFIX_MAP = {'X': '0', 'Y': '1', 'Z': '2'}

    @hookimpl
    def get_info(self):
        """Get plugin information."""
        return {
            'name': 'dni_validator',
            'display_name': 'Validador DNI/NIE',
            'description': 'Valida números de DNI y NIE españoles usando el algoritmo de módulo 23',
            'version': '1.0.0',
            'author': 'Case Manager',
            'category': 'forensic',
            'type': 'validator',
            'supported_formats': ['DNI', 'NIE']
        }

    def validate(self, identifier: str) -> dict:
        """
        Validate a Spanish DNI or NIE.

        Args:
            identifier: DNI or NIE string

        Returns:
            dict: Validation result with details
        """
        if not identifier:
            return {
                'valid': False,
                'error': 'Identificador vacío',
                'identifier': identifier
            }

        # Clean and normalize
        identifier = identifier.upper().strip().replace('-', '').replace(' ', '')

        # Check if it's a NIE
        if identifier[0] in self.NIE_PREFIXES:
            return self._validate_nie(identifier)
        else:
            return self._validate_dni(identifier)

    def _validate_dni(self, dni: str) -> dict:
        """
        Validate a DNI using modulo 23 algorithm.

        Args:
            dni: DNI string (8 digits + 1 letter)

        Returns:
            dict: Validation result
        """
        # DNI format: 8 digits + 1 letter
        pattern = re.compile(r'^(\d{8})([A-Z])$')
        match = pattern.match(dni)

        if not match:
            return {
                'valid': False,
                'error': 'Formato inválido. Debe ser 8 dígitos seguidos de una letra',
                'identifier': dni,
                'type': 'DNI'
            }

        number_part = match.group(1)
        letter_part = match.group(2)

        # Calculate expected letter using modulo 23
        number = int(number_part)
        expected_letter = self.DNI_LETTERS[number % 23]

        if letter_part == expected_letter:
            return {
                'valid': True,
                'identifier': dni,
                'type': 'DNI',
                'number': number_part,
                'letter': letter_part,
                'message': 'DNI válido'
            }
        else:
            return {
                'valid': False,
                'identifier': dni,
                'type': 'DNI',
                'number': number_part,
                'letter': letter_part,
                'expected_letter': expected_letter,
                'error': f'Letra incorrecta. Debería ser {expected_letter}'
            }

    def _validate_nie(self, nie: str) -> dict:
        """
        Validate a NIE using modulo 23 algorithm.

        Args:
            nie: NIE string (X/Y/Z + 7 digits + 1 letter)

        Returns:
            dict: Validation result
        """
        # NIE format: X/Y/Z + 7 digits + 1 letter
        pattern = re.compile(r'^([XYZ])(\d{7})([A-Z])$')
        match = pattern.match(nie)

        if not match:
            return {
                'valid': False,
                'error': 'Formato inválido. Debe ser X/Y/Z seguido de 7 dígitos y una letra',
                'identifier': nie,
                'type': 'NIE'
            }

        prefix = match.group(1)
        number_part = match.group(2)
        letter_part = match.group(3)

        # Replace prefix with corresponding number
        full_number = self.NIE_PREFIX_MAP[prefix] + number_part
        number = int(full_number)

        # Calculate expected letter using modulo 23
        expected_letter = self.DNI_LETTERS[number % 23]

        if letter_part == expected_letter:
            return {
                'valid': True,
                'identifier': nie,
                'type': 'NIE',
                'prefix': prefix,
                'number': number_part,
                'letter': letter_part,
                'message': 'NIE válido'
            }
        else:
            return {
                'valid': False,
                'identifier': nie,
                'type': 'NIE',
                'prefix': prefix,
                'number': number_part,
                'letter': letter_part,
                'expected_letter': expected_letter,
                'error': f'Letra incorrecta. Debería ser {expected_letter}'
            }

    @hookimpl
    def analyze_file(self, file_path, **kwargs):
        """
        Analyze a file to extract and validate DNI/NIE identifiers.

        Args:
            file_path: Path to the file
            **kwargs: Additional arguments

        Returns:
            dict: Extracted and validated identifiers
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Search for potential DNI/NIE patterns
            dni_pattern = re.compile(r'\b(\d{8}[A-Z])\b')
            nie_pattern = re.compile(r'\b([XYZ]\d{7}[A-Z])\b')

            found_identifiers = []

            # Find DNIs
            for match in dni_pattern.finditer(content):
                identifier = match.group(1)
                validation = self.validate(identifier)
                if validation['valid']:
                    found_identifiers.append(validation)

            # Find NIEs
            for match in nie_pattern.finditer(content):
                identifier = match.group(1)
                validation = self.validate(identifier)
                if validation['valid']:
                    found_identifiers.append(validation)

            return {
                'identifiers_found': len(found_identifiers),
                'identifiers': found_identifiers,
                'success': True
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
