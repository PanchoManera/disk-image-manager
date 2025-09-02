#!/usr/bin/env python3
"""
Script para listar archivos en una imagen FAT16
Específicamente diseñado para leer el contenido de MR_fixed.img
"""

import struct
import sys
import os

def parse_fat16_directory(filename):
    """Lee el directorio raíz de una imagen FAT16"""
    
    with open(filename, 'rb') as f:
        # El BPB real está en 0x100 + 0x0B para esta imagen
        bpb_start = 0x100
        
        # Leer BPB para obtener parámetros del sistema de archivos
        f.seek(bpb_start + 0x0B)  # Offset del BPB
        bytes_per_sector = struct.unpack('<H', f.read(2))[0]
        f.seek(bpb_start + 0x0D)
        sectors_per_cluster = f.read(1)[0]
        f.seek(bpb_start + 0x0E)
        reserved_sectors = struct.unpack('<H', f.read(2))[0]
        f.seek(bpb_start + 0x10)
        num_fats = f.read(1)[0]
        f.seek(bpb_start + 0x11)
        root_entries = struct.unpack('<H', f.read(2))[0]
        f.seek(bpb_start + 0x16)
        sectors_per_fat = struct.unpack('<H', f.read(2))[0]
        
        print(f"Parámetros FAT16:")
        print(f"  Bytes por sector: {bytes_per_sector}")
        print(f"  Sectores reservados: {reserved_sectors}")
        print(f"  Número de FATs: {num_fats}")
        print(f"  Entradas en directorio raíz: {root_entries}")
        print(f"  Sectores por FAT: {sectors_per_fat}")
        
        # Calcular posición del directorio raíz
        calculated_root = (reserved_sectors + (sectors_per_fat * num_fats)) * bytes_per_sector
        # Para esta imagen específica, el directorio está en 0x1100
        root_dir_start = 0x1100
        print(f"  Directorio raíz calculado: 0x{calculated_root:x}")
        print(f"  Directorio raíz real: 0x{root_dir_start:x}")
        
        # Leer entradas del directorio raíz
        f.seek(root_dir_start)
        
        print(f"\n=== Archivos en MR_fixed.img ===")
        
        file_count = 0
        for i in range(root_entries):
            entry = f.read(32)  # Cada entrada son 32 bytes
            
            if len(entry) < 32:
                break
                
            # Verificar si la entrada está vacía o borrada
            if entry[0] == 0x00:  # Fin de directorio
                break
            if entry[0] == 0xE5:  # Archivo borrado
                continue
                
            # Verificar si es una entrada de volumen
            attr = entry[11]
            if attr & 0x08:  # Volume label
                volume_name = entry[:11].decode('latin-1', errors='replace').strip()
                print(f"Etiqueta de volumen: '{volume_name}'")
                continue
                
            # Es un archivo normal
            filename = entry[:8].decode('latin-1', errors='replace').strip()
            extension = entry[8:11].decode('latin-1', errors='replace').strip()
            
            # Construir nombre completo
            if extension:
                full_name = f"{filename}.{extension}"
            else:
                full_name = filename
                
            # Obtener tamaño del archivo
            file_size = struct.unpack('<L', entry[28:32])[0]
            
            # Obtener fecha/hora
            time_raw = struct.unpack('<H', entry[22:24])[0]
            date_raw = struct.unpack('<H', entry[24:26])[0]
            
            # Parsear fecha y hora DOS
            hour = (time_raw >> 11) & 0x1F
            minute = (time_raw >> 5) & 0x3F
            second = (time_raw & 0x1F) * 2
            
            year = ((date_raw >> 9) & 0x7F) + 1980
            month = (date_raw >> 5) & 0x0F
            day = date_raw & 0x1F
            
            # Atributos
            attr_str = ""
            if attr & 0x01: attr_str += "R"
            if attr & 0x02: attr_str += "H"
            if attr & 0x04: attr_str += "S"
            if attr & 0x10: attr_str += "D"
            if attr & 0x20: attr_str += "A"
            
            print(f"{full_name:<12} {file_size:>8} bytes  {day:02d}/{month:02d}/{year} {hour:02d}:{minute:02d}:{second:02d}  {attr_str}")
            file_count += 1
        
        print(f"\nTotal de archivos: {file_count}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python3 list_fat_files.py <imagen.img>")
        sys.exit(1)
    
    filename = sys.argv[1]
    if not os.path.exists(filename):
        print(f"Error: El archivo {filename} no existe")
        sys.exit(1)
    
    parse_fat16_directory(filename)
