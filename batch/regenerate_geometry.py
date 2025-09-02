#!/usr/bin/env python3
"""
Regenerate geometry.txt files with actual geometry information
for all processed HP-150 software
"""

import os
import glob
from pathlib import Path

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
    processed_dir = "/Users/pancho/Library/CloudStorage/GoogleDrive-espaciotec2019@gmail.com/My Drive/PROY/Archiving/HP150/SOFT/HP150_PROCESSED"
    
    if not os.path.exists(processed_dir):
        print(f"❌ Processed directory not found: {processed_dir}")
        return
    
    # Find all software directories
    software_dirs = [d for d in os.listdir(processed_dir) if os.path.isdir(os.path.join(processed_dir, d))]
    
    print(f"Found {len(software_dirs)} software directories to process")
    
    updated_count = 0
    
    for software_name in software_dirs:
        software_dir = os.path.join(processed_dir, software_name)
        td0_dir = os.path.join(software_dir, "td0")
        img_dir = os.path.join(software_dir, "img")
        
        # Check if directories exist
        if not os.path.exists(td0_dir) or not os.path.exists(img_dir):
            print(f"⏭️  Skipping {software_name} - missing td0 or img directory")
            continue
        
        # Find TD0 and IMG files
        td0_files = glob.glob(os.path.join(td0_dir, "*.TD0"))
        img_files = glob.glob(os.path.join(img_dir, "*.img"))
        
        if not td0_files or not img_files:
            print(f"⏭️  Skipping {software_name} - no TD0 or IMG files found")
            continue
        
        # Use the first TD0 file as reference
        td0_file = td0_files[0]
        
        print(f"🔄 Updating geometry for: {software_name}")
        
        # Create updated geometry info
        create_geometry_info(software_dir, td0_file, img_files)
        updated_count += 1
        
        print(f"✅ Updated: {software_name}")
    
    print(f"\n🎉 Geometry regeneration complete! Updated {updated_count} files")

if __name__ == "__main__":
    main()
