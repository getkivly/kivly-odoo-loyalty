"""Extensión de res.partner para sincronización con Kivly"""

import logging
import requests
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    """Extensión de res.partner para sincronización bidireccional con Kivly"""
    _inherit = 'res.partner'
    # pylint: disable=no-member

    kivly_id = fields.Char(
        string='Kivly ID',
        readonly=True,
        help='ID único del cliente en Kivly',
        index=True,
        copy=False
    )
    kivly_points = fields.Integer(
        string='Puntos Kivly',
        readonly=True,
        help='Puntos de lealtad en Kivly (solo lectura)'
    )
    kivly_sync_enabled = fields.Boolean(
        string='Sincronizar con Kivly',
        default=True,
        help='Si está activo, este cliente se sincronizará automáticamente con Kivly'
    )
    last_kivly_sync = fields.Datetime(
        string='Última sincronización Kivly',
        readonly=True
    )

    def _get_phone_number(self):
        """Obtiene el número de teléfono del partner."""
        self.ensure_one()
        return self.phone or False

    @api.model_create_multi
    def create(self, vals_list):
        """Override create para sincronizar nuevos clientes con Kivly"""
        partners = super(ResPartner, self).create(vals_list)

        # Evitar sincronización circular si viene del webhook
        if self.env.context.get('skip_kivly_sync'):
            return partners

        # Sincronizar con Kivly después de crear
        for partner in partners:
            if partner.kivly_sync_enabled and partner._get_phone_number():
                partner._sync_to_kivly('create')

        return partners

    def write(self, vals):
        """Override write para sincronizar actualizaciones con Kivly"""
        result = super(ResPartner, self).write(vals)

        # Evitar sincronización circular si viene del webhook
        if self.env.context.get('skip_kivly_sync'):
            return result

        # Solo sincronizar si cambiaron campos relevantes
        sync_fields = {
            'name', 'phone', 'email', 'street', 'street2',
            'city', 'country_id', 'zip', 'vat', 'category_id',
            'date_of_birth', 'gender',
        }
        if sync_fields & set(vals.keys()):
            for partner in self:
                if partner.kivly_sync_enabled and partner._get_phone_number() and partner.kivly_id:
                    partner._sync_to_kivly('update')

        return result

    def _sync_to_kivly(self, operation='create'):
        """
        Sincroniza el cliente con Kivly
        
        Campos sincronizados:
        - name: Nombre completo del cliente
        - email: Correo electrónico
        - phone: Número de teléfono
        - address: Dirección completa (street + street2)
        - city: Ciudad
        - country: País
        - postal_code: Código postal (zip)
        - personal_id: ID personal (vat/RUC/DNI)
        - tags: Categorías/Tags del contacto
        - date_of_birth: Fecha de nacimiento (si existe)
        - gender: Género (si existe)
        - external_id: ID de Odoo
        - location_id: ID de ubicación de Kivly

        :param operation: 'create' o 'update'
        """
        self.ensure_one()

        # Verificar configuración
        config = self.env['kivly.config'].get_config()
        if not config or not config.is_configured():
            _logger.warning('Kivly no está configurado, saltando sincronización')
            return

        # Verificar si la sincronización está habilitada
        if not config.customer_sync_enabled:
            _logger.debug('Sincronización de clientes deshabilitada en configuración')
            return

        # Validar que tenga teléfono (requisito de Kivly)
        phone_number = self._get_phone_number()
        if not phone_number:
            _logger.warning('Cliente %s no tiene teléfono, no se puede sincronizar con Kivly', self.name)
            return

        try:
            # Construir URL
            base_url = config.base_url or 'https://api.getkivly.com'

            if operation == 'create':
                url = f"{base_url.rstrip('/')}/api/v1/customers"
                method = 'POST'
            else:
                if not self.kivly_id:
                    return
                url = f"{base_url.rstrip('/')}/api/v1/customers/{self.kivly_id}"
                method = 'PUT'

            # Preparar payload con todos los campos disponibles
            payload = {
                'name': self.name or '',
                'phone': phone_number,
                'email': self.email or '',
                'external_id': str(self.id),  # External ID de Odoo en Kivly
                'location_id': config.location_id
            }
            
            # Agregar campos opcionales si existen
            # Dirección completa
            if self.street:
                address_parts = [self.street]
                if self.street2:
                    address_parts.append(self.street2)
                payload['address'] = ', '.join(address_parts)
            
            # Ciudad
            if self.city:
                payload['city'] = self.city
            
            # País
            if self.country_id:
                payload['country'] = self.country_id.name
            
            # Código postal
            if self.zip:
                payload['postal_code'] = self.zip
            
            # ID personal (VAT/RUC/DNI)
            if self.vat:
                payload['personal_id'] = self.vat
            
            # Tags/Categorías
            if self.category_id:
                payload['tags'] = [tag.name for tag in self.category_id]
            
            # Fecha de nacimiento (si existe el campo personalizado)
            if hasattr(self, 'date_of_birth') and self.date_of_birth:
                payload['date_of_birth'] = self.date_of_birth.isoformat()
            
            # Género (si existe el campo personalizado)
            if hasattr(self, 'gender') and self.gender:
                payload['gender'] = self.gender
            # Headers
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {config.api_token}'
            }

            # Hacer la llamada
            if method == 'POST':
                response = requests.post(url, json=payload, headers=headers, timeout=10)
            else:
                response = requests.put(url, json=payload, headers=headers, timeout=10)

            # Procesar respuesta
            if response.status_code in [200, 201]:
                response_data = response.json()
                kivly_customer_id = response_data.get('id') or response_data.get('customer_id')

                # Actualizar kivly_id si es creación
                if operation == 'create' and kivly_customer_id:
                    super(ResPartner, self).write({
                        'kivly_id': kivly_customer_id,
                        'last_kivly_sync': fields.Datetime.now()
                    })
                else:
                    super(ResPartner, self).write({
                        'last_kivly_sync': fields.Datetime.now()
                    })

                _logger.info('Cliente %s sincronizado exitosamente con Kivly', self.name)

            else:
                error_msg = f'Error al sincronizar cliente con Kivly: HTTP {response.status_code}'
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', error_data.get('message', error_msg))
                except (ValueError, KeyError):
                    error_msg = response.text or error_msg

                _logger.error('Error al sincronizar cliente %s: %s', self.name, error_msg)

        except requests.exceptions.RequestException as e:
            _logger.error('Error de conexión al sincronizar cliente %s con Kivly: %s', self.name, e)
        except Exception as e:
            _logger.exception('Error inesperado al sincronizar cliente %s con Kivly: %s', self.name, e)

    def action_sync_to_kivly(self):
        """Acción manual para sincronizar cliente con Kivly"""
        for partner in self:
            if not partner._get_phone_number():
                raise UserError('El cliente debe tener un número de teléfono para sincronizar con Kivly')

            operation = 'update' if partner.kivly_id else 'create'
            partner._sync_to_kivly(operation)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '¡Sincronizado!',
                'message': 'Cliente(s) sincronizado(s) con Kivly exitosamente',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_fetch_kivly_points(self):
        """Obtiene los puntos actuales del cliente desde Kivly"""
        self.ensure_one()

        if not self.kivly_id:
            raise UserError('Este cliente no está vinculado con Kivly')

        config = self.env['kivly.config'].get_config()
        if not config or not config.is_configured():
            raise UserError('Kivly no está configurado')

        try:
            base_url = config.base_url or 'https://api.getkivly.com'
            url = f"{base_url.rstrip('/')}/api/v1/customers/{self.kivly_id}"

            headers = {
                'Authorization': f'Bearer {config.api_token}'
            }

            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                points = data.get('points', 0)

                self.write({'kivly_points': points})

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Puntos actualizados',
                        'message': f'El cliente tiene {points} puntos en Kivly',
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise UserError(f'Error al obtener puntos de Kivly: HTTP {response.status_code}')

        except Exception as e:
            raise UserError(f'Error al conectar con Kivly: {str(e)}')
