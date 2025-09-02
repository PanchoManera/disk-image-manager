#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.td0_converter_lib import TD0Reader

def analyze_td0_geometry(td0_file):
    """Analiza la geometría completa de un archivo TD0"""
    print(f"Analizando geometría de: {td0_file}")
    print("=" * 50)
    
    reader = TD0Reader(td0_file)
    
    # Parsear header
    header = reader.parse_header()
    print("HEADER TD0:")
    print(f"  Signature: {header['signature']}")
    print(f"  Compressed: {header['compressed']}")
    print(f"  Version: {header['version']}")
    print(f"  Data Rate: {header['data_rate']}")
    print(f"  Drive Type: {header['drive_type']}")
    print(f"  Stepping: {header['stepping']}")
    print(f"  DOS Allocation: {header['dos_allocation']}")
    print(f"  Sides: {header['sides']}")
    print(f"  Has Comment: {header['has_comment']}")
    
    # Si está comprimido, descomprimir
    if header['compressed']:
        print("\nDescomprimiendo archivo...")
        compressed_data = reader.data[reader.pos:]
        decompressed = reader.decompressor.decompress(compressed_data)
        reader.data = reader.data[:reader.pos] + decompressed
        
    # Parsear comentarios
    if header['has_comment']:
        comment = reader.parse_comment()
        if comment:
            print(f"\nComentario: {comment['data']}")
    
    # Analizar todos los tracks
    print("\nANALIZANDO TRACKS Y SECTORES:")
    print("-" * 40)
    
    tracks = []
    track_count = 0
    min_cylinder = float('inf')
    max_cylinder = -1
    min_head = float('inf')
    max_head = -1
    sector_sizes = {}
    sectors_per_track = {}
    
    while True:
        track = reader.parse_track()
        if track is None:
            break
            
        track_count += 1
        cylinder = track['cylinder']
        head = track['head']
        num_sectors = track['num_sectors']
        
        # Estadísticas generales
        min_cylinder = min(min_cylinder, cylinder)
        max_cylinder = max(max_cylinder, cylinder)
        min_head = min(min_head, head)
        max_head = max(max_head, head)
        
        print(f"Track {track_count}: Cyl={cylinder}, Head={head}, Sectores={num_sectors}")
        
        # Analizar sectores de este track
        track_sectors = []
        for i in range(num_sectors):
            sector = reader.parse_sector()
            if sector is None:
                break
                
            sector_data = reader.parse_sector_data(sector)
            actual_size = len(sector_data) if sector_data else 0
            
            track_sectors.append({
                'sector_num': sector['sector_num'],
                'size_code': sector['size_code'],
                'theoretical_size': sector['size'],
                'actual_size': actual_size
            })
            
            # Estadísticas de tamaños
            if sector['size_code'] not in sector_sizes:
                sector_sizes[sector['size_code']] = 0
            sector_sizes[sector['size_code']] += 1
            
            print(f"  Sector {sector['sector_num']}: size_code={sector['size_code']}, "
                  f"theoretical={sector['size']}, actual={actual_size}")
        
        # Estadísticas de sectores por track
        if num_sectors not in sectors_per_track:
            sectors_per_track[num_sectors] = 0
        sectors_per_track[num_sectors] += 1
        
        tracks.append({
            'cylinder': cylinder,
            'head': head,
            'num_sectors': num_sectors,
            'sectors': track_sectors
        })
    
    # Resumen de geometría
    print("\n" + "=" * 50)
    print("RESUMEN DE GEOMETRÍA:")
    print(f"  Total tracks analizados: {track_count}")
    print(f"  Cilindros: {min_cylinder} a {max_cylinder} (total: {max_cylinder - min_cylinder + 1})")
    print(f"  Cabezas: {min_head} a {max_head} (total: {max_head - min_head + 1})")
    
    print(f"\nDistribución de sectores por track:")
    for sectors, count in sorted(sectors_per_track.items()):
        print(f"  {sectors} sectores: {count} tracks")
    
    print(f"\nDistribución de tamaños de sector:")
    size_table = [128, 256, 512, 1024, 2048, 4096, 8192, 16384]
    for size_code, count in sorted(sector_sizes.items()):
        theoretical_size = size_table[size_code] if size_code < len(size_table) else "unknown"
        print(f"  Size code {size_code} ({theoretical_size} bytes): {count} sectores")
    
    # Calcular tamaño total esperado
    total_sectors = sum(len(track['sectors']) for track in tracks)
    expected_size_256 = total_sectors * 256  # Asumiendo 256 bytes por sector
    
    print(f"\nCÁLCULOS DE TAMAÑO:")
    print(f"  Total sectores encontrados: {total_sectors}")
    print(f"  Tamaño esperado (256 bytes/sector): {expected_size_256} bytes ({expected_size_256//1024} KB)")
    
    # Geometría estándar esperada
    cylinders = max_cylinder - min_cylinder + 1
    heads = max_head - min_head + 1
    print(f"\nGEOMETRÍA DETECTADA:")
    print(f"  Cilindros: {cylinders}")
    print(f"  Cabezas: {heads}")
    print(f"  Sectores por track: variable (ver distribución arriba)")
    print(f"  Bytes por sector: mayormente 256 (ver distribución arriba)")
    
    return {
        'header': header,
        'tracks': tracks,
        'geometry': {
            'cylinders': cylinders,
            'heads': heads,
            'total_sectors': total_sectors,
            'expected_size': expected_size_256
        }
    }

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python analyze_td0_geometry.py <archivo.td0>")
        sys.exit(1)
    
    td0_file = sys.argv[1]
    if not os.path.exists(td0_file):
        print(f"Error: No se encuentra el archivo {td0_file}")
        sys.exit(1)
    
    try:
        analyze_td0_geometry(td0_file)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
