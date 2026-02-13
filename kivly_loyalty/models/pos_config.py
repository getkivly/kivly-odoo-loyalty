# -*- coding: utf-8 -*-

import logging
from odoo import models, fields

_logger = logging.getLogger(__name__)


class PosConfig(models.Model):
    _inherit = 'pos.config'

    kivly_discount_product_id = fields.Many2one(
        'product.product',
        string='Producto de Descuento Kivly',
        help='Producto usado para aplicar descuentos de recompensas Kivly',
        domain=[('available_in_pos', '=', True)],
    )

    def _get_special_products(self):
        """Incluir el producto de descuento Kivly en los productos especiales del POS.

        Los productos especiales se cargan siempre en el POS independientemente
        de las categorías configuradas. Esto garantiza que el producto de descuento
        esté disponible para aplicar recompensas Kivly.
        """
        result = super()._get_special_products()
        if self.kivly_discount_product_id:
            result |= self.kivly_discount_product_id
        return result
