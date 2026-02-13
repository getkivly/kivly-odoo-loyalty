# 🧪 Tests de Webhooks Kivly

Scripts y guías para probar los webhooks de sincronización Kivly ↔ Odoo.

## 📁 Archivos

- `test_webhook.py` - Script automatizado para probar webhooks
- `TESTING.md` - Guía completa de pruebas manuales

## 🚀 Uso Rápido

### Opción 1: Script Automatizado (Recomendado)

```bash
cd /Users/leudy/Documents/odoo/addons/kivly_loyalty/tests
python3 test_webhook.py http://localhost:8069/kivly/webhook/customer TU_WEBHOOK_SECRET
```

### Opción 2: Test Manual con cURL

```bash
# Test básico
curl -X POST http://localhost:8069/kivly/webhook/test

# Con firma HMAC
PAYLOAD='{"event":"customer.created","customer":{"id":"test_123","name":"Test","phone":"+593987654321","points":0}}'
SECRET="tu_webhook_secret_aqui"
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | cut -d' ' -f2)

curl -X POST http://localhost:8069/kivly/webhook/customer \
  -H "Content-Type: application/json" \
  -H "X-Kivly-Signature: $SIGNATURE" \
  -d "$PAYLOAD"
```

## 📖 Documentación Completa

Ver `TESTING.md` para guía detallada con:
- Ejemplos de todos los tipos de webhooks
- Troubleshooting de errores comunes
- Pruebas de rendimiento
- Verificación en Odoo

## ✅ Checklist de Tests

- [ ] Endpoint de prueba responde
- [ ] Crear cliente funciona
- [ ] Actualizar cliente funciona
- [ ] Eliminar/archivar cliente funciona
- [ ] Validación de firma HMAC funciona
- [ ] Todos los campos se sincronizan correctamente
- [ ] Tags/categorías se crean automáticamente
- [ ] País se encuentra por nombre
- [ ] Cliente archivado en lugar de eliminado

## 🔍 Debug Rápido

```bash
# Ver logs en tiempo real
tail -f /var/log/odoo/odoo.log | grep -i kivly

# Ver solo webhooks
tail -f /var/log/odoo/odoo.log | grep "Webhook recibido"
```

## 📊 Respuestas Esperadas

**Éxito - Crear:**
```json
{"status": "ok", "action": "created", "odoo_partner_id": 42}
```

**Éxito - Actualizar:**
```json
{"status": "ok", "action": "updated", "odoo_partner_id": 42}
```

**Error - Firma inválida:**
```json
{"status": "error", "message": "Invalid signature"}
```

**Error - Campos faltantes:**
```json
{"status": "error", "message": "Missing required fields: id or phone"}
```

---

**Última actualización:** 2026-02-13
