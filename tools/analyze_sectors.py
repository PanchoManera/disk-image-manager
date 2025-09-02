#!/usr/bin/env python3

import sys
import os
import struct
from td0_to_hp150_pre_fixed import TD0Reader

def analyze_sectors(td0_file):
    """Analiza sectores específicos de un archivo TD0"""
    print(f"Analizando {td0_file}...")
    
    reader = TD0Reader(td0_file)
    
    # Parsear header
    header = reader.parse_header()
    print(f"Header: {header}")
    
    # Si está comprimido, descomprimir
    if header['compressed']:
        print("Descomprimiendo...")
        compressed_data = reader.data[reader.pos:]
        decompressed = reader.decompressor.decompress(compressed_data)
        reader.data = reader.data[:reader.pos] + decompressed
        
    # Parsear comentarios
    if header['has_comment']:
        comment = reader.parse_comment()
        if comment:
            print(f"Comentario: {comment['data']}")
    
    # Parsear primer track (track 0)
    track = reader.parse_track()
    if track is None:
        print("No se pudo leer el track 0")
        return
        
    print(f"Track 0 - Cilindro: {track['cylinder']}, Cabeza: {track['head']}, Sectores: {track['num_sectors']}")
    
    # Parsear sectores del track 0
    sectors = {}
    for i in range(track['num_sectors']):
        sector = reader.parse_sector()
        if sector is None:
            break
            
        sector_data = reader.parse_sector_data(sector)
        sectors[sector['sector_num']] = {
            'header': sector,
            'data': sector_data
        }
        
        print(f"  Sector {sector['sector_num']}: {sector['size']} bytes, flags=0x{sector['flags']:02x}")
    
    # Analizar sector de arranque (sector 0 o el primer sector disponible)
    boot_sector_num = None
    for num in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17]:
        if num in sectors:
            boot_sector_num = num
            break
    
    if boot_sector_num is not None:
        print(f"\nAnalizando sector de arranque (sector {boot_sector_num}):")
        boot_data = sectors[boot_sector_num]['data']
        
        if boot_data and len(boot_data) >= 16:
            print(f"Primeros 16 bytes: {boot_data[:16].hex()}")
            print(f"Primeros 16 bytes ASCII: {repr(boot_data[:16])}")
            
            # Buscar signature de arranque
            if len(boot_data) >= 256:
                print(f"Últimos 2 bytes: {boot_data[254:256].hex()}")
                if boot_data[254:256] == b'\x55\xaa':
                    print("✓ Signature de arranque válida (0x55AA)")
                else:
                    print("✗ Signature de arranque inválida")
        else:
            print("✗ Datos del sector de arranque vacíos o insuficientes")
    else:
        print("✗ No se encontró sector de arranque")
    
    # Mostrar mapa de sectores disponibles
    print(f"\nMapa de sectores en track 0:")
    for i in range(18):  # 0-17
        if i in sectors:
            print(f"  Sector {i:2d}: ✓ ({len(sectors[i]['data'])} bytes)")
        else:
            print(f"  Sector {i:2d}: ✗ (ausente)")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python analyze_sectors.py <archivo.td0>")
        sys.exit(1)
        
    analyze_sectors(sys.argv[1])
