#!/usr/bin/env python3
"""
Script de prueba para webhooks de Kivly
Uso: python3 test_webhook.py [URL] [SECRET]
"""

import sys
import json
import hmac
import hashlib
import requests

def calculate_signature(payload_str, secret):
    """Calcula la firma HMAC SHA256 del payload"""
    return hmac.new(
        secret.encode('utf-8'),
        payload_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def test_webhook(url, secret, payload):
    """Envía un webhook de prueba"""
    payload_str = json.dumps(payload)
    signature = calculate_signature(payload_str, secret)
    
    headers = {
        'Content-Type': 'application/json',
        'X-Kivly-Signature': signature
    }
    
    print(f"\n{'='*60}")
    print(f"🔍 Probando Webhook")
    print(f"{'='*60}")
    print(f"URL:       {url}")
    print(f"Secret:    {secret[:10]}...{secret[-10:]}")
    print(f"Signature: {signature[:20]}...{signature[-20:]}")
    print(f"Payload:   {payload_str[:100]}...")
    print(f"{'='*60}\n")
    
    try:
        response = requests.post(url, data=payload_str, headers=headers, timeout=10)
        
        print(f"✅ Status Code: {response.status_code}")
        print(f"📦 Response:")
        print(json.dumps(response.json(), indent=2))
        
        return response.status_code == 200
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error: {str(e)}")
        return False

def main():
    # Configuración por defecto
    if len(sys.argv) < 2:
        print("Uso: python3 test_webhook.py [URL] [SECRET]")
        print("\nEjemplo:")
        print("  python3 test_webhook.py http://localhost:8069/kivly/webhook/customer kv_webhook_...")
        print("\nO sin argumentos para modo test:")
        url = input("URL del webhook (ej: http://localhost:8069/kivly/webhook/customer): ").strip()
        secret = input("Webhook Secret: ").strip()
    else:
        url = sys.argv[1]
        secret = sys.argv[2] if len(sys.argv) > 2 else ""
    
    if not url:
        print("❌ URL es obligatoria")
        sys.exit(1)
    
    print(f"\n🚀 Iniciando pruebas de webhooks...")
    
    # Test 1: Endpoint de prueba
    print(f"\n{'#'*60}")
    print("Test 1: Endpoint de prueba")
    print(f"{'#'*60}")
    
    test_url = url.replace('/customer', '/test')
    payload_test = {"test": True}
    
    success1 = test_webhook(test_url, secret, payload_test)
    
    # Test 2: Crear cliente
    print(f"\n{'#'*60}")
    print("Test 2: Crear cliente")
    print(f"{'#'*60}")
    
    test_customer_id = "test_" + hashlib.md5(str(hash("test")).encode()).hexdigest()[:8]
    
    # Estructura real de Kivly
    payload_create = {
        "webhook_id": hashlib.md5(str(hash("webhook1")).encode()).hexdigest(),
        "event": "customer.created",
        "payload": {
            "id": hashlib.md5(str(hash("payload1")).encode()).hexdigest(),
            "event": "customer.created",
            "timestamp": "2026-02-13T12:00:00Z",
            "data": {
                "id": test_customer_id,
                "name": "Cliente de Prueba Webhook",
                "email": "test.webhook@example.com",
                "phone": "+593987654321",
                "loyalty_points": 0,
                "address": "Calle de Prueba 123",
                "city": "Quito",
                "country": "Ecuador",
                "postal_code": "170150",
                "personal_id": "",
                "date_of_birth": None,
                "gender": "other",
                "external_id": None
            }
        }
    }
    
    success2 = test_webhook(url, secret, payload_create)
    
    # Test 3: Actualizar cliente
    print(f"\n{'#'*60}")
    print("Test 3: Actualizar cliente")
    print(f"{'#'*60}")
    
    payload_update = {
        "webhook_id": hashlib.md5(str(hash("webhook2")).encode()).hexdigest(),
        "event": "customer.updated",
        "payload": {
            "id": hashlib.md5(str(hash("payload2")).encode()).hexdigest(),
            "event": "customer.updated",
            "timestamp": "2026-02-13T12:05:00Z",
            "data": {
                "id": test_customer_id,
                "name": "Cliente Actualizado Webhook",
                "email": "updated.webhook@example.com",
                "phone": "+593987654321",
                "loyalty_points": 150,
                "address": "Nueva Calle 456",
                "city": "Guayaquil",
                "country": "Ecuador",
                "postal_code": "170150",
                "personal_id": "1712345678",
                "date_of_birth": "1990-01-15",
                "gender": "male"
            }
        }
    }
    
    success3 = test_webhook(url, secret, payload_update)
    
    # Resumen
    print(f"\n{'='*60}")
    print("📊 RESUMEN DE PRUEBAS")
    print(f"{'='*60}")
    print(f"Test 1 (Endpoint de prueba): {'✅ OK' if success1 else '❌ FAIL'}")
    print(f"Test 2 (Crear cliente):      {'✅ OK' if success2 else '❌ FAIL'}")
    print(f"Test 3 (Actualizar cliente): {'✅ OK' if success3 else '❌ FAIL'}")
    print(f"{'='*60}\n")
    
    if success1 and success2 and success3:
        print("🎉 ¡Todos los tests pasaron exitosamente!")
        sys.exit(0)
    else:
        print("⚠️  Algunos tests fallaron. Revisa los logs de Odoo para más detalles.")
        sys.exit(1)

if __name__ == "__main__":
    main()
