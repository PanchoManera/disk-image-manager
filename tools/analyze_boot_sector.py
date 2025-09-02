#!/usr/bin/env python3

import sys
import struct

def analyze_hp150_boot_sector(filename):
    """Analiza el boot sector de HP-150 en detalle"""
    print(f"Analizando boot sector de {filename}...")
    
    with open(filename, 'rb') as f:
        boot_sector = f.read(256)
    
    if len(boot_sector) < 256:
        print(f"❌ Archivo muy pequeño: {len(boot_sector)} bytes")
        return
    
    # Parsear el boot sector HP-150
    # Offset 0-2: Jump instruction
    jump_code = boot_sector[0:3]
    print(f"Jump code: {jump_code.hex()} ({repr(jump_code)})")
    
    # Offset 3-10: OEM ID
    oem_id = boot_sector[3:11]
    print(f"OEM ID: {repr(oem_id.decode('ascii', errors='ignore'))}")
    
    # Offset 11-12: Bytes per sector
    bytes_per_sector = struct.unpack('<H', boot_sector[11:13])[0]
    print(f"Bytes per sector: {bytes_per_sector}")
    
    # Offset 13: Sectors per cluster
    sectors_per_cluster = boot_sector[13]
    print(f"Sectors per cluster: {sectors_per_cluster}")
    
    # Offset 14-15: Reserved sectors
    reserved_sectors = struct.unpack('<H', boot_sector[14:16])[0]
    print(f"Reserved sectors: {reserved_sectors}")
    
    # Offset 16: Number of FATs
    num_fats = boot_sector[16]
    print(f"Number of FATs: {num_fats}")
    
    # Offset 17-18: Root directory entries
    root_entries = struct.unpack('<H', boot_sector[17:19])[0]
    print(f"Root directory entries: {root_entries}")
    
    # Offset 19-20: Total sectors (if < 65536)
    total_sectors_small = struct.unpack('<H', boot_sector[19:21])[0]
    print(f"Total sectors (small): {total_sectors_small}")
    
    # Offset 21: Media descriptor
    media_descriptor = boot_sector[21]
    print(f"Media descriptor: 0x{media_descriptor:02x}")
    
    # Offset 22-23: Sectors per FAT
    sectors_per_fat = struct.unpack('<H', boot_sector[22:24])[0]
    print(f"Sectors per FAT: {sectors_per_fat}")
    
    # Offset 24-25: Sectors per track
    sectors_per_track = struct.unpack('<H', boot_sector[24:26])[0]
    print(f"Sectors per track: {sectors_per_track}")
    
    # Offset 26-27: Number of heads
    num_heads = struct.unpack('<H', boot_sector[26:28])[0]
    print(f"Number of heads: {num_heads}")
    
    # Boot signature
    signature = boot_sector[254:256]
    print(f"Boot signature: {signature.hex()}")
    if signature == b'\x55\xaa':
        print("✅ Valid boot signature")
    else:
        print("❌ Invalid boot signature")
    
    # Verificar valores específicos de HP-150
    print("\n=== Verificación HP-150 ===")
    checks = [
        ("OEM ID", oem_id == b'HP150   ', "Should be 'HP150   '"),
        ("Bytes per sector", bytes_per_sector == 256, "Should be 256"),
        ("Sectors per track", sectors_per_track == 16, "Should be 16"),
        ("Number of heads", num_heads == 2, "Should be 2"),
        ("Media descriptor", media_descriptor == 0xfa, "Should be 0xfa"),
        ("Boot signature", signature == b'\x55\xaa', "Should be 0x55AA"),
    ]
    
    for check_name, is_ok, description in checks:
        status = "✅" if is_ok else "❌"
        print(f"{status} {check_name}: {description}")
    
    # Mostrar algunos bytes del código de arranque
    print(f"\nCódigo de arranque (bytes 30-50): {boot_sector[30:50].hex()}")
    
    return boot_sector

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python analyze_boot_sector.py <archivo.img>")
        sys.exit(1)
    
    analyze_hp150_boot_sector(sys.argv[1])
