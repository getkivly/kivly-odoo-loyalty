"""Webhooks de Kivly para sincronización bidireccional"""

import logging
import hmac
import hashlib
import json
from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)


class KivlyWebhook(http.Controller):
    """Controller para recibir webhooks de Kivly"""

    def _handle_customer_deletion(self, kivly_id, external_id, customer_data):
        """
        Maneja la eliminación/archivado/anonimización de clientes
        
        :param kivly_id: ID del cliente en Kivly
        :param external_id: ID del cliente en Odoo (si existe)
        :param customer_data: Datos completos del cliente
        :return: JSON response
        """
        try:
            if not kivly_id and not external_id:
                _logger.error('Datos de cliente incompletos en webhook de eliminación')
                return request.make_json_response({
                    'status': 'error',
                    'message': 'Missing required fields: id or external_id'
                })
            
            Partner = request.env['res.partner'].sudo()
            
            # Buscar cliente existente
            partner = None
            
            # 1. Buscar por kivly_id (más confiable)
            if kivly_id:
                partner = Partner.search([('kivly_id', '=', kivly_id)], limit=1)
            
            # 2. Buscar por external_id (ID de Odoo)
            if not partner and external_id:
                try:
                    partner = Partner.browse(int(external_id))
                    if not partner.exists():
                        partner = None
                except (ValueError, TypeError):
                    pass
            
            if not partner:
                _logger.warning('Cliente no encontrado para eliminar: kivly_id=%s, external_id=%s', kivly_id, external_id)
                return request.make_json_response({
                    'status': 'ok',
                    'message': 'Customer not found in Odoo',
                    'action': 'not_found'
                })
            
            # Obtener configuración para decidir cómo procesar la eliminación
            config = request.env['kivly.config'].sudo().get_config()
            deletion_action = config.customer_deletion_action if config else 'archive'
            
            _logger.info('=== ELIMINACIÓN DE CLIENTE ===')
            _logger.info('Configuración: %s', deletion_action)
            _logger.info('Cliente: %s (ID: %s)', partner.name, partner.id)
            
            partner_id = partner.id
            partner_name = partner.name
            
            # Siempre desvincular de Kivly
            vals = {
                'kivly_id': False,
                'kivly_sync_enabled': False
            }
            
            if deletion_action == 'anonymize':
                # Anonimizar datos personales (GDPR compliant)
                vals.update({
                    'name': f'Cliente Anonimizado #{partner_id}',
                    'email': False,
                    'phone': False,
                    'street': False,
                    'street2': False,
                    'city': False,
                    'zip': False,
                    'vat': False,
                    'comment': 'Datos anonimizados por solicitud de eliminación',
                    'active': False  # También archivamos
                })
                partner.with_context(skip_kivly_sync=True).write(vals)
                action_taken = 'anonymized'
                message = f'Cliente anonimizado desde Kivly: {partner_name} (ID: {partner_id})'
                _logger.info('✅ %s', message)
                    
            else:  # 'archive' (por defecto)
                # Archivar en lugar de eliminar (más seguro)
                vals['active'] = False
                partner.with_context(skip_kivly_sync=True).write(vals)
                action_taken = 'archived'
                message = f'Cliente archivado desde Kivly: {partner_name} (ID: {partner_id})'
            
            _logger.info('%s', message)
            
            return request.make_json_response({
                'status': 'ok',
                'action': action_taken,
                'odoo_partner_id': partner_id,
                'message': message
            })
            
        except Exception as e:
            _logger.exception('Error procesando eliminación de cliente: %s', e)
            return request.make_json_response({
                'status': 'error',
                'message': str(e)
            })

    def _validate_signature(self, payload, signature):
        """
        Valida la firma HMAC del webhook
        
        :param payload: Datos del webhook en bytes
        :param signature: Firma enviada por Kivly en header X-Kivly-Signature
        :return: True si la firma es válida, False en caso contrario
        """
        config = request.env['kivly.config'].sudo().get_config()
        
        # Si no hay webhook_secret configurado, no validar (modo desarrollo)
        if not config or not config.webhook_secret:
            _logger.warning('Webhook secret no configurado - modo desarrollo sin validación')
            return True
        
        # Si no hay signature, rechazar
        if not signature:
            _logger.error('No se recibió header X-Kivly-Signature')
            return False
        
        # Calcular HMAC SHA256
        expected_signature = hmac.new(
            config.webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Log para debug
        _logger.debug('Signature esperada: %s...', expected_signature[:20])
        _logger.debug('Signature recibida: %s...', signature[:20])
        
        # Comparación segura contra timing attacks
        is_valid = hmac.compare_digest(signature, expected_signature)
        
        if not is_valid:
            _logger.error('Firma inválida. Esperada: %s..., Recibida: %s...', expected_signature[:20], signature[:20])
        
        return is_valid

    @http.route('/kivly/webhook/customer', type='http', auth='public', methods=['POST'], csrf=False)
    def webhook_customer_create_or_update(self, **kwargs):
        """
        Webhook para crear o actualizar clientes desde Kivly
        
        Payload esperado (estructura real de Kivly):
        {
            "webhook_id": "uuid",
            "event": "customer.created" | "customer.updated",
            "payload": {
                "id": "uuid",
                "event": "customer.created",
                "timestamp": "2026-02-13T12:00:00",
                "data": {
                    "id": "kivly_customer_id",
                    "name": "Nombre del cliente",
                    "phone": "+1234567890",
                    "email": "email@example.com",
                    "loyalty_points": 100,
                    "address": "Calle 123",
                    "city": "Ciudad",
                    "country": "País",
                    "postal_code": "12345",
                    "personal_id": "DNI/RUC",
                    "date_of_birth": "2000-01-01",
                    "gender": "male|female|other",
                    "external_id": "123"
                }
            }
        }
        """
        try:
            # Obtener signature del header
            signature = request.httprequest.headers.get('X-Kivly-Signature', '')
            
            # Obtener payload raw para validar signature
            payload_raw = request.httprequest.get_data()
            
            # Log para debug
            _logger.info('Webhook recibido - Signature header: %s', signature)
            _logger.info('Payload length: %s bytes', len(payload_raw))
            
            # Validar signature
            if not self._validate_signature(payload_raw, signature):
                _logger.error('Firma de webhook inválida. Header recibido: %s', signature)
                return request.make_json_response({
                    'status': 'error',
                    'message': 'Invalid signature'
                })
            
            # Parsear datos
            data = json.loads(payload_raw.decode('utf-8')) if payload_raw else {}
            
            # Verificar que el evento sea de cliente
            webhook_event = data.get('event')
            
            # Filtrar eventos no relacionados con clientes
            if webhook_event and not webhook_event.startswith('customer.'):
                _logger.info('Webhook ignorado (no es evento de cliente): %s', webhook_event)
                return request.make_json_response({
                    'status': 'ignored',
                    'message': f'Este endpoint solo procesa eventos de clientes. Recibido: {webhook_event}'
                })
            
            # Estructura real de Kivly: los datos del cliente están en 'data'
            customer_data = data.get('data', {})
            
            # Fallback a estructura alternativa por compatibilidad
            if not customer_data:
                payload_obj = data.get('payload', {})
                customer_data = payload_obj.get('data', {}) if isinstance(payload_obj, dict) else {}
            
            # Último fallback: estructura antigua
            if not customer_data:
                customer_data = data.get('customer', {})
            
            _logger.info('Webhook recibido de Kivly: %s', webhook_event)
            _logger.info('Cliente ID: %s, Nombre: %s', customer_data.get('id'), customer_data.get('name'))
            
            # Extraer datos del cliente
            kivly_id = customer_data.get('id')
            phone = customer_data.get('phone')
            name = customer_data.get('name')
            email = customer_data.get('email')
            points = customer_data.get('loyalty_points', customer_data.get('points', 0))
            external_id = customer_data.get('external_id')  # ID de Odoo
            
            # Campos adicionales opcionales
            address = customer_data.get('address')
            city = customer_data.get('city')
            country = customer_data.get('country')
            postal_code = customer_data.get('postal_code')
            personal_id = customer_data.get('personal_id')
            date_of_birth = customer_data.get('date_of_birth')
            gender = customer_data.get('gender')
            
            # Tags no vienen en el payload de Kivly, por ahora
            tags = customer_data.get('tags', [])
            
            # Si es un evento de eliminación, manejar de forma especial
            if webhook_event == 'customer.deleted':
                return self._handle_customer_deletion(kivly_id, external_id, customer_data)
            
            # Para crear/actualizar, validar campos obligatorios
            if not kivly_id or not phone:
                _logger.error('Datos de cliente incompletos en webhook')
                return request.make_json_response({
                    'status': 'error',
                    'message': 'Missing required fields: id or phone'
                })
            
            Partner = request.env['res.partner'].sudo()
            
            # Buscar cliente existente
            partner = None
            
            # 1. Buscar por kivly_id (más confiable)
            if kivly_id:
                partner = Partner.search([('kivly_id', '=', kivly_id)], limit=1)
            
            # 2. Buscar por external_id (ID de Odoo)
            if not partner and external_id:
                try:
                    partner = Partner.browse(int(external_id))
                    if not partner.exists():
                        partner = None
                except (ValueError, TypeError):
                    pass
            
            # 3. Buscar por teléfono (último recurso)
            if not partner and phone:
                partner = Partner.search([('phone', '=', phone)], limit=1)

            vals = {
                'name': name or phone,
                'email': email or False,
                'phone': phone,
                'kivly_id': kivly_id,
                'kivly_points': points,
                'kivly_sync_enabled': True,
                'last_kivly_sync': fields.Datetime.now(),
            }
            
            # Campos adicionales opcionales
            if address:
                vals['street'] = address
            
            if city:
                vals['city'] = city
            
            if country:
                # Buscar país por nombre
                country_obj = request.env['res.country'].sudo().search([('name', 'ilike', country)], limit=1)
                if country_obj:
                    vals['country_id'] = country_obj.id
            
            if postal_code:
                vals['zip'] = postal_code
            
            if personal_id:
                vals['vat'] = personal_id
            
            # Fecha de nacimiento y género (si existen como campos personalizados)
            if date_of_birth and 'date_of_birth' in Partner._fields:
                # Convertir string ISO a datetime
                try:
                    from dateutil import parser as dateutil_parser
                    vals['date_of_birth'] = dateutil_parser.parse(date_of_birth).date()
                except (ValueError, TypeError):
                    _logger.warning('No se pudo parsear fecha de nacimiento: %s', date_of_birth)
            
            if gender and 'gender' in Partner._fields:
                vals['gender'] = gender
            
            if tags:
                # Buscar o crear tags/categorías
                category_ids = []
                for tag_name in tags:
                    category = request.env['res.partner.category'].sudo().search([('name', '=', tag_name)], limit=1)
                    if not category:
                        category = request.env['res.partner.category'].sudo().create({'name': tag_name})
                    category_ids.append(category.id)
                if category_ids:
                    vals['category_id'] = [(6, 0, category_ids)]
            
            if partner:
                # Actualizar cliente existente
                # Usar super().write() para evitar trigger de sincronización
                partner.with_context(skip_kivly_sync=True).write(vals)
                _logger.info('Cliente actualizado desde Kivly: %s (ID: %s)', partner.name, partner.id)
                
                return request.make_json_response({
                    'status': 'ok',
                    'action': 'updated',
                    'odoo_partner_id': partner.id
                })
            else:
                # Crear nuevo cliente
                vals['customer_rank'] = 1  # Marcar como cliente
                partner = Partner.with_context(skip_kivly_sync=True).create(vals)
                _logger.info('Cliente creado desde Kivly: %s (ID: %s)', partner.name, partner.id)
                
                return request.make_json_response({
                    'status': 'ok',
                    'action': 'created',
                    'odoo_partner_id': partner.id
                })
                
        except Exception as e:
            _logger.exception('Error procesando webhook de Kivly: %s', e)
            return request.make_json_response({
                'status': 'error',
                'message': str(e)
            })

    @http.route('/kivly/webhook/customer/delete', type='http', auth='public', methods=['POST'], csrf=False)
    def webhook_customer_delete(self, **kwargs):
        """
        Webhook para eliminar/archivar clientes desde Kivly
        
        Payload esperado (estructura real de Kivly):
        {
            "webhook_id": "uuid",
            "event": "customer.deleted",
            "payload": {
                "id": "uuid",
                "event": "customer.deleted",
                "timestamp": "2026-02-13T12:00:00",
                "data": {
                    "id": "kivly_customer_id",
                    "external_id": "123"
                }
            }
        }
        """
        try:
            # Obtener signature del header
            signature = request.httprequest.headers.get('X-Kivly-Signature', '')
            
            # Obtener payload raw para validar signature
            payload_raw = request.httprequest.get_data()
            
            # Validar signature
            if not self._validate_signature(payload_raw, signature):
                _logger.error('Firma de webhook inválida')
                return request.make_json_response({
                    'status': 'error',
                    'message': 'Invalid signature'
                })
            
            # Parsear datos
            data = json.loads(payload_raw.decode('utf-8')) if payload_raw else {}
            
            # Estructura real de Kivly: payload.data contiene los datos
            webhook_event = data.get('event')
            payload_obj = data.get('payload', {})
            customer_data = payload_obj.get('data', {})
            
            # Fallback a estructura antigua por compatibilidad
            if not customer_data:
                customer_data = data.get('customer', {})
            
            _logger.info('Webhook de eliminación recibido de Kivly: %s', webhook_event)
            _logger.info('Datos del cliente: %s', customer_data)
            
            # Extraer datos del cliente
            kivly_id = customer_data.get('id')
            external_id = customer_data.get('external_id')
            
            if not kivly_id and not external_id:
                _logger.error('Datos de cliente incompletos en webhook de eliminación')
                return request.make_json_response({
                    'status': 'error',
                    'message': 'Missing required fields: id or external_id'
                })
            
            Partner = request.env['res.partner'].sudo()
            
            # Buscar cliente existente
            partner = None
            
            # 1. Buscar por kivly_id (más confiable)
            if kivly_id:
                partner = Partner.search([('kivly_id', '=', kivly_id)], limit=1)
            
            # 2. Buscar por external_id (ID de Odoo)
            if not partner and external_id:
                try:
                    partner = Partner.browse(int(external_id))
                    if not partner.exists():
                        partner = None
                except (ValueError, TypeError):
                    pass
            
            if not partner:
                _logger.warning('Cliente no encontrado para eliminar: kivly_id=%s, external_id=%s', kivly_id, external_id)
                return request.make_json_response({
                    'status': 'ok',
                    'message': 'Customer not found in Odoo',
                    'action': 'not_found'
                })
            
            # Obtener configuración para decidir cómo procesar la eliminación
            config = request.env['kivly.config'].sudo().get_config()
            deletion_action = config.customer_deletion_action if config else 'archive'
            
            _logger.info('=== ELIMINACIÓN DE CLIENTE ===')
            _logger.info('Configuración: %s', deletion_action)
            _logger.info('Cliente: %s (ID: %s)', partner.name, partner.id)
            
            partner_id = partner.id
            partner_name = partner.name
            
            # Siempre desvincular de Kivly
            vals = {
                'kivly_id': False,
                'kivly_sync_enabled': False
            }
            
            if deletion_action == 'anonymize':
                # Anonimizar datos personales (GDPR compliant)
                vals.update({
                    'name': f'Cliente Anonimizado #{partner_id}',
                    'email': False,
                    'phone': False,
                    'street': False,
                    'street2': False,
                    'city': False,
                    'zip': False,
                    'vat': False,
                    'comment': 'Datos anonimizados por solicitud de eliminación',
                    'active': False  # También archivamos
                })
                partner.with_context(skip_kivly_sync=True).write(vals)
                action_taken = 'anonymized'
                message = f'Cliente anonimizado desde Kivly: {partner_name} (ID: {partner_id})'
                _logger.info('✅ %s', message)
                    
            else:  # 'archive' (por defecto)
                # Archivar en lugar de eliminar (más seguro)
                vals['active'] = False
                partner.with_context(skip_kivly_sync=True).write(vals)
                action_taken = 'archived'
                message = f'Cliente archivado desde Kivly: {partner_name} (ID: {partner_id})'
            
            _logger.info('%s', message)
            
            return request.make_json_response({
                'status': 'ok',
                'action': action_taken,
                'odoo_partner_id': partner_id,
                'message': message
            })
            
        except Exception as e:
            _logger.exception('Error procesando webhook de eliminación de Kivly: %s', e)
            return request.make_json_response({
                'status': 'error',
                'message': str(e)
            })

    @http.route('/kivly/webhook/transaction', type='http', auth='public', methods=['POST'], csrf=False)
    def webhook_transaction(self, **kwargs):
        """
        Webhook para transacciones de puntos desde Kivly
        
        Payload esperado:
        {
            "event": "point_transaction.created",
            "data": {
                "customer_id": "kivly_customer_id",
                "points": 100,
                "type": "EARN" | "REDEEM",
                "description": "..."
            }
        }
        """
        try:
            # Obtener signature del header
            signature = request.httprequest.headers.get('X-Kivly-Signature', '')
            
            # Obtener payload raw para validar signature
            payload_raw = request.httprequest.get_data()
            
            # Validar signature
            if not self._validate_signature(payload_raw, signature):
                _logger.error('Firma de webhook inválida')
                return request.make_json_response({
                    'status': 'error',
                    'message': 'Invalid signature'
                })
            
            # Parsear datos
            data = json.loads(payload_raw.decode('utf-8')) if payload_raw else {}
            
            webhook_event = data.get('event')
            transaction_data = data.get('data', {})
            
            _logger.info('Webhook de transacción recibido: %s', webhook_event)
            
            # Extraer datos de la transacción
            customer_id = transaction_data.get('customer_id')
            points = transaction_data.get('points', 0)
            transaction_type = transaction_data.get('type', 'UNKNOWN')
            
            if not customer_id:
                _logger.error('customer_id no encontrado en webhook de transacción')
                return request.make_json_response({
                    'status': 'error',
                    'message': 'Missing customer_id'
                })
            
            # Buscar cliente por kivly_id
            Partner = request.env['res.partner'].sudo()
            partner = Partner.search([('kivly_id', '=', customer_id)], limit=1)
            
            if not partner:
                _logger.warning('Cliente con kivly_id=%s no encontrado para actualizar puntos', customer_id)
                return request.make_json_response({
                    'status': 'ok',
                    'message': 'Customer not found in Odoo',
                    'action': 'skipped'
                })
            
            # Obtener puntos actuales desde Kivly
            config = request.env['kivly.config'].sudo().get_config()
            if config and config.is_configured():
                try:
                    import requests as req
                    base_url = config.base_url or 'https://api.getkivly.com'
                    url = f"{base_url.rstrip('/')}/api/v1/customers/{customer_id}"
                    
                    headers = {
                        'Authorization': f'Bearer {config.api_token}'
                    }
                    
                    response = req.get(url, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        customer_info = response.json()
                        current_points = customer_info.get('loyalty_points', customer_info.get('points', 0))
                        
                        # Actualizar puntos en Odoo
                        partner.with_context(skip_kivly_sync=True).write({
                            'kivly_points': current_points,
                            'last_kivly_sync': fields.Datetime.now()
                        })
                        
                        _logger.info('Puntos actualizados para %s: %s', partner.name, current_points)
                        
                        return request.make_json_response({
                            'status': 'ok',
                            'action': 'points_updated',
                            'odoo_partner_id': partner.id,
                            'new_points': current_points
                        })
                except Exception as e:
                    _logger.error('Error al obtener puntos de Kivly: %s', e)
            
            # Si no se pudo obtener de la API, retornar OK
            return request.make_json_response({
                'status': 'ok',
                'action': 'acknowledged',
                'message': 'Transaction acknowledged but points not updated'
            })
            
        except Exception as e:
            _logger.exception('Error procesando webhook de transacción de Kivly: %s', e)
            return request.make_json_response({
                'status': 'error',
                'message': str(e)
            })

    @http.route('/kivly/webhook/test', type='http', auth='public', methods=['POST', 'GET'], csrf=False)
    def webhook_test(self, **kwargs):
        """Endpoint de prueba para webhooks"""
        _logger.info('Webhook de prueba recibido')
        return request.make_json_response({
            'status': 'ok',
            'message': 'Webhook test successful'
        })

