"""
Vehicle lookup tasks.

Async Celery tasks for looking up vehicle data by matrícula or VIN.
Used for batch lookups; individual lookups are handled synchronously
via the graph blueprint AJAX endpoint.
"""
from app.tasks.celery_app import celery


@celery.task(
    name='app.tasks.vehicle.lookup_vehicle',
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=2,
)
def lookup_vehicle(self, plate_or_vin: str, case_id: int = None, node_id: str = None):
    """
    Look up vehicle data by Spanish matrícula or VIN (número de bastidor).

    Args:
        plate_or_vin: License plate (e.g. '1234ABC') or 17-char VIN.
        case_id:      Optional case ID for audit context.
        node_id:      Optional Neo4j node ID to update after lookup.

    Returns:
        dict: {success, plate_or_vin, vehicle_data, source, error}
    """
    self.update_state(
        state='PROGRESS',
        meta={'current': 10, 'total': 100, 'status': 'Iniciando consulta…', 'progress': 10},
    )

    try:
        from app.plugins import plugin_manager

        self.update_state(
            state='PROGRESS',
            meta={'current': 40, 'total': 100, 'status': 'Consultando registro de vehículos…', 'progress': 40},
        )

        result = plugin_manager.execute_vehicle_lookup(plate_or_vin)

        self.update_state(
            state='PROGRESS',
            meta={'current': 80, 'total': 100, 'status': 'Procesando resultado…', 'progress': 80},
        )

        inner = result.get('result', {})

        # Optionally update the Neo4j node if node_id was provided
        if node_id and inner.get('vehicle_data') and result.get('success'):
            try:
                from app.services.graph_service import GraphService
                from app.models.graph import NodeType
                vehicle_data = inner['vehicle_data']
                props = {k: v for k, v in vehicle_data.items() if v}
                GraphService().update_node(node_id, NodeType.VEHICLE, props)
            except Exception:
                pass  # Non-fatal; data is still returned

        return {
            'success': result.get('success', False),
            'plate_or_vin': plate_or_vin,
            'case_id': case_id,
            'node_id': node_id,
            'vehicle_data': inner.get('vehicle_data', {}),
            'source': inner.get('source', ''),
            'query_type': inner.get('query_type', ''),
            'error': inner.get('error') or result.get('error', ''),
        }

    except Exception as e:
        return {
            'success': False,
            'plate_or_vin': plate_or_vin,
            'error': str(e),
        }
