#!/usr/bin/env python3
"""
Process all TD0 files from HP150_ALL_ORIGINAL directory
Creates organized directory structure with TD0 files, converted IMG files, and geometry info
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

def get_td0_files(directory):
    """Get all TD0 files from directory recursively"""
    td0_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.TD0'):
                td0_files.append(os.path.join(root, file))
    return sorted(td0_files)

def create_directory_structure(base_name, target_dir):
    """Create directory structure for a software package"""
    software_dir = os.path.join(target_dir, base_name)
    td0_dir = os.path.join(software_dir, "td0")
    img_dir = os.path.join(software_dir, "img")
    
    os.makedirs(td0_dir, exist_ok=True)
    os.makedirs(img_dir, exist_ok=True)
    
    return software_dir, td0_dir, img_dir

def analyze_img_geometry(img_file):
    """Analyze geometry of IMG file"""
    try:
        file_size = os.path.getsize(img_file)
        
        # HP-150 standard geometry calculations
        bytes_per_sector = 256
        sectors_per_track = 16
        total_sectors = file_size // bytes_per_sector
        
        # Determine if single-sided or double-sided based on total sectors
        # Single-sided: up to 80 tracks * 16 sectors = 1280 sectors = 327,680 bytes
        # Double-sided: up to 80 tracks * 2 heads * 16 sectors = 2560 sectors = 655,360 bytes
        
        if total_sectors <= 1280:  # Single-sided
            heads = 1
            cylinders = total_sectors // sectors_per_track
        else:  # Double-sided
            heads = 2
            tracks_total = total_sectors // sectors_per_track
            cylinders = tracks_total // heads
        
        return {
            'file_size': file_size,
            'cylinders': cylinders,
            'heads': heads,
            'sectors_per_track': sectors_per_track,
            'bytes_per_sector': bytes_per_sector,
            'total_sectors': total_sectors
        }
    except:
        # Default HP-150 geometry if analysis fails
        return {
            'file_size': 0,
            'cylinders': 80,
            'heads': 2,
            'sectors_per_track': 16,
            'bytes_per_sector': 256,
            'total_sectors': 2560
        }

def convert_td0_to_img(td0_file, converter_script):
    """Convert TD0 file to IMG using our converter"""
    try:
        img_output = f"{os.path.splitext(td0_file)[0]}.img"
        result = subprocess.run([
            sys.executable, converter_script, td0_file, img_output
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Successfully converted {os.path.basename(td0_file)}")
            return img_output
        else:
            print(f"❌ Failed to convert {os.path.basename(td0_file)}: {result.stderr}")
            return None
    except Exception as e:
        print(f"❌ Error converting {os.path.basename(td0_file)}: {e}")
        return None

def create_geometry_info(software_dir, td0_file, img_files):
    """Create geometry information file with actual geometry"""
    geometry_file = os.path.join(software_dir, "geometry.txt")
    base_name = os.path.splitext(os.path.basename(td0_file))[0]
    
    with open(geometry_file, 'w') as f:
        f.write(f"HP-150 Disk Geometry Information\n")
        f.write(f"================================\n\n")
        f.write(f"Software: {base_name}\n")
        f.write(f"Original TD0: {os.path.basename(td0_file)}\n")
        f.write(f"Converted IMG files: {', '.join([os.path.basename(img) for img in img_files])}\n\n")
        
        # Analyze geometry for each IMG file
        for img_file in img_files:
            img_name = os.path.basename(img_file)
            geometry = analyze_img_geometry(img_file)
            
            f.write(f"Actual Geometry for {img_name}:\n")
            f.write(f"{'=' * (25 + len(img_name))}\n")
            f.write(f"File size: {geometry['file_size']:,} bytes ({geometry['file_size']/1024:.1f} KB)\n")
            f.write(f"Cylinders: {geometry['cylinders']}\n")
            sided_text = "single-sided" if geometry['heads'] == 1 else "double-sided"
            f.write(f"Heads: {geometry['heads']} ({sided_text})\n")
            f.write(f"Sectors per track: {geometry['sectors_per_track']}\n")
            f.write(f"Bytes per sector: {geometry['bytes_per_sector']}\n")
            f.write(f"Total sectors: {geometry['total_sectors']}\n\n")
            
            f.write("GreaseWeazle Commands:\n")
            f.write("-" * 22 + "\n")
            f.write(f"# Write {img_name} to physical disk:\n")
            f.write(f"gw write --drive=A --format=img --cylinders={geometry['cylinders']} --heads={geometry['heads']} {img_name}\n\n")
            f.write(f"# Read physical disk with same geometry:\n")
            f.write(f"gw read --drive=A --format=img --cylinders={geometry['cylinders']} --heads={geometry['heads']} output.img\n\n")

def main():
    # Configuration
    original_dir = "/Users/pancho/Library/CloudStorage/GoogleDrive-espaciotec2019@gmail.com/My Drive/PROY/Archiving/HP150/SOFT/HP150_ALL_ORIGINAL"
    target_dir = "/Users/pancho/Library/CloudStorage/GoogleDrive-espaciotec2019@gmail.com/My Drive/PROY/Archiving/HP150/SOFT/HP150_PROCESSED"
    converter_script = "../td0_to_hp150_V1.0.py"
    
    # Verify converter script exists
    if not os.path.exists(converter_script):
        print(f"❌ Converter script not found: {converter_script}")
        return
    
    # Get all TD0 files
    td0_files = get_td0_files(original_dir)
    
    if not td0_files:
        print("❌ No TD0 files found in the original directory")
        return
    
    print(f"Found {len(td0_files)} TD0 files to process")
    
    # Process each TD0 file
    for td0_file in td0_files:
        base_name = os.path.splitext(os.path.basename(td0_file))[0]
        print(f"\n🔄 Processing: {base_name}")
        
        # Create directory structure
        software_dir, td0_dir, img_dir = create_directory_structure(base_name, target_dir)
        
        # Copy TD0 file to td0 directory
        shutil.copy2(td0_file, td0_dir)
        print(f"📁 Copied TD0 to {td0_dir}")
        
        # Convert TD0 to IMG
        img_output = convert_td0_to_img(td0_file, converter_script)
        if img_output and os.path.exists(img_output):
            # Move IMG file to img directory
            dest_path = os.path.join(img_dir, os.path.basename(img_output))
            shutil.move(img_output, dest_path)
            print(f"📁 Moved {os.path.basename(img_output)} to {img_dir}")
            
            # Create geometry info file
            create_geometry_info(software_dir, td0_file, [dest_path])
            print(f"📄 Created geometry.txt")
        
        print(f"✅ Completed: {base_name}")
    
    print(f"\n🎉 Processing complete! All files organized in {target_dir}")

if __name__ == "__main__":
    main()
