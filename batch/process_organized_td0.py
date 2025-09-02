#!/usr/bin/env python3
"""
Process organized TD0 files and generate comprehensive analysis
Including geometry information and conversion statistics
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from collections import defaultdict
import re

def get_all_td0_files(directory):
    """Get all TD0 files from directory recursively"""
    td0_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.TD0'):
                td0_files.append(os.path.join(root, file))
    return sorted(td0_files)

def get_software_from_path(td0_path, base_dir):
    """Extract software name from TD0 file path"""
    relative_path = os.path.relpath(td0_path, base_dir)
    software_name = relative_path.split('/')[0]
    return software_name

def convert_td0_to_img(td0_file, converter_script):
    """Convert TD0 file to IMG using our converter and capture geometry info"""
    try:
        img_output = f"{os.path.splitext(td0_file)[0]}.img"
        result = subprocess.run([
            sys.executable, converter_script, td0_file, img_output
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            # Extract geometry info from output
            geometry_info = parse_geometry_from_output(result.stdout)
            return img_output, geometry_info
        else:
            print(f"❌ Failed to convert {os.path.basename(td0_file)}: {result.stderr}")
            return None, None
    except Exception as e:
        print(f"❌ Error converting {os.path.basename(td0_file)}: {e}")
        return None, None

def parse_geometry_from_output(output):
    """Parse geometry information from converter output"""
    geometry = {}
    
    # Extract geometry information from the output
    lines = output.split('\n')
    for line in lines:
        if "Cilindros:" in line:
            match = re.search(r'Cilindros:\s*(\d+)', line)
            if match:
                geometry['cylinders'] = int(match.group(1))
        elif "Cabezas:" in line:
            match = re.search(r'Cabezas:\s*(\d+)', line)
            if match:
                geometry['heads'] = int(match.group(1))
        elif "Sectores:" in line and "Track" in line:
            match = re.search(r'Sectores:\s*(\d+)', line)
            if match:
                geometry['sectors'] = int(match.group(1))
        elif "Tamaño imagen:" in line:
            match = re.search(r'(\d+)\s*bytes', line)
            if match:
                geometry['size'] = int(match.group(1))
    
    return geometry

def create_software_directory(software_name, base_dir):
    """Create organized directory structure for software"""
    software_dir = os.path.join(base_dir, software_name)
    td0_dir = os.path.join(software_dir, "td0")
    img_dir = os.path.join(software_dir, "img")
    
    os.makedirs(td0_dir, exist_ok=True)
    os.makedirs(img_dir, exist_ok=True)
    
    return software_dir, td0_dir, img_dir

def create_geometry_file(software_dir, software_name, disk_info):
    """Create comprehensive geometry file for software"""
    geometry_file = os.path.join(software_dir, "geometry.txt")
    
    with open(geometry_file, 'w') as f:
        f.write(f"HP-150 Disk Geometry Information\n")
        f.write(f"================================\n\n")
        f.write(f"Software: {software_name}\n")
        f.write(f"Total disks: {len(disk_info)}\n\n")
        
        # Write information for each disk
        for i, (td0_file, img_file, geometry) in enumerate(disk_info, 1):
            f.write(f"Disk {i}:\n")
            f.write(f"--------\n")
            f.write(f"TD0 file: {os.path.basename(td0_file)}\n")
            f.write(f"IMG file: {os.path.basename(img_file) if img_file else 'CONVERSION FAILED'}\n")
            
            if geometry:
                f.write(f"Cylinders: {geometry.get('cylinders', 'Unknown')}\n")
                f.write(f"Heads: {geometry.get('heads', 'Unknown')}\n")
                f.write(f"Sectors: {geometry.get('sectors', 'Unknown')}\n")
                f.write(f"Size: {geometry.get('size', 'Unknown')} bytes\n")
                
                # Generate GreaseWeazle commands
                if all(k in geometry for k in ['cylinders', 'heads']):
                    f.write(f"\nGreaseWeazle commands for {os.path.basename(img_file)}:\n")
                    f.write(f"gw write --drive=A --format=img --cylinders={geometry['cylinders']} --heads={geometry['heads']} {os.path.basename(img_file)}\n")
                    f.write(f"gw read --drive=A --format=img --cylinders={geometry['cylinders']} --heads={geometry['heads']} output.img\n")
            else:
                f.write("Geometry: CONVERSION FAILED\n")
            
            f.write("\n")

def main():
    # Configuration
    original_dir = "./HP150_ALL_ORIGINAL"
    output_dir = "./HP150_PROCESSED"
    converter_script = "./td0_to_hp150.py"
    
    # Verify converter script exists
    if not os.path.exists(converter_script):
        print(f"❌ Converter script not found: {converter_script}")
        return
    
    # Get all TD0 files
    td0_files = get_all_td0_files(original_dir)
    
    if not td0_files:
        print("❌ No TD0 files found in the directory")
        return
    
    print(f"Found {len(td0_files)} TD0 files to process")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Track results
    software_results = defaultdict(list)
    geometry_types = defaultdict(int)
    successful_conversions = 0
    failed_conversions = 0
    
    # Process each TD0 file
    for td0_file in td0_files:
        software_name = get_software_from_path(td0_file, original_dir)
        print(f"\n🔄 Processing: {os.path.basename(td0_file)} [{software_name}]")
        
        # Convert TD0 to IMG
        img_output, geometry = convert_td0_to_img(td0_file, converter_script)
        
        if img_output and os.path.exists(img_output):
            successful_conversions += 1
            print(f"✅ Successfully converted {os.path.basename(td0_file)}")
            
            # Track geometry types
            if geometry:
                geom_key = f"{geometry.get('cylinders', '?')}c/{geometry.get('heads', '?')}h/{geometry.get('sectors', '?')}s"
                geometry_types[geom_key] += 1
        else:
            failed_conversions += 1
            print(f"❌ Failed to convert {os.path.basename(td0_file)}")
        
        # Store results for this software
        software_results[software_name].append((td0_file, img_output, geometry))
    
    # Process results by software
    print(f"\n📦 Creating organized directories...")
    
    for software_name, disk_info in software_results.items():
        # Create software directory structure
        software_dir, td0_dir, img_dir = create_software_directory(software_name, output_dir)
        
        # Copy TD0 files and move IMG files
        for td0_file, img_file, geometry in disk_info:
            # Copy TD0 file
            shutil.copy2(td0_file, td0_dir)
            
            # Move IMG file if it exists
            if img_file and os.path.exists(img_file):
                dest_img = os.path.join(img_dir, os.path.basename(img_file))
                shutil.move(img_file, dest_img)
        
        # Create geometry file
        create_geometry_file(software_dir, software_name, disk_info)
        
        print(f"📁 Created: {software_name} ({len(disk_info)} disks)")
    
    # Generate summary report
    generate_summary_report(software_results, geometry_types, successful_conversions, failed_conversions)
    
    print(f"\n🎉 Processing complete!")
    print(f"📊 Results: {successful_conversions} successful, {failed_conversions} failed")

def generate_summary_report(software_results, geometry_types, successful, failed):
    """Generate comprehensive summary report"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    
    report_content = f"""# HP-150 TD0 Processing Complete Report
Generated: {timestamp}

## Overview
- **Total TD0 files processed**: {successful + failed}
- **Successfully converted**: {successful}
- **Failed conversions**: {failed}
- **Success rate**: {successful / (successful + failed) * 100:.1f}%
- **Software packages**: {len(software_results)}

## Geometry Types Found
"""
    
    for geom_type, count in sorted(geometry_types.items()):
        report_content += f"- {geom_type}: {count} disks\n"
    
    report_content += f"\n## Software Packages Summary\n"
    
    for software_name, disk_info in sorted(software_results.items()):
        successful_disks = sum(1 for _, img, _ in disk_info if img is not None)
        failed_disks = len(disk_info) - successful_disks
        
        if successful_disks == len(disk_info):
            status = "✅"
        elif successful_disks > 0:
            status = "⚠️"
        else:
            status = "❌"
        
        report_content += f"{status} **{software_name}** ({len(disk_info)} disks: {successful_disks} OK, {failed_disks} failed)\n"
    
    report_content += f"""
## Directory Structure
```
HP150_PROCESSED/
├── [Software_Name]/
│   ├── td0/          # Original TD0 files
│   ├── img/          # Converted IMG files
│   └── geometry.txt  # Disk geometry and commands
```

## Common Geometries
- **Single-sided disks**: Usually 71 cylinders, 1 head, 17 sectors
- **Double-sided disks**: Usually 80 cylinders, 2 heads, 9 sectors
- **Variations**: Some disks may have different sector counts or cylinder counts

## Usage
Each software directory contains:
1. Original TD0 files in `td0/` folder
2. Converted IMG files in `img/` folder
3. Geometry information and GreaseWeazle commands in `geometry.txt`

## GreaseWeazle Commands
Check individual `geometry.txt` files for specific commands for each disk.
"""
    
    # Write report to file
    with open("HP150_COMPLETE_REPORT.md", "w") as f:
        f.write(report_content)
    
    print(f"📄 Complete report saved to: HP150_COMPLETE_REPORT.md")

if __name__ == "__main__":
    main()
