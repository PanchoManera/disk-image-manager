#!/usr/bin/env python3
"""
IMD to IMG Converter
Convert ImageDisk (.IMD) files to raw disk images (.IMG)

Based on imd2raw.c by David Schmidt, Tom Burnett, and others
Fixes sector skew issues and handles compressed/bad sectors correctly
"""

import os
import sys
import argparse
from modules.imd_handler import IMD2IMGConverter
from modules.geometry_detector import GeometryDetector
from modules.def_generator import DefGenerator, DefGenerationOptions

def validate_files(imd_path: str, img_path: str) -> bool:
    """Validate input and output file paths"""
    # Check input file exists
    if not os.path.exists(imd_path):
        print(f"Error: Input file '{imd_path}' does not exist")
        return False
    
    # Check input file is IMD
    if not imd_path.lower().endswith('.imd'):
        print(f"Warning: Input file '{imd_path}' doesn't have .imd extension")
    
    # Check output directory exists
    output_dir = os.path.dirname(img_path)
    if output_dir and not os.path.exists(output_dir):
        print(f"Error: Output directory '{output_dir}' does not exist")
        return False
    
    # Check if output file already exists
    if os.path.exists(img_path):
        response = input(f"Output file '{img_path}' already exists. Overwrite? (y/N): ")
        if response.lower() not in ['y', 'yes']:
            print("Conversion cancelled")
            return False
    
    return True

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
        description="Convert ImageDisk (.IMD) files to raw disk images (.IMG)",
        epilog="""
Examples:
  python3 imd2img_converter.py disk.imd disk.img
  python3 imd2img_converter.py -v source.imd output.img
  python3 imd2img_converter.py --quiet disk.imd disk.img
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('input', help='Input IMD file path')
    parser.add_argument('output', help='Output IMG file path')
    parser.add_argument('-v', '--verbose', action='store_true', 
                       help='Enable verbose output (show track/sector details)')
    parser.add_argument('-q', '--quiet', action='store_true',
                       help='Suppress all output except errors')
    parser.add_argument('-f', '--force', action='store_true',
                       help='Overwrite output file without asking')
    parser.add_argument('--create-def', action='store_true',
                       help='Also create a .def file for use with Greaseweazle')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.verbose and args.quiet:
        print("Error: Cannot use both --verbose and --quiet options")
        sys.exit(1)
    
    imd_path = os.path.abspath(args.input)
    img_path = os.path.abspath(args.output)
    
    # Validate files unless forced
    if not args.force:
        if not validate_files(imd_path, img_path):
            sys.exit(1)
    else:
        # Quick check for input file existence
        if not os.path.exists(imd_path):
            print(f"Error: Input file '{imd_path}' does not exist")
            sys.exit(1)
    
    # Show file info unless quiet
    if not args.quiet:
        print(f"Converting: {os.path.basename(imd_path)} ({get_file_info(imd_path)})")
        print(f"Output: {os.path.basename(img_path)}")
        if args.verbose:
            print()
    
    # Perform conversion
    converter = IMD2IMGConverter(verbose=args.verbose and not args.quiet)
    success = converter.convert(imd_path, img_path)
    
    if success:
        if not args.quiet:
            output_size = get_file_info(img_path)
            print(f"Success: Created {os.path.basename(img_path)} ({output_size})")
        
        # Create .def file if requested
        if args.create_def:
            def_path = os.path.splitext(img_path)[0] + '.def'
            
            try:
                if not args.quiet:
                    print(f"Creating .def file: {os.path.basename(def_path)}")
                
                # Generate geometry from the IMG file
                geometry = GeometryDetector().detect_from_file(img_path)
                options = DefGenerationOptions()
                generator = DefGenerator(geometry, img_path, options)
                
                if generator.save_def_file(def_path):
                    if not args.quiet:
                        print(f"Success: Created {os.path.basename(def_path)}")
                else:
                    print(f"Warning: Failed to create .def file")
                    
            except Exception as e:
                print(f"Warning: Error creating .def file: {str(e)}")
        
        sys.exit(0)
    else:
        print(f"Error: Failed to convert {os.path.basename(imd_path)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
