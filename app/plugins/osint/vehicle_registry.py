"""
Vehicle Registry Lookup Plugin.

OSINT plugin for looking up vehicle details by Spanish license plate (matrícula)
or VIN (número de bastidor) using the Autoways API via RapidAPI.

API: api-license-plate-spain-matricula-api-espana (RapidAPI / Autoways)
"""
import re
import logging

import pluggy
import requests

from app.models.api_key import ApiKey

hookimpl = pluggy.HookimplMarker("casemanager")
logger = logging.getLogger(__name__)

# RapidAPI endpoint
_RAPIDAPI_HOST = 'api-license-plate-spain-matricula-api-espana.p.rapidapi.com'
_RAPIDAPI_URL = f'https://{_RAPIDAPI_HOST}/'

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
        params = {'country': 'es'}
        if query_type == 'plate':
            params['plaque'] = query
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

            # Check API-level errors
            if payload.get('error'):
                return {
                    'success': False, 'query': query, 'query_type': query_type,
                    'error': payload.get('message', 'Error en la consulta.'),
                }

            data = payload.get('data', {})
            if not data:
                return {
                    'success': False, 'query': query, 'query_type': query_type,
                    'error': f'No se encontraron datos para {query}.',
                }

            return {
                'success': True,
                'query': query,
                'query_type': query_type,
                'source': 'RapidAPI / Autoways (DGT)',
                'vehicle_data': self._normalize_response(data),
                'raw': data,
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
        """Normalise Autoways/RapidAPI response to internal vehicle_data schema."""
        return {
            # Identification
            'plate':              data.get('AWN_immat', ''),
            'vin':                data.get('AWN_VIN', ''),
            'make':               data.get('AWN_marque', ''),
            'model':              data.get('AWN_modele', ''),
            'version':            data.get('AWN_version', ''),
            'label':              data.get('AWN_label', ''),
            'commercial_name':    data.get('AWN_nom_commercial', ''),
            'color':              data.get('AWN_couleur', ''),
            'body_type':          data.get('AWN_style_carrosserie', ''),
            'platform_code':      data.get('AWN_code_platform', ''),
            'serial_number':      data.get('AWN_numero_de_serie', ''),

            # Engine & Performance
            'fuel_type':          data.get('AWN_energie', ''),
            'engine_code':        data.get('AWN_code_moteur', ''),
            'engine_codes':       data.get('AWN_codes_moteur', []),
            'engine_cc':          data.get('AWN_cylindre_capacite', ''),
            'engine_liters':      data.get('AWN_cylindree_liters', ''),
            'power_kw':           data.get('AWN_puissance_KW', ''),
            'power_hp':           data.get('AWN_puissance_chevaux', ''),
            'fiscal_power':       data.get('AWN_puissance_fiscale', ''),
            'gearbox_type':       data.get('AWN_type_boite_vites', ''),
            'num_gears':          data.get('AWN_nbr_vitesses', ''),
            'max_speed':          data.get('AWN_max_speed', ''),

            # Dimensions & Weight
            'num_doors':          data.get('AWN_nbr_portes', ''),
            'num_seats':          data.get('AWN_nbr_places', ''),
            'length_mm':          data.get('AWN_longueur', ''),
            'width_mm':           data.get('AWN_largeur', ''),
            'height_mm':          data.get('AWN_hauteur', ''),
            'ptac_kg':            data.get('AWN_PTAC', ''),

            # Emissions & Consumption
            'co2_emissions':      data.get('AWN_emission_co_2', ''),
            'euro_standard':      data.get('AWN_norme_euro_standardise', ''),
            'mixed_consumption':  data.get('AWN_consommation_mixte', ''),

            # Tyres
            'tyres':              data.get('AWN_pneus', ''),

            # Dates
            'first_registration': data.get('AWN_date_mise_en_circulation', ''),
            'year_start':         data.get('AWN_annee_de_debut_modele', ''),
            'year_end':           data.get('AWN_annee_de_fin_modele', ''),

            # TecDoc
            'tecdoc_ktype':       data.get('AWN_k_type', ''),
            'tecdoc_ktypes':      data.get('AWN_k_types', []),
            'tecdoc_description': data.get('AWN_tecdoc_modele_description', ''),

            # Images
            'brand_image':        data.get('AWN_marque_image', ''),
            'model_image':        data.get('AWN_model_image', ''),
        }
