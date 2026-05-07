# -*- coding: utf-8 -*-
{
    "name": "Kivly Loyalty",
    "summary": "Tarjetas digitales en Apple/Google Wallet con puntos, promos y notificaciones",
    "description": """
Integración completa de Kivly con Odoo POS
==========================================

Características principales:
----------------------------
* Sincronización automática de órdenes POS a Kivly
* Sincronización bidireccional de clientes (Odoo ↔ Kivly)
* Acumulación automática de puntos de lealtad
* Tarjetas digitales en Apple Wallet y Google Wallet
* Notificaciones push a clientes
* Webhooks seguros con validación HMAC SHA256
* Gestión completa desde Odoo

Resultados comprobados:
-----------------------
* +31% en ventas
* +23% en ticket medio
* 78% tasa de apertura de notificaciones
* Más de 800 clientes activos

Para más información: https://getkivly.com
    """,

    "author": "Locatefit LLC (Kivly)",
    "website": "https://getkivly.com",

    "category": "Marketing",
    "version": "18.0.1.0.2",

    "depends": [
        "base",
        "contacts",
        "product",
        "point_of_sale",
    ],

    "data": [
        "security/ir.model.access.csv",

        "data/kivly_config_data.xml",
        "data/kivly_product_data.xml",

        "views/kivly_config_views.xml",
        "views/pos_config_views.xml",
        "views/pos_order_views.xml",
        "views/res_partner_views.xml",
        "views/views.xml",
        "views/templates.xml",
    ],

    "demo": [
        "demo/demo.xml",
    ],

    "assets": {
        "point_of_sale.assets_prod": [
            "kivly_loyalty/static/src/app/kivly/**/*",
        ],
    },

    "images": [
        "static/description/thumbnail.png",
    ],

    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
