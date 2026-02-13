#!/usr/bin/env python3
"""
Script de prueba para webhooks de Kivly

Uso:
    python test_webhook.py <odoo_url> <webhook_secret>
    
Ejemplo:
    python test_webhook.py https://tu-odoo.com abc123...
"""

import sys
import json
import hmac
import hashlib
import requests


def calculate_signature(payload, secret):
    """Calcula la firma HMAC SHA256 del payload"""
    return hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def test_webhook_endpoint(base_url, webhook_secret):
    """Prueba el endpoint de webhook"""
    
    # Primero probar el endpoint de test (sin signature)
    print("=" * 70)
    print("Probando endpoint de prueba...")
    print("=" * 70)
    
    test_url = f"{base_url.rstrip('/')}/kivly/webhook/test"
    print(f"URL: {test_url}")
    print()
    
    try:
        response = requests.post(
            test_url,
            json={},
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Endpoint de prueba funciona correctamente")
            print(f"Respuesta: {response.json()}")
        else:
            print(f"❌ Error: HTTP {response.status_code}")
            print(f"Respuesta: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error al conectar: {str(e)}")
        return False
    
    print()
    print("=" * 70)
    print("Probando webhook de cliente (con signature)...")
    print("=" * 70)
    
    # Probar el endpoint de cliente con signature
    customer_url = f"{base_url.rstrip('/')}/kivly/webhook/customer"
    print(f"URL: {customer_url}")
    print()
    
    # Payload de prueba
    payload = {
        "event": "customer.created",
        "customer": {
            "id": "test_kivly_123",
            "name": "Test Customer",
            "phone": "+34612345678",
            "email": "test@example.com",
            "points": 0
        }
    }
    
    payload_str = json.dumps(payload)
    
    # Calcular signature
    signature = calculate_signature(payload_str, webhook_secret)
    
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print()
    print(f"Signature: {signature}")
    print()
    
    try:
        response = requests.post(
            customer_url,
            json=payload,
            headers={
                'Content-Type': 'application/json',
                'X-Kivly-Signature': signature
            },
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Webhook de cliente funciona correctamente")
            print(f"Respuesta: {response.json()}")
            return True
        else:
            print(f"❌ Error: HTTP {response.status_code}")
            print(f"Respuesta: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error al conectar: {str(e)}")
        return False


def main():
    """Función principal"""
    if len(sys.argv) < 2:
        print("Uso: python test_webhook.py <odoo_url> [webhook_secret]")
        print()
        print("Ejemplos:")
        print("  python test_webhook.py https://tu-odoo.com")
        print("  python test_webhook.py https://tu-odoo.com abc123...")
        sys.exit(1)
    
    base_url = sys.argv[1]
    webhook_secret = sys.argv[2] if len(sys.argv) > 2 else ''
    
    print()
    print("=" * 70)
    print("Test de Webhooks de Kivly")
    print("=" * 70)
    print()
    print(f"URL base: {base_url}")
    print(f"Webhook secret: {'Configurado' if webhook_secret else 'No configurado (modo desarrollo)'}")
    print()
    
    success = test_webhook_endpoint(base_url, webhook_secret)
    
    print()
    print("=" * 70)
    print()
    
    if success:
        print("✅ Todos los tests pasaron exitosamente")
        print()
        print("Siguiente paso:")
        print("  Configura este webhook en el dashboard de Kivly")
        sys.exit(0)
    else:
        print("❌ Algunos tests fallaron")
        print()
        print("Verificar:")
        print("  1. La URL de Odoo es accesible desde internet")
        print("  2. El webhook secret es correcto")
        print("  3. El módulo kivly_loyalty está instalado")
        sys.exit(1)


if __name__ == '__main__':
    main()
