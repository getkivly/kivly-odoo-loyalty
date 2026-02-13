from odoo import models, api


class KivlyAPI(models.AbstractModel):
    """Clase helper para acceder a la configuración de Kivly"""
    _name = 'kivly.api.helper'
    _description = 'Kivly API Helper'

    @api.model
    def get_api_token(self):
        """Obtiene el token de API configurado"""
        config = self.env['kivly.config'].sudo().get_config()
        return config.api_token or ''

    @api.model
    def get_location_id(self):
        """Obtiene el Location ID configurado"""
        config = self.env['kivly.config'].sudo().get_config()
        return config.location_id or ''

    @api.model
    def is_configured(self):
        """Verifica si el módulo está configurado correctamente"""
        return self.env['kivly.config'].sudo().is_configured()
