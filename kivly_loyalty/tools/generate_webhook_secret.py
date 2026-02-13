#!/usr/bin/env python3
"""
Utilidad para generar un webhook secret aleatorio y seguro

Uso:
    python generate_webhook_secret.py
"""

import secrets


def generate_webhook_secret(length=32):
    """
    Genera un webhook secret aleatorio usando secrets (criptográficamente seguro)
    
    :param length: Longitud del secret en bytes (default: 32)
    :return: String hexadecimal del secret
    """
    return secrets.token_hex(length)


def main():
    """Función principal"""
    print("=" * 70)
    print("Generador de Webhook Secret para Kivly")
    print("=" * 70)
    print()
    
    secret = generate_webhook_secret(32)
    
    print("Tu webhook secret seguro es:")
    print()
    print(f"  {secret}")
    print()
    print("=" * 70)
    print("Instrucciones:")
    print("=" * 70)
    print()
    print("1. Copia el secret de arriba")
    print("2. Ve a Odoo → Kivly → Configuración")
    print("3. Pega el secret en el campo 'Webhook Secret'")
    print("4. Guarda la configuración")
    print("5. Ve al dashboard de Kivly")
    print("6. Configura el mismo secret en Kivly → Webhooks")
    print()
    print("⚠️  IMPORTANTE: Guarda este secret en un lugar seguro.")
    print("   No lo compartas públicamente ni lo subas a repositorios.")
    print()


if __name__ == '__main__':
    main()
