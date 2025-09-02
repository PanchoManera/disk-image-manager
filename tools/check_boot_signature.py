#!/usr/bin/env python3

import sys

def check_boot_signature(filename):
    """Muestra específicamente los bytes 254-255 del boot sector"""
    print(f"Verificando firma de boot en {filename}...")
    
    with open(filename, 'rb') as f:
        f.seek(254)  # Ir al byte 254
        signature_bytes = f.read(2)  # Leer 2 bytes
    
    print(f"Bytes 254-255: {signature_bytes.hex()}")
    print(f"Decimal: {signature_bytes[0]}, {signature_bytes[1]}")
    print(f"Esperado: 55aa (85, 170)")
    
    if signature_bytes == b'\x55\xaa':
        print("✅ Firma correcta")
    else:
        print("❌ Firma incorrecta")
    
    # Mostrar contexto alrededor
    with open(filename, 'rb') as f:
        f.seek(250)
        context = f.read(10)
    
    print(f"Contexto (bytes 250-259): {context.hex()}")
    
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python check_boot_signature.py <archivo>")
        sys.exit(1)
    
    check_boot_signature(sys.argv[1])
