# Guía de Pruebas de Webhooks

Esta guía te ayudará a probar los webhooks de Kivly en tu instalación de Odoo.

## 🚀 Inicio Rápido

### 1. Prueba Básica con cURL

El test más simple es verificar que el endpoint responda:

```bash
curl -X POST http://localhost:8069/kivly/webhook/test
```

**Respuesta esperada:**
```json
{
  "status": "ok",
  "message": "Webhook test successful"
}
```

### 2. Usar el Script de Prueba (Recomendado)

Hemos creado un script Python que prueba todos los webhooks automáticamente:

```bash
cd /Users/leudy/Documents/odoo/addons/kivly_loyalty/tests
python3 test_webhook.py http://localhost:8069/kivly/webhook/customer kv_webhook_4NB3l0KmgCajSfjSAQPLdx-zTdJ1navKMplcoNasKME
```

**Reemplaza:**
- `http://localhost:8069` con tu URL de Odoo
- `kv_webhook_...` con tu webhook secret real

El script probará:
- ✅ Endpoint de prueba
- ✅ Crear cliente
- ✅ Actualizar cliente

## 🔧 Pruebas Manuales

### Test 1: Crear Cliente

```bash
# 1. Preparar el payload
PAYLOAD='{"event":"customer.created","customer":{"id":"test_123","name":"Juan Pérez","phone":"+593987654321","email":"juan@example.com","points":0}}'

# 2. Calcular la firma HMAC (con tu secret real)
SECRET="kv_webhook_4NB3l0KmgCajSfjSAQPLdx-zTdJ1navKMplcoNasKME"
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | cut -d' ' -f2)

# 3. Enviar el webhook
curl -X POST http://localhost:8069/kivly/webhook/customer \
  -H "Content-Type: application/json" \
  -H "X-Kivly-Signature: $SIGNATURE" \
  -d "$PAYLOAD"
```

**Respuesta esperada:**
```json
{
  "status": "ok",
  "action": "created",
  "odoo_partner_id": 42
}
```

### Test 2: Actualizar Cliente

```bash
PAYLOAD='{"event":"customer.updated","customer":{"id":"test_123","name":"Juan Pérez García","phone":"+593987654321","email":"juan.nuevo@example.com","points":150}}'

SECRET="kv_webhook_4NB3l0KmgCajSfjSAQPLdx-zTdJ1navKMplcoNasKME"
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | cut -d' ' -f2)

curl -X POST http://localhost:8069/kivly/webhook/customer \
  -H "Content-Type: application/json" \
  -H "X-Kivly-Signature: $SIGNATURE" \
  -d "$PAYLOAD"
```

### Test 3: Eliminar Cliente

```bash
PAYLOAD='{"event":"customer.deleted","customer":{"id":"test_123"}}'

SECRET="kv_webhook_4NB3l0KmgCajSfjSAQPLdx-zTdJ1navKMplcoNasKME"
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | cut -d' ' -f2)

curl -X POST http://localhost:8069/kivly/webhook/customer/delete \
  -H "Content-Type: application/json" \
  -H "X-Kivly-Signature: $SIGNATURE" \
  -d "$PAYLOAD"
```

## 🔍 Verificar en Odoo

Después de enviar webhooks, verifica en Odoo:

1. Ve a **Contactos** en Odoo
2. Busca "Juan Pérez" o el nombre que usaste
3. Abre el contacto y ve a la pestaña **"Kivly Loyalty"**
4. Verifica que:
   - ✅ `Kivly ID` esté lleno
   - ✅ `Kivly Points` tenga el valor correcto
   - ✅ `Última sincronización Kivly` sea reciente

## 📋 Revisar Logs

Ver logs en tiempo real:

```bash
# Logs generales de Kivly
tail -f odoo.log | grep -i kivly

# Solo webhooks
tail -f odoo.log | grep "Webhook recibido"

# Solo errores
tail -f odoo.log | grep -E "(ERROR|WARNING)" | grep -i kivly
```

## ❌ Errores Comunes

### Error: "Invalid signature"

**Problema:** La firma HMAC no coincide

**Soluciones:**

1. **Verifica que el secret sea correcto:**
   ```bash
   # En Odoo
   Kivly → Configuración → Webhook Secret
   
   # Debe coincidir exactamente con el que usas en tu script
   ```

2. **Verifica que el payload sea idéntico:**
   - No agregues espacios extras
   - No cambies el orden de los campos
   - Usa el payload RAW exacto para calcular la firma

3. **Calcula la firma correctamente:**
   ```python
   import hmac
   import hashlib
   
   secret = "kv_webhook_..."
   payload = '{"event":"customer.created",...}'
   
   signature = hmac.new(
       secret.encode('utf-8'),
       payload.encode('utf-8'),
       hashlib.sha256
   ).hexdigest()
   
   print(signature)
   ```

4. **Modo desarrollo (sin validación):**
   - Si quieres probar sin validar firma, deja el campo `Webhook Secret` vacío en la configuración de Odoo
   - **⚠️ NO hacer esto en producción**

### Error: "Missing required fields"

**Problema:** Faltan campos obligatorios en el payload

**Campos obligatorios:**
- `customer.id` - ID de Kivly
- `customer.phone` - Teléfono del cliente

**Solución:** Asegúrate de incluir estos campos:
```json
{
  "event": "customer.created",
  "customer": {
    "id": "kivly_123",     ← Obligatorio
    "phone": "+593...",    ← Obligatorio
    "name": "..."
  }
}
```

### Error: 404 Not Found

**Problema:** La URL no existe

**Soluciones:**

1. **Verifica que Odoo esté corriendo:**
   ```bash
   curl http://localhost:8069
   ```

2. **Verifica la URL correcta:**
   - ✅ Correcto: `http://localhost:8069/kivly/webhook/customer`
   - ❌ Incorrecto: `http://localhost:8069/webhook/customer`
   - ❌ Incorrecto: `http://localhost:8069/kivly/webhook`

3. **Verifica que el módulo esté instalado:**
   ```bash
   # En Odoo
   Aplicaciones → Buscar "Kivly" → Debe estar instalado
   ```

### Error: Connection refused

**Problema:** No se puede conectar a Odoo

**Soluciones:**

1. **Verifica que Odoo esté corriendo:**
   ```bash
   ps aux | grep odoo
   ```

2. **Inicia Odoo si no está corriendo:**
   ```bash
   cd /Users/leudy/Documents/odoo
   ./venv/bin/python3 odoo-bin -d mydb
   ```

3. **Verifica el puerto:**
   - Por defecto Odoo usa el puerto 8069
   - Verifica en el archivo de configuración

## 🧪 Pruebas Avanzadas

### Test con múltiples campos

```bash
PAYLOAD='{
  "event": "customer.created",
  "timestamp": "2026-02-13T12:00:00Z",
  "customer": {
    "id": "test_full_123",
    "name": "María González",
    "email": "maria@example.com",
    "phone": "+593987654321",
    "points": 0,
    "address": "Av. Amazonas 456",
    "city": "Quito",
    "country": "Ecuador",
    "postal_code": "170150",
    "personal_id": "1712345678",
    "tags": ["VIP", "Premium"],
    "external_id": null
  }
}'

SECRET="kv_webhook_4NB3l0KmgCajSfjSAQPLdx-zTdJ1navKMplcoNasKME"
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | cut -d' ' -f2)

curl -X POST http://localhost:8069/kivly/webhook/customer \
  -H "Content-Type: application/json" \
  -H "X-Kivly-Signature: $SIGNATURE" \
  -d "$PAYLOAD"
```

Verifica que todos los campos se hayan sincronizado correctamente en Odoo.

### Test de rendimiento

```bash
# Crear 100 clientes de prueba
for i in {1..100}; do
  PAYLOAD="{\"event\":\"customer.created\",\"customer\":{\"id\":\"test_$i\",\"name\":\"Cliente $i\",\"phone\":\"+59398765432$i\",\"points\":0}}"
  SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | cut -d' ' -f2)
  
  curl -X POST http://localhost:8069/kivly/webhook/customer \
    -H "Content-Type: application/json" \
    -H "X-Kivly-Signature: $SIGNATURE" \
    -d "$PAYLOAD" \
    -s -o /dev/null -w "Cliente $i: %{http_code} - %{time_total}s\n"
done
```

## 📊 Métricas de Éxito

Un webhook exitoso debe:

- ✅ Retornar status code 200
- ✅ Retornar `{"status": "ok"}`
- ✅ Crear/actualizar el cliente en Odoo en < 1 segundo
- ✅ Sincronizar todos los campos correctamente
- ✅ Registrar el evento en los logs

## 🆘 Soporte

Si después de seguir esta guía aún tienes problemas:

1. **Revisa los logs de Odoo:**
   ```bash
   tail -100 odoo.log | grep -i error
   ```

2. **Activa modo debug en Odoo:**
   - Agrega `?debug=1` a la URL de Odoo
   - Esto mostrará más detalles de errores

3. **Contacta soporte:**
   - Email: support@getkivly.com
   - Dashboard: https://getkivly.com/dashboard

---

**Última actualización:** 2026-02-13
