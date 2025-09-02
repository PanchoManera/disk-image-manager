#!/usr/bin/env python3
"""
Organize HP150 files into software-specific directories
Each software will have its own directory with all related TD0 files
"""

import os
import shutil
import glob
from pathlib import Path

def organize_software_directories():
    """Organize all files into software-specific directories"""
    
    base_dir = "./HP150_ALL_ORIGINAL"
    
    # Get all items in the directory
    items = os.listdir(base_dir)
    
    # Process each item
    for item in items:
        item_path = os.path.join(base_dir, item)
        
        # Skip hidden files
        if item.startswith('.'):
            continue
            
        # If it's a directory, leave it as is (it's already organized)
        if os.path.isdir(item_path):
            print(f"📁 Directory already exists: {item}")
            continue
            
        # If it's a TD0 file, create a directory for it
        if item.endswith('.TD0'):
            # Extract software name (remove .TD0 extension)
            software_name = item[:-4]  # Remove .TD0
            software_dir = os.path.join(base_dir, software_name)
            
            # Create directory if it doesn't exist
            os.makedirs(software_dir, exist_ok=True)
            
            # Move the TD0 file to the software directory
            dest_path = os.path.join(software_dir, item)
            shutil.move(item_path, dest_path)
            print(f"📦 Created directory and moved: {item} -> {software_name}/")
            
        # If it's other file type (.hpi, etc.), create directory based on filename
        elif '.' in item:
            # Extract software name (remove extension)
            software_name = os.path.splitext(item)[0]
            software_dir = os.path.join(base_dir, software_name)
            
            # Create directory if it doesn't exist
            os.makedirs(software_dir, exist_ok=True)
            
            # Move the file to the software directory
            dest_path = os.path.join(software_dir, item)
            shutil.move(item_path, dest_path)
            print(f"📦 Created directory and moved: {item} -> {software_name}/")

def find_all_td0_files():
    """Find all TD0 files in the organized structure"""
    base_dir = "./HP150_ALL_ORIGINAL"
    td0_files = []
    
    # Walk through all directories
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith('.TD0'):
                td0_files.append(os.path.join(root, file))
    
    return sorted(td0_files)

def main():
    print("🔧 Organizing HP150 software directories...")
    organize_software_directories()
    
    print("\n📊 Summary of TD0 files found:")
    td0_files = find_all_td0_files()
    
    software_count = {}
    for td0_file in td0_files:
        # Extract software directory name
        relative_path = os.path.relpath(td0_file, "./HP150_ALL_ORIGINAL")
        software_name = relative_path.split('/')[0]
        
        if software_name not in software_count:
            software_count[software_name] = []
        software_count[software_name].append(os.path.basename(td0_file))
    
    print(f"\n📈 Found {len(td0_files)} TD0 files across {len(software_count)} software packages:")
    
    for software, files in sorted(software_count.items()):
        if len(files) == 1:
            print(f"  📀 {software} (1 disk)")
        else:
            print(f"  💿 {software} ({len(files)} disks)")
            for file in files:
                print(f"    - {file}")
    
    print(f"\n✅ Organization complete! Total: {len(td0_files)} TD0 files")

if __name__ == "__main__":
    main()
