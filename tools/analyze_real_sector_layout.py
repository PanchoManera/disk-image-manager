#!/usr/bin/env python3
"""
Análisis detallado de la estructura de sectores de la imagen real
"""

import struct
import sys

def analyze_sector_layout(filename):
    """Analiza el layout exacto de sectores"""
    
    with open(filename, 'rb') as f:
        data = f.read()
    
    print(f"=== Análisis detallado de sectores - {filename} ===")
    print(f"Tamaño total: {len(data)} bytes")
    print()
    
    # Analizar por tracks con más detalle
    SECTOR_SIZE = 256
    
    # Calcular cuántos sectores de 256 bytes caben
    total_sectors_256 = len(data) // SECTOR_SIZE
    remaining_bytes = len(data) % SECTOR_SIZE
    
    print(f"Sectores de 256 bytes: {total_sectors_256}")
    print(f"Bytes restantes: {remaining_bytes}")
    print()
    
    # Análisis track por track
    offset = 0
    track_data = []
    
    for track in range(85):  # Analizar más tracks por si acaso
        if offset >= len(data):
            break
            
        sectors_in_track = 0
        track_start = offset
        
        # Contar sectores con datos no vacíos
        while offset + SECTOR_SIZE <= len(data):
            sector_data = data[offset:offset + SECTOR_SIZE]
            
            # Verificar si es un sector válido (no todo ceros)
            if not all(b == 0 for b in sector_data):
                sectors_in_track += 1
                offset += SECTOR_SIZE
                
                # Límite de sectores por track
                if sectors_in_track >= 20:  # Máximo razonable
                    break
            else:
                # Si encontramos un sector vacío, verificar si es final de track
                # o si hay más sectores después
                next_sector_data = data[offset + SECTOR_SIZE:offset + 2*SECTOR_SIZE] if offset + 2*SECTOR_SIZE <= len(data) else b''
                
                if len(next_sector_data) > 0 and not all(b == 0 for b in next_sector_data):
                    # Hay datos después, contar este sector vacío también
                    sectors_in_track += 1
                    offset += SECTOR_SIZE
                else:
                    # No hay más datos, terminar este track
                    break
        
        if sectors_in_track > 0:
            track_data.append((track, sectors_in_track))
            print(f"Track {track:2d}: {sectors_in_track:2d} sectores")
            
            # Mostrar primeros bytes para identificar contenido
            first_bytes = data[track_start:track_start + 16]
            hex_data = ' '.join(f'{b:02x}' for b in first_bytes)
            print(f"    Primeros bytes: {hex_data}")
    
    print(f"\nTotal tracks analizados: {len(track_data)}")
    total_sectors = sum(sectors for _, sectors in track_data)
    print(f"Total sectores: {total_sectors}")
    print(f"Tamaño calculado: {total_sectors * SECTOR_SIZE} bytes")
    
    # Análisis del boot sector
    print(f"\n=== Análisis del boot sector ===")
    boot_sector = data[0:256]
    
    # Mostrar estructura del boot sector
    print(f"Jump instruction: {boot_sector[0]:02x} {boot_sector[1]:02x} {boot_sector[2]:02x}")
    oem_name = boot_sector[3:11].decode('ascii', errors='ignore')
    print(f"OEM Name: '{oem_name}'")
    
    # Parámetros del BPB (BIOS Parameter Block)
    if len(boot_sector) >= 30:
        bytes_per_sector = struct.unpack('<H', boot_sector[11:13])[0]
        sectors_per_cluster = boot_sector[13]
        reserved_sectors = struct.unpack('<H', boot_sector[14:16])[0]
        num_fats = boot_sector[16]
        root_entries = struct.unpack('<H', boot_sector[17:19])[0]
        total_sectors = struct.unpack('<H', boot_sector[19:21])[0]
        media_descriptor = boot_sector[21]
        sectors_per_fat = struct.unpack('<H', boot_sector[22:24])[0]
        sectors_per_track = struct.unpack('<H', boot_sector[24:26])[0]
        heads = struct.unpack('<H', boot_sector[26:28])[0]
        
        print(f"Bytes per sector: {bytes_per_sector}")
        print(f"Sectors per cluster: {sectors_per_cluster}")
        print(f"Reserved sectors: {reserved_sectors}")
        print(f"Number of FATs: {num_fats}")
        print(f"Root entries: {root_entries}")
        print(f"Total sectors: {total_sectors}")
        print(f"Media descriptor: 0x{media_descriptor:02x}")
        print(f"Sectors per FAT: {sectors_per_fat}")
        print(f"Sectors per track: {sectors_per_track}")
        print(f"Heads: {heads}")
    
    return track_data

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python3 analyze_real_sector_layout.py <imagen.img>")
        sys.exit(1)
    
    track_data = analyze_sector_layout(sys.argv[1])
