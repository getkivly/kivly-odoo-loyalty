"""Migration script para agregar soporte de sincronización de clientes"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Migración post-instalación para configurar sincronización de clientes
    
    Esta migración:
    - Habilita sincronización automática en la configuración de Kivly
    - Marca todos los clientes existentes como sincronizables (si tienen teléfono)
    """
    
    _logger.info('Iniciando migración de sincronización de clientes Kivly')
    
    # 1. Habilitar sincronización automática en la configuración
    cr.execute("""
        UPDATE kivly_config 
        SET customer_sync_enabled = TRUE,
            customer_sync_only_with_phone = TRUE
        WHERE id IS NOT NULL
    """)
    
    _logger.info('Sincronización automática habilitada en configuración Kivly')
    
    # 2. Habilitar sincronización para clientes existentes que tengan teléfono
    # Primero verificamos si existe la columna mobile
    cr.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='res_partner' AND column_name='mobile'
    """)
    has_mobile = bool(cr.fetchone())
    
    if has_mobile:
        cr.execute("""
            UPDATE res_partner 
            SET kivly_sync_enabled = TRUE
            WHERE (mobile IS NOT NULL AND mobile != '')
               OR (phone IS NOT NULL AND phone != '')
        """)
    else:
        cr.execute("""
            UPDATE res_partner 
            SET kivly_sync_enabled = TRUE
            WHERE phone IS NOT NULL AND phone != ''
        """)
    
    affected_rows = cr.rowcount
    _logger.info('%s clientes marcados como sincronizables con Kivly', affected_rows)
    
    _logger.info('Migración de sincronización de clientes Kivly completada')
