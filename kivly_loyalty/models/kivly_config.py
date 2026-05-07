"""Configuración de Kivly"""

import logging
import requests
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from odoo.tools import _

_logger = logging.getLogger(__name__)


class KivlyConfig(models.Model):
    """Configuración de Kivly"""
    _name = 'kivly.config'
    _description = 'Configuración de Kivly'
    _rec_name = 'name'

    name = fields.Char(string='Nombre', default='Configuración de Kivly', readonly=True)
    api_token = fields.Char(
        string='API Token',
        help='Token de autenticación para la API de Kivly'
    )
    location_id = fields.Char(
        string='Location ID',
        help='ID de ubicación para Kivly'
    )
    base_url = fields.Char(
        string='URL Base',
        default='https://api.getkivly.com',
        help='URL base del servidor de Kivly (Producción: https://api.getkivly.com, Desarrollo: http://localhost:9900)'
    )
    loyalty_url = fields.Char(
        string='URL de Loyalty (POS)',
        help='URL completa con token firmado para el sistema de loyalty en el POS. Ejemplo: https://api.getkivly.com/api/v1/loyalty/TOKEN_FIRMADO',
        required=False
    )
    active = fields.Boolean(string='Activo', default=True)
    last_sync = fields.Datetime(string='Última sincronización', readonly=True)
    sync_status = fields.Char(string='Estado de sincronización', readonly=True)
    
    # Configuración de sincronización de clientes
    customer_sync_enabled = fields.Boolean(
        string='Sincronización automática de clientes',
        default=True,
        help='Si está activo, los clientes se sincronizarán automáticamente con Kivly'
    )
    customer_sync_only_with_phone = fields.Boolean(
        string='Solo sincronizar clientes con teléfono',
        default=True,
        help='Solo sincronizar clientes que tengan número de teléfono'
    )
    
    # Configuración de eliminación (GDPR/LOPD)
    customer_deletion_action = fields.Selection([
        ('archive', 'Archivar - Mantiene todos los datos'),
        ('anonymize', 'Anonimizar - Cumple GDPR (Recomendado)')
    ], string='Acción al eliminar desde Kivly', default='anonymize',
        help='Cómo procesar cuando un cliente se elimina en Kivly:\n'
             '- Archivar: Desactiva el contacto pero mantiene todos los datos históricos (facturas, órdenes, etc.)\n'
             '- Anonimizar: Reemplaza datos personales por valores genéricos cumpliendo GDPR/LOPD (Recomendado para Europa)')
    
    # Seguridad de Webhooks
    webhook_secret = fields.Char(
        string='Webhook Secret',
        help='Clave secreta para validar webhooks de Kivly mediante HMAC SHA256'
    )
    webhook_url = fields.Char(
        string='URL del Webhook',
        compute='_compute_webhook_url',
        readonly=True,
        help='URL que debe configurar en Kivly para recibir webhooks'
    )

    @api.depends()
    def _compute_webhook_url(self):
        """Calcula la URL del webhook que debe configurarse en Kivly"""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            record.webhook_url = f"{base_url}/kivly/webhook/customer"

    @api.model
    def get_config(self):
        """Obtiene la configuración activa de Kivly"""
        # Primero intentar obtener el registro por XMLID (más confiable)
        try:
            config = self.env.ref('kivly_loyalty.kivly_config_default', raise_if_not_found=False)
            if config:
                # Asegurarse de que esté activo
                if not config.active:
                    config.write({'active': True})
                return config
        except Exception:
            pass
        
        # Si no existe por XMLID, buscar por activo
        config = self.search([('active', '=', True)], limit=1, order='id asc')
        if not config:
            # Buscar cualquier configuración existente
            config = self.search([], limit=1, order='id asc')
            if config:
                config.write({'active': True})
            else:
                # Solo crear si no existe ninguna configuración
                config = self.create({
                    'name': 'Configuración de Kivly',
                    'api_token': '',
                    'location_id': '',
                    'base_url': 'https://api.getkivly.com',
                    'active': True,
                })
        return config

    @api.model
    def get_api_token(self):
        """Obtiene el token de API configurado"""
        config = self.get_config()
        return config.api_token or ''

    @api.model
    def get_location_id(self):
        """Obtiene el Location ID configurado"""
        config = self.get_config()
        return config.location_id or ''

    @api.model
    def is_configured(self):
        """Verifica si el módulo está configurado correctamente"""
        config = self.get_config()
        return bool(config.api_token and config.location_id)
    
    @api.model
    def get_loyalty_url(self):
        """Obtiene la URL de loyalty configurada para el POS"""
        config = self.get_config()
        return config.loyalty_url or ''
    
    @api.model
    def is_loyalty_configured(self):
        """Verifica si la URL de loyalty está configurada"""
        config = self.get_config()
        return bool(config.loyalty_url)

    def _setup_kivly_backend(self):
        """Envía la configuración al backend de Kivly - OBLIGATORIO"""
        self.ensure_one()

        if (
            not (self.api_token and self.api_token.strip())
            or not (self.location_id and self.location_id.strip())
        ):
            raise ValidationError(_('Debe proporcionar el API Token y Location ID'))

        # Construir URL completa
        base_url = self.base_url or 'http://localhost:9900'
        url = f"{base_url.rstrip('/')}/api/v1/odoo/setup"

        # Preparar datos para enviar
        payload = {
            'api_token': self.api_token,
            'location_id': self.location_id,
            'odoo_version': self.env['ir.config_parameter'].sudo().get_param('web.base.version', 'unknown'),
        }

        try:
            _logger.info('Enviando configuración a Kivly: %s', url)

            # Hacer la llamada POST al backend de Kivly
            response = requests.post(
                url,
                json=payload,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.api_token}'
                },
                timeout=10
            )

            # Verificar respuesta - SOLO 200/201 son aceptables
            if response.status_code in [200, 201]:
                response_data = response.json()
                _logger.info('Configuración sincronizada exitosamente con Kivly: %s', response_data)

                # Actualizar estado de sincronización
                self.write({
                    'last_sync': fields.Datetime.now(),
                    'sync_status': 'Configuración sincronizada correctamente'
                })

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('¡Éxito!'),
                        'message': _('La configuración se sincronizó correctamente con Kivly.'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                # Cualquier otro código de estado es un ERROR
                error_msg = f'Error al sincronizar con Kivly: HTTP {response.status_code}'
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', error_data.get('message', error_msg))
                except (ValueError, KeyError):
                    error_msg = response.text or error_msg

                _logger.error('Error al sincronizar con Kivly: %s', error_msg)

                self.write({
                    'last_sync': fields.Datetime.now(),
                    'sync_status': f'Error: {error_msg}'
                })

                raise UserError(_(f'No se pudo guardar la configuración. Error de Kivly: {error_msg}'))

        except requests.exceptions.ConnectionError:
            error_msg = 'No se pudo conectar con el servidor de Kivly. Verifique que el servidor esté ejecutándose y la URL sea correcta.'
            _logger.error(error_msg)

            self.write({
                'sync_status': f'Error: {error_msg}'
            })

            raise UserError(_(error_msg))

        except requests.exceptions.Timeout:
            error_msg = 'Tiempo de espera agotado al conectar con Kivly. El servidor no respondió a tiempo.'
            _logger.error(error_msg)

            self.write({
                'sync_status': f'Error: {error_msg}'
            })

            raise UserError(_(error_msg))

        except UserError:
            # Re-lanzar UserError sin modificar
            raise

        except Exception as e:
            error_msg = f'Error inesperado al sincronizar con Kivly: {str(e)}'
            _logger.exception(error_msg)

            self.write({
                'sync_status': f'Error: {error_msg}'
            })

            raise UserError(_(error_msg))

    @api.model_create_multi
    def create(self, vals_list):
        """Override create - sincronización OBLIGATORIA si tiene credenciales completas"""
        records = super(KivlyConfig, self).create(vals_list)
        
        # Sincronizar OBLIGATORIAMENTE solo si tiene credenciales completas y no están vacías
        for record in records:
            if record.api_token and record.location_id and record.api_token.strip() and record.location_id.strip():
                # Si falla, se lanza excepción y no se guarda
                record._setup_kivly_backend()
        
        return records

    def write(self, vals):
        """Override write - sincronización OBLIGATORIA al actualizar credenciales"""
        # Si se está activando esta configuración, desactivar las demás
        if vals.get('active', False):
            other_configs = self.search([('active', '=', True), ('id', 'not in', self.ids)])
            if other_configs:
                other_configs.write({'active': False})
        
        result = super(KivlyConfig, self).write(vals)
        
        # Sincronizar OBLIGATORIAMENTE si se actualizaron las credenciales
        if 'api_token' in vals or 'location_id' in vals or 'base_url' in vals:
            for record in self:
                if (
                    record.api_token and record.api_token.strip()
                    and record.location_id and record.location_id.strip()
                ):
                    # Si falla, se lanza excepción y se hace rollback
                    record._setup_kivly_backend()
        
        return result

    def action_test_connection(self):
        """Botón para probar la conexión manualmente"""
        self.ensure_one()
        return self._setup_kivly_backend()
    
    def action_debug_config(self):
        """Botón para debug de configuración"""
        self.ensure_one()
        
        msg = f"""
        <h3>Debug de Configuración Kivly</h3>
        <ul>
            <li><b>ID:</b> {self.id}</li>
            <li><b>Nombre:</b> {self.name}</li>
            <li><b>API Token:</b> {'Configurado ✓' if self.api_token else 'VACÍO ✗'}</li>
            <li><b>Location ID:</b> {'Configurado ✓' if self.location_id else 'VACÍO ✗'}</li>
            <li><b>Base URL:</b> {self.base_url}</li>
            <li><b>Activo:</b> {'Sí ✓' if self.active else 'No ✗'}</li>
            <li><b>Estado:</b> {self.sync_status or 'Sin estado'}</li>
            <li><b>¿Configurado correctamente?:</b> {'SÍ ✓' if self.is_configured() else 'NO ✗'}</li>
        </ul>
        """
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Debug de Configuración',
                'message': msg,
                'type': 'info',
                'sticky': True,
            }
        }
