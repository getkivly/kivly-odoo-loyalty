"""Pre-migration script para agregar campos de sincronización de clientes"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Pre-migración para asegurar compatibilidad con versiones anteriores
    """
    _logger.info('Pre-migración: Preparando campos de sincronización de clientes')
    
    # Verificar si los campos ya existen antes de agregarlos
    cr.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='kivly_config' AND column_name='customer_sync_enabled'
    """)
    
    if not cr.fetchone():
        _logger.info('Agregando campos de sincronización de clientes')
    else:
        _logger.info('Campos de sincronización ya existen, saltando')
