# Changelog

All notable changes to this project will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
adhering to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.2] - 2026-02-13

### Fixed

- **POS discount product not found in Odoo 19**: Custom fields on `pos.config`
  are filtered by the frontend Proxy system unless explicitly declared in the
  schema. Resolved by fetching `kivly_discount_product_id` via a direct ORM call
  from the frontend, bypassing proxy limitations entirely.
- **Discount product not loaded in POS**: Overrode `_get_special_products()` in
  `pos.config` to ensure the Kivly discount product is always available in the
  POS regardless of category filters.
- **`order.add_product` TypeError**: Replaced deprecated method with
  `pos.addLineToCurrentOrder()` (Odoo 19 API).
- **XML view warning**: Changed `@class` xpath selector to `hasclass()` function
  as recommended by Odoo's view validation.
- **Code quality**: Replaced bare `except:` with specific exception types,
  converted f-string logger calls to `%s` formatting, removed debug
  `console.log` statements from frontend code.

### Removed

- Removed unused `models.py`, `models.js`, and `pos_config.js` placeholder files.
- Removed all debugging `console.log` calls from JS modules (KivlyModal, KivlyButton).

## [1.0.1] - 2026-02-13

### Added

- **Bidirectional customer sync** between Odoo and Kivly.
  - Odoo to Kivly: Auto-sync on customer create/update.
  - Kivly to Odoo: Webhook endpoint for customer events.
- **New fields on `res.partner`**: `kivly_id`, `kivly_points`,
  `kivly_sync_enabled`, `last_kivly_sync`.
- **Webhook security** with HMAC SHA256 signature validation.
- **Sync configuration** in `kivly.config`: `customer_sync_enabled`,
  `customer_sync_only_with_phone`, `webhook_secret`.
- **Customer views**: Kivly Loyalty tab, sync buttons, filters.
- **Webhook endpoints**: `/kivly/webhook/customer`, `/kivly/webhook/test`.
- **Migration script**: `migrations/1.0.1/post-migrate.py`.

### Changed

- Customer identification now prioritises `kivly_id` over Odoo partner ID.

## [1.0.0] - 2026-02-01

### Added

- Initial Kivly integration for Odoo POS.
- Automatic POS order sync to Kivly API.
- `kivly.config` model for centralised configuration.
- `kivly.api` model for API client.
- Extension of `pos.order` with sync fields and automatic push on payment.
- Configuration and order views with sync status indicators.
- Post-install hook to auto-configure discount product on all POS configs.
- Connection test button in settings.
