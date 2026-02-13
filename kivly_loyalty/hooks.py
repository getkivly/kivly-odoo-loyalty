"""Post-install hooks para kivly_loyalty"""

import logging
from odoo.api import Environment

_logger = logging.getLogger(__name__)


def post_init_hook(cr, registry):  # pylint: disable=unused-argument
    """Ejecutar después de instalar/actualizar el módulo"""

    _logger.info("Ejecutando post_init_hook de kivly_loyalty...")

    # Limpiar registros duplicados de configuración
    cr.execute("""
        SELECT id FROM kivly_config
        ORDER BY id ASC
    """)
    all_configs = cr.fetchall()

    if len(all_configs) > 1:
        # Mantener solo el primero
        keep_id = all_configs[0][0]
        delete_ids = [config[0] for config in all_configs[1:]]

        _logger.warning(
            "Encontrados %s registros de configuración. Manteniendo ID %s, eliminando %s",
            len(all_configs), keep_id, delete_ids
        )

        cr.execute("""
            DELETE FROM kivly_config
            WHERE id IN %s
        """, (tuple(delete_ids),))

        _logger.info("Registros duplicados eliminados: %s", delete_ids)

    # Asegurar que el registro restante esté activo
    cr.execute("""
        UPDATE kivly_config
        SET active = TRUE
    """)

    # Configurar el producto de descuento en todos los POS que no lo tengan
    env = Environment(cr, 1, {})  # UID 1 = admin

    try:
        # Buscar el producto de descuento Kivly
        discount_product = env.ref('kivly_loyalty.product_kivly_discount', raise_if_not_found=False)

        if discount_product:
            _logger.info("Producto de descuento Kivly encontrado: ID %s", discount_product.id)

            # Actualizar todos los POS configs que no tengan producto de descuento configurado
            cr.execute("""
                UPDATE pos_config
                SET kivly_discount_product_id = %s
                WHERE kivly_discount_product_id IS NULL
            """, (discount_product.id,))

            updated_count = cr.rowcount
            if updated_count > 0:
                _logger.info("Producto de descuento configurado en %s puntos de venta", updated_count)
        else:
            _logger.warning("No se encontró el producto de descuento Kivly (kivly_loyalty.product_kivly_discount)")

    except Exception as e:  # pylint: disable=broad-except
        _logger.error("Error al configurar el producto de descuento: %s", e)

    _logger.info("Post_init_hook completado")
