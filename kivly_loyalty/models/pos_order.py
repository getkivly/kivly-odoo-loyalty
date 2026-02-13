"""Orden de POS"""
import logging
import requests
from odoo import models, fields, api
from odoo.tools import _


_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    """Orden de POS"""
    _inherit = 'pos.order'

    kivly_synced = fields.Boolean(string='Sincronizado con Kivly', default=False, readonly=True)
    kivly_sync_date = fields.Datetime(string='Fecha de sincronización Kivly', readonly=True)
    kivly_order_id = fields.Char(string='ID de Orden en Kivly', readonly=True)

    def _prepare_kivly_invoice_data(self):
        """Prepara los datos de la factura/invoice para enviar a Kivly según su API"""
        self.ensure_one()

        # Preparar líneas de productos (items) - Precios en centavos
        items = []
        order_lines = getattr(self, 'lines', [])
        for line in order_lines:
            items.append({
                'id': str(line.product_id.id),
                'name': line.product_id.name,
                'quantity': int(line.qty),
                'price': int(line.price_subtotal_incl * 100),  # Convertir a centavos
                'type': 'product',
            })

        # Datos del cliente según estructura de Kivly
        customer_data = None
        external_customer_id = None
        kivly_customer_id = None

        partner = getattr(self, 'partner_id', None)
        if partner:
            phone = partner.phone or ''
            
            # Usar kivly_id si existe, sino usar el ID de Odoo
            kivly_customer_id = getattr(partner, 'kivly_id', None)
            
            customer_data = {
                'id': kivly_customer_id or str(partner.id),
                'name': partner.name,
                'email': partner.email or '',
                'phone': phone,
                'external_id': str(partner.id),
            }
            external_customer_id = kivly_customer_id or str(partner.id)

        # Calcular totales en centavos usando acceso seguro
        amount_total = getattr(self, 'amount_total', 0.0)
        amount_tax = getattr(self, 'amount_tax', 0.0)

        total_cents = int(amount_total * 100)
        subtotal_cents = int((amount_total - amount_tax) * 100)
        tax_cents = int(amount_tax * 100)
        discount_cents = 0  # Si tienes descuentos globales, calcularlos aquí

        # Calcular porcentaje de impuesto promedio
        tax_percentage = 0
        if subtotal_cents > 0:
            tax_percentage = int((tax_cents / subtotal_cents) * 100)

        # Obtener referencias de orden
        pos_reference = getattr(self, 'pos_reference', None)
        order_name = getattr(self, 'name', '')
        date_order = getattr(self, 'date_order', None)
        currency_id = getattr(self, 'currency_id', None)
        user_id = getattr(self, 'user_id', None)

        # Estructura de la factura según API de Kivly
        invoice_data = {
            'name': pos_reference or order_name,
            'creation_time': date_order.isoformat() if date_order else fields.Datetime.now().isoformat(),
            'close_time': fields.Datetime.now().isoformat(),
            'code': pos_reference or order_name,
            'source': 'Odoo POS',
            'external_location_id': self.env['kivly.config'].sudo().get_config().location_id,
            'external_customer_id': external_customer_id,
            'employee_name': getattr(user_id, 'name', 'Unknown') if user_id else 'Unknown',
            'items': items,
            'total': {
                'total': total_cents,
                'currency': getattr(currency_id, 'name', 'EUR') if currency_id else 'EUR',
                'tax': tax_percentage,
                'discount': discount_cents,
                'subtotal': subtotal_cents,
            },
            'customer': customer_data,
            'promotions': []  # Agregar promociones si las tienes
        }

        return invoice_data

    def _send_order_to_kivly(self):
        """Envía la orden/factura a Kivly para validación y procesamiento de puntos"""
        self.ensure_one()

        order_name = getattr(self, 'name', 'Unknown')
        order_id = getattr(self, 'id', 0)

        # Obtener configuración de Kivly
        config = self.env['kivly.config'].sudo().get_config()

        if not config.is_configured():
            _logger.warning('Kivly no está configurado. Orden %s no se sincronizará.', order_name)
            return False

        # Construir URL con el location_id según API de Kivly
        base_url = config.base_url or 'https://api.getkivly.com'
        location_id = config.location_id
        url = f"{base_url.rstrip('/')}/api/v1/loyalty/{location_id}"

        # Preparar datos de la factura
        invoice_data = self._prepare_kivly_invoice_data()

        try:
            _logger.info('Enviando factura %s a Kivly: %s', order_name, url)
            _logger.debug('Datos de factura: %s', invoice_data)

            # Hacer la llamada POST según API de Kivly
            response = requests.post(
                url,
                json=invoice_data,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {config.api_token}'
                },
                timeout=15
            )

            # Verificar respuesta
            if response.status_code in [200, 201]:
                response_data = response.json()
                _logger.info('Factura %s procesada en Kivly: %s', order_name, response_data)

                # Verificar el status de la respuesta de Kivly
                success = response_data.get('success', False)
                status = response_data.get('status', '')
                message = response_data.get('message', '')

                if success and status == 'accepted':
                    # Transacción aceptada
                    _logger.info('Factura %s aceptada por Kivly. %s', order_name, message)

                    # Marcar como sincronizado
                    self.write({
                        'kivly_synced': True,
                        'kivly_sync_date': fields.Datetime.now(),
                        'kivly_order_id': f"kivly_{order_id}_{fields.Datetime.now().timestamp()}",
                    })

                    return True
                else:
                    # Transacción rechazada
                    _logger.warning('Factura %s rechazada por Kivly: %s', order_name, message)
                    return False
            else:
                error_msg = f'Error al procesar factura en Kivly: HTTP {response.status_code}'
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', error_data.get('message', error_msg))
                except (ValueError, KeyError):
                    error_msg = response.text or error_msg

                _logger.error('Error al sincronizar factura %s con Kivly: %s', order_name, error_msg)
                return False

        except requests.exceptions.ConnectionError:
            _logger.error('No se pudo conectar con Kivly para sincronizar factura %s', order_name)
            return False

        except requests.exceptions.Timeout:
            _logger.error('Timeout al conectar con Kivly para factura %s', order_name)
            return False

        except Exception as e:
            _logger.exception('Error inesperado al sincronizar factura %s con Kivly: %s', order_name, e)
            return False

    @api.model
    def _order_fields(self, ui_order):
        """Override para capturar cuando se crea una orden desde el POS"""
        order_fields = super()._order_fields(ui_order)  # pylint: disable=no-member
        return order_fields

    def write(self, vals):
        """Override write para detectar cuando se confirma una orden"""
        result = super().write(vals)

        # Si se cambió el estado a 'paid' o 'done', enviar a Kivly
        if 'state' in vals and vals['state'] in ['paid', 'done']:
            for order in self:
                kivly_synced = getattr(order, 'kivly_synced', False)
                if not kivly_synced:
                    order._send_order_to_kivly()

        return result

    @api.model_create_multi
    def create(self, vals_list):
        """Override create para enviar órdenes nuevas que ya vienen confirmadas"""
        orders = super().create(vals_list)

        # Enviar a Kivly las órdenes que se crearon como 'paid' o 'done'
        for order in orders:
            order_state = getattr(order, 'state', '')
            kivly_synced = getattr(order, 'kivly_synced', False)
            if order_state in ['paid', 'done'] and not kivly_synced:
                order._send_order_to_kivly()

        return orders

    def action_pos_order_paid(self):
        """Override para capturar cuando una orden es pagada"""
        result = super().action_pos_order_paid()  # pylint: disable=no-member
        
        # Enviar a Kivly después de marcar como pagada
        for order in self:
            kivly_synced = getattr(order, 'kivly_synced', False)
            if not kivly_synced:
                order._send_order_to_kivly()
        
        return result

    def action_resync_kivly(self):
        """Acción manual para re-sincronizar con Kivly"""
        for order in self:
            order._send_order_to_kivly()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sincronización'),
                'message': _('Orden(es) enviada(s) a Kivly'),
                'type': 'success',
                'sticky': False,
            }
        }
