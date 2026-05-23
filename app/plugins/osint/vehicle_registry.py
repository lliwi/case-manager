"""
Vehicle Registry Lookup Plugin.

OSINT plugin for looking up vehicle details by Spanish license plate (matrícula)
or VIN (número de bastidor) via RapidAPI (api-license-plate-spain).
"""
import re
import logging

import pluggy
import requests

from app.models.api_key import ApiKey

hookimpl = pluggy.HookimplMarker("casemanager")
logger = logging.getLogger(__name__)

# RapidAPI endpoint
_RAPIDAPI_HOST = 'api-license-plate-spain.p.rapidapi.com'
_RAPIDAPI_URL = f'https://{_RAPIDAPI_HOST}/es'

# Regex patterns for input detection
_PLATE_MODERN = re.compile(r'^[0-9]{4}[A-Z]{3}$')          # Modern: 1234ABC
_PLATE_OLD    = re.compile(r'^[A-Z]{1,2}[0-9]{4}[A-Z]{2}$')  # Old provincial
_VIN_PATTERN  = re.compile(r'^[A-HJ-NPR-Z0-9]{17}$', re.IGNORECASE)


def _detect_query_type(query: str) -> str:
    """Return 'plate', 'vin', or 'unknown'."""
    q = query.strip().upper().replace('-', '').replace(' ', '')
    if _VIN_PATTERN.match(q):
        return 'vin'
    if _PLATE_MODERN.match(q) or _PLATE_OLD.match(q):
        return 'plate'
    return 'unknown'


class VehicleRegistryPlugin:
    """
    OSINT plugin for vehicle data lookup.

    Resolves a Spanish matrícula or VIN to make, model, year, colour,
    fuel type, engine displacement, and more using the Autoways/RapidAPI
    Spanish plate database (same source as Oscaro.es).
    """

    @hookimpl
    def get_info(self):
        return {
            'name': 'vehicle_registry',
            'display_name': 'Consulta de Vehículos (Matrícula / Bastidor)',
            'description': (
                'Obtiene datos técnicos de un vehículo a partir de su matrícula española '
                'o número de bastidor (VIN) vía RapidAPI (Autoways / DGT).'
            ),
            'version': '2.0.0',
            'author': 'Case Manager',
            'category': 'osint',
            'type': 'vehicle',
            'supported_formats': ['plate', 'vin'],
            'requires_api_key': True,
            'api_service': 'rapidapi',
        }

    @hookimpl
    def lookup(self, query: str, query_type: str = 'auto', **kwargs) -> dict:
        """
        Look up vehicle data.

        Args:
            query:      Matrícula (e.g. '1234ABC') or VIN (17 chars).
            query_type: 'plate', 'vin', or 'auto' (default).

        Returns:
            dict with keys: success, query, query_type, vehicle_data, source, error.
        """
        query = query.strip().upper().replace(' ', '').replace('-', '')

        if query_type == 'auto':
            query_type = _detect_query_type(query)

        if query_type == 'unknown':
            return {
                'success': False,
                'query': query,
                'query_type': 'unknown',
                'error': (
                    'Formato no reconocido. Introduce una matrícula española '
                    '(ej. 1234ABC) o un número de bastidor de 17 caracteres.'
                ),
            }

        # Retrieve RapidAPI key from DB
        api_key_obj = ApiKey.get_active_key('rapidapi')

        if not api_key_obj:
            return {
                'success': False,
                'query': query,
                'query_type': query_type,
                'error': (
                    'No hay API Key de RapidAPI configurada. '
                    'Añade una key en Admin → API Keys (Servicio: RapidAPI).'
                ),
            }

        api_key = api_key_obj.get_api_key()
        return self._query_rapidapi(query, query_type, api_key, api_key_obj)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _query_rapidapi(self, query: str, query_type: str, api_key: str, api_key_obj) -> dict:
        """Query the Autoways API via RapidAPI for plate or VIN."""
        params = {}
        if query_type == 'plate':
            params['plate'] = query
        else:
            params['vin'] = query

        headers = {
            'X-RapidAPI-Key': api_key,
            'X-RapidAPI-Host': _RAPIDAPI_HOST,
        }

        try:
            resp = requests.get(_RAPIDAPI_URL, params=params, headers=headers, timeout=15)

            # Track usage
            api_key_obj.increment_usage()

            if resp.status_code == 401 or resp.status_code == 403:
                return {
                    'success': False, 'query': query, 'query_type': query_type,
                    'error': 'API Key de RapidAPI inválida o sin suscripción activa.',
                }
            if resp.status_code == 429:
                return {
                    'success': False, 'query': query, 'query_type': query_type,
                    'error': 'Límite de consultas de RapidAPI alcanzado. Inténtalo más tarde.',
                }

            resp.raise_for_status()
            payload = resp.json()

            # API returns a list of matching records
            if not payload or (isinstance(payload, list) and len(payload) == 0):
                return {
                    'success': False, 'query': query, 'query_type': query_type,
                    'error': f'No se encontraron datos para {query}.',
                }

            # Take the first result as the primary record
            data = payload[0] if isinstance(payload, list) else payload

            return {
                'success': True,
                'query': query,
                'query_type': query_type,
                'source': 'RapidAPI / DGT (api-license-plate-spain)',
                'vehicle_data': self._normalize_response(data),
                'raw': payload,
            }

        except requests.exceptions.Timeout:
            logger.warning("Timeout querying RapidAPI for %s %s", query_type, query)
            return {
                'success': False, 'query': query, 'query_type': query_type,
                'error': 'La consulta tardó demasiado. Inténtalo de nuevo.',
            }
        except requests.exceptions.RequestException as e:
            logger.error("RapidAPI request error for %s %s: %s", query_type, query, e)
            return {
                'success': False, 'query': query, 'query_type': query_type,
                'error': str(e),
            }

    # ------------------------------------------------------------------
    # Response normaliser — map Autoways fields to standard schema
    # ------------------------------------------------------------------

    def _normalize_response(self, data: dict) -> dict:
        """Normalise DGT/RapidAPI response to internal vehicle_data schema."""
        return {
            # Identification
            'plate':              data.get('MATRICULA', ''),
            'vin':                data.get('VIN', ''),
            'make':               data.get('MARCA', ''),
            'model':              data.get('MODELO', ''),
            'version':            data.get('TPMOTOR', ''),
            'label':              '',
            'commercial_name':    '',
            'color':              data.get('COLOR', ''),
            'body_type':          data.get('CARROCERIA', ''),
            'platform_code':      '',
            'serial_number':      '',

            # Engine & Performance
            'fuel_type':          data.get('TYMOTOR', ''),
            'engine_code':        data.get('MOTOR', ''),
            'engine_codes':       [],
            'engine_cc':          '',
            'engine_liters':      '',
            'power_kw':           data.get('KWs', ''),
            'power_hp':           '',
            'fiscal_power':       '',
            'gearbox_type':       '',
            'num_gears':          '',
            'max_speed':          '',

            # Drivetrain
            'drivetrain':         data.get('TRACCION', ''),
            'injection':          data.get('INYECCION', ''),

            # Dimensions & Weight
            'num_doors':          '',
            'num_seats':          '',
            'length_mm':          '',
            'width_mm':           '',
            'height_mm':          '',
            'ptac_kg':            '',

            # Emissions & Consumption
            'co2_emissions':      '',
            'euro_standard':      '',
            'mixed_consumption':  '',

            # Tyres
            'tyres':              '',

            # Dates
            'first_registration': data.get('FECHA_MATRICULACION', ''),
            'year_start':         '',
            'year_end':           '',

            # TecDoc
            'tecdoc_ktype':       data.get('ID_KTYPE', ''),
            'tecdoc_ktypes':      [],
            'tecdoc_description': '',

            # IDs
            'brand_id':           data.get('IDMARCA', ''),
            'model_id':           data.get('IDMODELO', ''),
            'tecdoc_brand_id':    data.get('ID_MARCA_TECDOC', ''),
            'tecdoc_model_id':    data.get('ID_MODELO_TECDOC', ''),
            'country':            data.get('PAIS', ''),

            # Images (not provided by this API)
            'brand_image':        '',
            'model_image':        '',
        }
