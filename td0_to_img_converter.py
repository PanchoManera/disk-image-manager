#!/usr/bin/env python3
"""
TD0 to IMG Converter - Fixed Version V3.1
Versión corregida que maneja mejor los errores de secuencia de sectores
y no se detiene prematuramente durante la conversión.
"""

import sys
import os
import argparse
import time
from typing import Dict, List, Optional

# Import the unified converter library
from modules.td0_converter_lib import (
    FixedTD0Converter, ConversionOptions, ConversionCallbacks, ConversionResult,
    DebugLevel, convert_td0_to_hp150_fixed
)

class FixedCLICallbacks(ConversionCallbacks):
    """CLI callbacks mejorados para manejo de errores"""
    
    def __init__(self, verbose: bool = False):
        super().__init__()
        self.verbose = verbose
        self.error_count = 0
        self.setup_callbacks()
    
    def setup_callbacks(self):
        """Setup all callback functions"""
        self.on_progress = self._on_progress
        self.on_debug = self._on_debug
        self.on_warning = self._on_warning
        self.on_error = self._on_error
        self.on_info = self._on_info
    
    def _on_progress(self, message: str, current: int, total: int):
        """Handle progress updates"""
        if total > 0:
            percentage = (current / total) * 100
            print(f"\r{message} ({current}/{total}) {percentage:.1f}%", end='', flush=True)
        else:
            print(f"\r{message}...", end='', flush=True)
    
    def _on_debug(self, level: DebugLevel, message: str):
        """Handle debug messages"""
        level_names = {
            DebugLevel.NONE: "",
            DebugLevel.HEADERS: "HEADERS",
            DebugLevel.SECTORS: "SECTORS", 
            DebugLevel.BLOCKS: "BLOCKS",
            DebugLevel.VERBOSE: "VERBOSE"
        }
        
        level_name = level_names.get(level, "DEBUG")
        print(f"[{level_name}] {message}")
    
    def _on_warning(self, message: str):
        """Handle warning messages"""
        print(f"⚠️  WARNING: {message}")
    
    def _on_error(self, message: str):
        """Handle error messages - pero no detener la conversión"""
        self.error_count += 1
        # Solo mostrar errores críticos, no errores de secuencia de sectores
        if "sector sequence error" in message.lower():
            if self.verbose:
                print(f"🔄 INFO: {message}")
        else:
            print(f"❌ ERROR: {message}")
    
    def _on_info(self, message: str):
        """Handle info messages"""
        print(message)

def print_header(args):
    """Print program header"""
    print(f"TD0 to IMG Enhanced Converter V3.1 - Fixed")
    print(f"Input: {args.input}")
    print(f"Output: {args.output}")
    print(f"Debug level: {args.debug}")
    print(f"Options: warn_only={args.warn_only}, generate_def={args.generate_def}")
    print("=" * 50)

def print_geometry_info(geometry):
    """Print detected geometry information"""
    print(f"\n=== Detected Geometry ===")
    # Handle both dict and GeometryInfo objects
    if isinstance(geometry, dict):
        print(f"Type: {geometry.get('type', 'unknown')}")
        print(f"Cylinders: {geometry.get('cylinders', 0)}")
        print(f"Heads: {geometry.get('heads', 0)}")
        print(f"Sectors per track: {geometry.get('sectors_per_track', 16)}")
        print(f"Bytes per sector: {geometry.get('bytes_per_sector', 256)}")
        print(f"Has phantom sectors: {geometry.get('has_phantom', False)}")
        
        if geometry.get('type') == 'variable':
            print("Variable sector counts detected:")
            for track_id, count in geometry.get('sector_counts', {}).items():
                print(f"  Track {track_id[0]}.{track_id[1]}: {count} sectors")
    else:
        print(f"Type: {geometry.type}")
        print(f"Cylinders: {geometry.cylinders}")
        print(f"Heads: {geometry.heads}")
        print(f"Sectors per track: {geometry.sectors_per_track}")
        print(f"Bytes per sector: {geometry.bytes_per_sector}")
        print(f"Has phantom sectors: {geometry.has_phantom}")
        
        if geometry.type == 'variable':
            print("Variable sector counts detected:")
            for track_id, count in geometry.sector_counts.items():
                print(f"  Track {track_id[0]}.{track_id[1]}: {count} sectors")

def print_statistics(stats):
    """Print processing statistics"""
    print(f"\n=== Processing Statistics ===")
    print(f"Tracks processed: {stats.tracks_processed}")
    print(f"Sectors read: {stats.sectors_read}")
    print(f"Sectors skipped: {stats.sectors_skipped}")
    print(f"Sectors repeated: {stats.sectors_repeated}")
    print(f"Phantom sectors: {stats.phantom_sectors}")
    print(f"CRC errors: {stats.crc_errors}")
    print(f"Warnings: {stats.warnings}")
    print(f"Image size: {stats.image_size} bytes ({stats.image_size/1024:.1f} KB)")
    print(f"Conversion time: {stats.conversion_time:.2f} seconds")

def print_results(result: ConversionResult):
    """Print conversion results"""
    if result.success:
        print("\n✓ Conversion completed successfully!")
        
        if result.def_file:
            print(f"✓ Greaseweazle .def file generated: {result.def_file}")
        
        # Print Greaseweazle command
        print(f"\n=== Greaseweazle Command ===")
        print(f"To write this disk to a floppy, use:")
        print(f"\n{result.greaseweazle_command}")
        print(f"\nNote: Replace --drive=0 with your actual drive number")
        
    else:
        print("\n❌ Conversion failed!")
        print(f"Error: {result.error_message}")

def create_parser():
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        description='TD0 to IMG Converter V3.1 - Fixed (manejo mejorado de errores)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s disk.td0 disk.img                    # Basic conversion
  %(prog)s disk.td0 disk.img -d verbose         # Verbose debug output
  %(prog)s disk.td0 disk.img -w -g             # Warn-only mode with .def file
  %(prog)s disk.td0 disk.img --no-fix-boot    # Don't fix boot sector
        """
    )
    
    parser.add_argument('input', help='Input TD0 file')
    parser.add_argument('output', help='Output IMG file')
    
    parser.add_argument('-d', '--debug', 
                       choices=['none', 'headers', 'sectors', 'blocks', 'verbose'],
                       default='none', 
                       help='Debug level (default: none)')
    
    parser.add_argument('-w', '--warn-only', 
                       action='store_true',
                       help='Warn instead of error on sector sequence problems')
    
    parser.add_argument('-n', '--no-fix-boot', 
                       action='store_true',
                       help='Don\'t fix boot sector')
    
    parser.add_argument('-v', '--verbose', 
                       action='store_true',
                       help='Verbose output (show all messages)')
    
    parser.add_argument('-g', '--generate-def', 
                       action='store_true',
                       help='Generate Greaseweazle .def file from detected geometry')
    
    parser.add_argument('-q', '--quiet', 
                       action='store_true',
                       help='Minimize output (only show errors and final result)')
    
    parser.add_argument('--version', 
                       action='version', 
                       version='TD0 to IMG Converter V3.1 - Fixed')
    
    return parser

def validate_arguments(args):
    """Validate command line arguments"""
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found")
        return False
    
    if not args.input.lower().endswith('.td0'):
        print(f"Warning: Input file '{args.input}' doesn't have .td0 extension")
    
    # Check if output directory exists
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        print(f"Error: Output directory '{output_dir}' doesn't exist")
        return False
    
    # Check if output file already exists
    if os.path.exists(args.output):
        response = input(f"Output file '{args.output}' already exists. Overwrite? (y/N): ")
        if response.lower() not in ['y', 'yes']:
            print("Operation cancelled")
            return False
    
    return True

def main():
    """Main function"""
    parser = create_parser()
    args = parser.parse_args()
    
    # Validate arguments
    if not validate_arguments(args):
        sys.exit(1)
    
    # Map debug levels
    debug_levels = {
        'none': DebugLevel.NONE,
        'headers': DebugLevel.HEADERS,
        'sectors': DebugLevel.SECTORS,
        'blocks': DebugLevel.BLOCKS,
        'verbose': DebugLevel.VERBOSE
    }
    
    # FORZAR warn_only=True para evitar que se detenga en errores de secuencia
    warn_only_fixed = True  # Esto evita que se detenga en errores de secuencia
    
    # Create conversion options - FORZAMOS warn_only para que continue
    options = ConversionOptions(
        debug_level=debug_levels[args.debug],
        warn_only=warn_only_fixed,  # FORZADO a True
        force_hp150=True,  # Mantener por compatibilidad, pero no afecta la conversión
        fix_boot_sector=not args.no_fix_boot,
        verbose=args.verbose,
        generate_def=args.generate_def
    )
    
    # Create callbacks
    callbacks = FixedCLICallbacks(verbose=args.verbose)
    
    # Don't show header in quiet mode
    if not args.quiet:
        print_header(args)
        if not args.warn_only and warn_only_fixed:
            print("🔧 MODO FIJO: Ignorando errores de secuencia de sectores para continuar conversión")
    
    # Perform conversion
    converter = FixedTD0Converter(options, callbacks)
    result = converter.convert(args.input, args.output)
    
    # Print results
    if not args.quiet:
        if result.geometry:
            print_geometry_info(result.geometry)
        
        print_statistics(result.stats)
        
        # Mostrar resumen de errores encontrados pero ignorados
        if callbacks.error_count > 0:
            print(f"\n📊 Se encontraron {callbacks.error_count} errores de secuencia de sectores")
            print("   Estos errores fueron ignorados para permitir la conversión completa")
    
    print_results(result)
    
    # Verificar si la conversión fue exitosa a pesar de los errores
    if result.success and callbacks.error_count > 0:
        print(f"\n✅ Conversión completada con {callbacks.error_count} advertencias de secuencia")
        print("   El archivo IMG fue generado. Verifica que funcione correctamente.")
    
    # Exit with appropriate code
    sys.exit(0 if result.success else 1)

if __name__ == "__main__":
    main()
