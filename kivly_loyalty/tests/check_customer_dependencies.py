#!/usr/bin/env python3
"""
Script para verificar si un cliente tiene datos relacionados
que impedirían su eliminación permanente

Uso: python3 check_customer_dependencies.py [CUSTOMER_ID]
"""

import sys
import xmlrpc.client

def check_customer(url, db, username, password, customer_id):
    """Verifica las dependencias de un cliente"""
    
    print(f"\n{'='*60}")
    print(f"🔍 Verificando Cliente ID: {customer_id}")
    print(f"{'='*60}\n")
    
    # Conectar a Odoo
    common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
    uid = common.authenticate(db, username, password, {})
    
    if not uid:
        print("❌ Error de autenticación")
        return False
    
    models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
    
    # Obtener información del cliente
    partner = models.execute_kw(db, uid, password,
        'res.partner', 'read',
        [[customer_id], ['name', 'email', 'phone', 'kivly_id']])
    
    if not partner:
        print(f"❌ Cliente {customer_id} no encontrado")
        return False
    
    partner = partner[0]
    print(f"📋 Cliente: {partner['name']}")
    print(f"📧 Email: {partner.get('email', 'N/A')}")
    print(f"📱 Teléfono: {partner.get('phone', 'N/A')}")
    print(f"🆔 Kivly ID: {partner.get('kivly_id', 'N/A')}")
    print(f"\n{'='*60}\n")
    
    # Verificar facturas
    print("💰 Verificando facturas...")
    invoice_count = models.execute_kw(db, uid, password,
        'account.move', 'search_count',
        [[['partner_id', '=', customer_id]]])
    print(f"   Facturas encontradas: {invoice_count}")
    
    # Verificar órdenes de venta
    print("\n📦 Verificando órdenes de venta...")
    sale_count = models.execute_kw(db, uid, password,
        'sale.order', 'search_count',
        [[['partner_id', '=', customer_id]]])
    print(f"   Órdenes de venta encontradas: {sale_count}")
    
    # Verificar órdenes POS
    print("\n🛒 Verificando órdenes POS...")
    pos_count = models.execute_kw(db, uid, password,
        'pos.order', 'search_count',
        [[['partner_id', '=', customer_id]]])
    print(f"   Órdenes POS encontradas: {pos_count}")
    
    # Verificar pagos
    print("\n💳 Verificando pagos...")
    payment_count = models.execute_kw(db, uid, password,
        'account.payment', 'search_count',
        [[['partner_id', '=', customer_id]]])
    print(f"   Pagos encontrados: {payment_count}")
    
    # Resumen
    print(f"\n{'='*60}")
    print("📊 RESUMEN")
    print(f"{'='*60}\n")
    
    total = invoice_count + sale_count + pos_count + payment_count
    
    if total == 0:
        print("✅ Este cliente NO tiene datos relacionados")
        print("✅ Puede ser eliminado permanentemente")
        return True
    else:
        print(f"⚠️  Este cliente tiene {total} registros relacionados:")
        print(f"   - Facturas: {invoice_count}")
        print(f"   - Órdenes de venta: {sale_count}")
        print(f"   - Órdenes POS: {pos_count}")
        print(f"   - Pagos: {payment_count}")
        print("\n❌ NO puede ser eliminado permanentemente")
        print("\n💡 Recomendaciones:")
        print("   1. Usar 'Anonimizar' para cumplir GDPR")
        print("   2. Usar 'Archivar' para mantener historial")
        print("   3. Si intentas 'Eliminar permanentemente', se archivará automáticamente")
        return False

def main():
    # Configuración
    if len(sys.argv) < 2:
        print("Uso: python3 check_customer_dependencies.py [CUSTOMER_ID]")
        print("\nEjemplo:")
        print("  python3 check_customer_dependencies.py 13")
        sys.exit(1)
    
    customer_id = int(sys.argv[1])
    
    # Configuración de Odoo
    url = input("URL de Odoo (default: http://localhost:8069): ").strip() or "http://localhost:8069"
    db = input("Base de datos (default: mydb): ").strip() or "mydb"
    username = input("Usuario (default: admin): ").strip() or "admin"
    password = input("Contraseña: ").strip()
    
    if not password:
        print("❌ Contraseña requerida")
        sys.exit(1)
    
    try:
        can_delete = check_customer(url, db, username, password, customer_id)
        
        print(f"\n{'='*60}\n")
        
        if can_delete:
            print("✅ Puedes proceder con la eliminación permanente")
        else:
            print("⚠️  Considera usar 'Anonimizar' en lugar de 'Eliminar'")
        
        sys.exit(0 if can_delete else 1)
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
