#!/usr/bin/env python3
"""
Analizador de imagen de floppy HP150 real
Analiza la estructura de sectores de la imagen que funciona
"""

import struct
import sys

def analyze_hp150_image(filename):
    """Analiza la estructura de la imagen HP150 real"""
    
    with open(filename, 'rb') as f:
        data = f.read()
    
    print(f"=== Análisis de imagen HP150 real ===")
    print(f"Archivo: {filename}")
    print(f"Tamaño total: {len(data)} bytes ({len(data)/1024:.1f} KB)")
    print()
    
    # Parámetros conocidos del HP150
    # Suponiendo estructura estándar HP150: 80 tracks, 16 sectores por track, 256 bytes por sector
    # Pero sabemos que puede tener variaciones
    
    SECTORS_PER_TRACK_STANDARD = 16
    BYTES_PER_SECTOR_STANDARD = 256
    EXPECTED_TRACKS = 80
    
    # Calcular tamaño esperado para disco estándar
    expected_standard_size = EXPECTED_TRACKS * SECTORS_PER_TRACK_STANDARD * BYTES_PER_SECTOR_STANDARD
    print(f"Tamaño esperado para disco estándar HP150: {expected_standard_size} bytes ({expected_standard_size/1024:.1f} KB)")
    print(f"Diferencia: {len(data) - expected_standard_size} bytes")
    print()
    
    # Analizar por tracks asumiendo estructura HP150
    print("=== Análisis por tracks ===")
    
    offset = 0
    for track in range(EXPECTED_TRACKS):
        track_start = offset
        
        # Analizar sectores en este track
        sectors_found = 0
        sector_sizes = []
        
        # Buscar sectores estándar de 256 bytes primero
        for sector in range(SECTORS_PER_TRACK_STANDARD):
            if offset + BYTES_PER_SECTOR_STANDARD <= len(data):
                sector_data = data[offset:offset + BYTES_PER_SECTOR_STANDARD]
                
                # Verificar si el sector tiene datos válidos
                if not all(b == 0 for b in sector_data):
                    sectors_found += 1
                    sector_sizes.append(BYTES_PER_SECTOR_STANDARD)
                
                offset += BYTES_PER_SECTOR_STANDARD
        
        # Verificar si quedan bytes que podrían ser sectores de otros tamaños
        remaining_in_track = len(data) - offset
        
        if track < 10 or track % 10 == 0:  # Mostrar solo algunos tracks para no saturar
            print(f"Track {track:2d}: {sectors_found:2d} sectores, tamaños: {sector_sizes}")
            
            # Mostrar primeros bytes del track para análisis
            track_data = data[track_start:track_start + 32]
            hex_data = ' '.join(f'{b:02x}' for b in track_data)
            print(f"   Primeros 32 bytes: {hex_data}")
    
    print()
    
    # Buscar patrones específicos
    print("=== Búsqueda de patrones ===")
    
    # Buscar firma de boot sector (típicamente en el primer sector)
    boot_sector = data[0:512]
    print(f"Primer sector (boot):")
    print(f"  Primeros 16 bytes: {' '.join(f'{b:02x}' for b in boot_sector[:16])}")
    print(f"  Bytes 510-511: {boot_sector[510]:02x} {boot_sector[511]:02x}")
    
    # Buscar strings ASCII que puedan indicar estructura
    print("\n=== Strings ASCII encontrados ===")
    ascii_strings = []
    current_string = ""
    
    for i, byte in enumerate(data):
        if 32 <= byte <= 126:  # Caracteres ASCII imprimibles
            current_string += chr(byte)
        else:
            if len(current_string) > 8:  # Solo strings de más de 8 caracteres
                ascii_strings.append((i - len(current_string), current_string))
            current_string = ""
    
    # Mostrar las primeras 10 strings más largas
    ascii_strings.sort(key=lambda x: len(x[1]), reverse=True)
    for i, (pos, string) in enumerate(ascii_strings[:10]):
        print(f"  Posición {pos:6d}: '{string[:50]}{'...' if len(string) > 50 else ''}'")
    
    # Análisis de densidad de datos por regiones
    print("\n=== Análisis de densidad de datos ===")
    
    chunk_size = 1024
    for i in range(0, len(data), chunk_size):
        chunk = data[i:i + chunk_size]
        non_zero_bytes = sum(1 for b in chunk if b != 0)
        density = non_zero_bytes / len(chunk) * 100
        
        if i // chunk_size < 20:  # Mostrar solo los primeros 20 chunks
            print(f"Chunk {i//chunk_size:2d} ({i:6d}-{i+chunk_size-1:6d}): {density:5.1f}% datos")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python3 analyze_hp150_real_image.py <imagen.img>")
        sys.exit(1)
    
    analyze_hp150_image(sys.argv[1])
