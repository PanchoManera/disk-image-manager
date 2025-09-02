#!/usr/bin/env python3

import sys
import os

def calculate_geometry(filename):
    """Calcula la geometría completa de un disco HP-150"""
    print(f"Calculando geometría de {filename}...")
    
    # Obtener tamaño del archivo
    file_size = os.path.getsize(filename)
    print(f"Tamaño del archivo: {file_size} bytes ({file_size // 1024} KB)")
    
    # Parámetros estándar HP-150
    bytes_per_sector = 256
    sectors_per_track = 16
    heads = 2
    
    # Calcular sectores totales
    total_sectors = file_size // bytes_per_sector
    print(f"Sectores totales: {total_sectors}")
    
    # Calcular tracks totales (considerando ambas cabezas)
    total_tracks = total_sectors // sectors_per_track
    print(f"Tracks totales: {total_tracks}")
    
    # Calcular cilindros
    cylinders = total_tracks // heads
    remainder_tracks = total_tracks % heads
    
    print(f"\n=== Geometría ===")
    print(f"Cilindros: {cylinders}")
    print(f"Cabezas: {heads}")
    print(f"Sectores por track: {sectors_per_track}")
    print(f"Bytes por sector: {bytes_per_sector}")
    
    if remainder_tracks > 0:
        print(f"⚠️  Tracks restantes: {remainder_tracks} (geometría no perfecta)")
    
    # Verificar si es geometría estándar
    print(f"\n=== Verificaciones ===")
    
    # Geometrías comunes HP-150
    geometries = [
        {"cylinders": 35, "heads": 2, "sectors": 16, "name": "Floppy 5.25\" SS"},
        {"cylinders": 70, "heads": 1, "sectors": 16, "name": "Floppy 5.25\" DS convertido a SS"},
        {"cylinders": 70, "heads": 2, "sectors": 16, "name": "Floppy 5.25\" DS"},
        {"cylinders": 80, "heads": 1, "sectors": 16, "name": "Floppy 3.5\" DD convertido a SS"},
        {"cylinders": 80, "heads": 2, "sectors": 16, "name": "Floppy 3.5\" DD"},
    ]
    
    for geom in geometries:
        expected_size = geom["cylinders"] * geom["heads"] * geom["sectors"] * bytes_per_sector
        if expected_size == file_size:
            print(f"✅ Coincide con: {geom['name']}")
            print(f"   ({geom['cylinders']} cilindros × {geom['heads']} cabezas × {geom['sectors']} sectores × {bytes_per_sector} bytes)")
            break
    else:
        print("❓ No coincide con geometrías estándar conocidas")
    
    # Mostrar capacidad
    capacity_kb = file_size / 1024
    print(f"\nCapacidad: {capacity_kb:.1f} KB")
    
    return {
        "file_size": file_size,
        "cylinders": cylinders,
        "heads": heads,
        "sectors_per_track": sectors_per_track,
        "bytes_per_sector": bytes_per_sector,
        "total_sectors": total_sectors,
        "total_tracks": total_tracks
    }

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python calculate_geometry.py <archivo.img>")
        sys.exit(1)
    
    calculate_geometry(sys.argv[1])
