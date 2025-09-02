#!/usr/bin/env python3
"""
Generate a summary of all processed TD0 files
"""

import os
import time
from pathlib import Path

def generate_summary():
    """Generate a comprehensive summary report"""
    
    target_dir = "./HP150_ALL_ORIGINAL"
    
    # Count successful conversions
    successful_conversions = []
    failed_conversions = []
    
    # Walk through all directories
    for item in os.listdir(target_dir):
        item_path = os.path.join(target_dir, item)
        
        # Skip files, only process directories
        if os.path.isdir(item_path):
            img_dir = os.path.join(item_path, "img")
            td0_dir = os.path.join(item_path, "td0")
            
            # Check if conversion was successful
            if os.path.exists(img_dir) and os.listdir(img_dir):
                successful_conversions.append(item)
            else:
                failed_conversions.append(item)
    
    # Generate summary content
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    
    summary_content = f"""# HP-150 TD0 to IMG Conversion Summary
Generated: {timestamp}

## Overview
- **Total TD0 files processed**: {len(successful_conversions) + len(failed_conversions)}
- **Successfully converted**: {len(successful_conversions)}
- **Failed conversions**: {len(failed_conversions)}
- **Success rate**: {len(successful_conversions) / (len(successful_conversions) + len(failed_conversions)) * 100:.1f}%

## Successfully Converted Files
"""
    
    for software in sorted(successful_conversions):
        summary_content += f"- ✅ {software}\n"
    
    if failed_conversions:
        summary_content += f"\n## Failed Conversions\n"
        for software in sorted(failed_conversions):
            summary_content += f"- ❌ {software}\n"
    
    summary_content += f"""
## Directory Structure
Each successfully converted software package contains:
```
{target_dir}/[SOFTWARE_NAME]/
├── td0/                          # Original TD0 file
├── img/                          # Converted IMG file(s)
└── geometry.txt                  # Disk geometry and GreaseWeazle commands
```

## Usage Instructions
1. Navigate to the software directory you want to use
2. Check the `geometry.txt` file for GreaseWeazle commands
3. Use the commands to write IMG files to physical disks

## Example GreaseWeazle Commands
```bash
# Write IMG to physical disk
gw write --drive=A --format=img --cylinders=80 --heads=2 software.img

# Read physical disk
gw read --drive=A --format=img --cylinders=80 --heads=2 output.img
```

## Notes
- Standard HP-150 geometry is 80 cylinders, 2 heads, 9 sectors per track
- Some disks may have different geometry - check individual geometry.txt files
- Failed conversions are typically due to LZSS decompression issues with certain TD0 files
"""
    
    # Write summary to file
    with open("HP150_CONVERSION_SUMMARY.md", "w") as f:
        f.write(summary_content)
    
    print("Summary report generated: HP150_CONVERSION_SUMMARY.md")
    print(f"Successfully converted: {len(successful_conversions)}/{len(successful_conversions) + len(failed_conversions)} files")

if __name__ == "__main__":
    generate_summary()
