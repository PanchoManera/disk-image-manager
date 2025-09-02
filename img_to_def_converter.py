#!/usr/bin/env python3
"""
IMG to DEF Converter
Create Greaseweazle .def files from raw disk images (.IMG)

This tool analyzes an IMG file and creates a .def file that describes
the disk geometry for use with Greaseweazle flux tools.
"""

import os
import sys
import argparse
from modules.geometry_detector import GeometryDetector
from modules.def_generator import DefGenerator, DefGenerationOptions

def validate_files(img_path: str, def_path: str = None) -> tuple[bool, str]:
    """Validate input and output file paths"""
    # Check input file exists
    if not os.path.exists(img_path):
        return False, f"Input file '{img_path}' does not exist"
    
    # Check input file is IMG
    if not img_path.lower().endswith('.img'):
        print(f"Warning: Input file '{img_path}' doesn't have .img extension")
    
    # Auto-generate output path if not provided
    if def_path is None:
        def_path = os.path.splitext(img_path)[0] + '.def'
    
    # Check output directory exists
    output_dir = os.path.dirname(def_path)
    if output_dir and not os.path.exists(output_dir):
        return False, f"Output directory '{output_dir}' does not exist"
    
    return True, def_path

def get_file_info(file_path: str) -> str:
    """Get file size information"""
    try:
        size = os.path.getsize(file_path)
        if size < 1024:
            return f"{size} bytes"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"
    except:
        return "unknown size"

def main():
    parser = argparse.ArgumentParser(
        description="Create Greaseweazle .def files from raw disk images (.IMG)",
        epilog="""
Examples:
  python3 img_to_def_converter.py disk.img
  python3 img_to_def_converter.py disk.img disk.def
  python3 img_to_def_converter.py -v --show-geometry disk.img
  python3 img_to_def_converter.py --force disk.img custom.def
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('input', help='Input IMG file path')
    parser.add_argument('output', nargs='?', help='Output DEF file path (optional, auto-generated if not provided)')
    parser.add_argument('-v', '--verbose', action='store_true', 
                       help='Enable verbose output')
    parser.add_argument('-q', '--quiet', action='store_true',
                       help='Suppress all output except errors')
    parser.add_argument('-f', '--force', action='store_true',
                       help='Overwrite output file without asking')
    parser.add_argument('--show-geometry', action='store_true',
                       help='Display detected disk geometry information')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.verbose and args.quiet:
        print("Error: Cannot use both --verbose and --quiet options")
        sys.exit(1)
    
    img_path = os.path.abspath(args.input)
    
    # Validate files and get output path
    valid, result = validate_files(img_path, args.output)
    if not valid:
        print(f"Error: {result}")
        sys.exit(1)
    
    def_path = result
    
    # Check if output file already exists
    if os.path.exists(def_path) and not args.force:
        response = input(f"Output file '{def_path}' already exists. Overwrite? (y/N): ")
        if response.lower() not in ['y', 'yes']:
            print("Operation cancelled")
            sys.exit(1)
    
    # Show file info unless quiet
    if not args.quiet:
        print(f"Input: {os.path.basename(img_path)} ({get_file_info(img_path)})")
        print(f"Output: {os.path.basename(def_path)}")
        if args.verbose or args.show_geometry:
            print()
    
    try:
        # Detect geometry
        if args.verbose:
            print("Analyzing disk image geometry...")
        
        geometry = GeometryDetector().detect_from_file(img_path)
        
        # Show geometry info if requested
        if args.show_geometry or args.verbose:
            print("Detected Geometry:")
            print(f"  Source Format: {geometry.source_format.upper()}")
            print(f"  Geometry Type: {geometry.type}")
            print(f"  File Size: {geometry.file_size:,} bytes ({geometry.file_size/1024:.1f} KB)")
            print(f"  Cylinders: {geometry.cylinders}")
            print(f"  Heads: {geometry.heads}")
            print(f"  Sectors per Track: {geometry.sectors_per_track}")
            print(f"  Bytes per Sector: {geometry.bytes_per_sector}")
            print(f"  Total Sectors: {geometry.total_sectors}")
            
            if geometry.has_phantom:
                print("  ⚠️  Contains phantom sectors")
            
            if geometry.notes:
                print("  Notes:")
                for note in geometry.notes:
                    print(f"    • {note}")
            print()
        
        # Generate .def file
        if args.verbose:
            print("Generating .def file...")
        
        options = DefGenerationOptions()
        generator = DefGenerator(geometry, img_path, options)
        
        if generator.save_def_file(def_path):
            if not args.quiet:
                print(f"Success: Created {os.path.basename(def_path)}")
                if args.verbose:
                    print(f"Full path: {def_path}")
        else:
            print("Error: Failed to create .def file")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
