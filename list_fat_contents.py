import sys
import os
from modules.fat_lister import FATHandler

def main(img_path, extract_dir=None):
    with FATHandler(img_path) as handler:
        # Show disk info
        disk_info = handler.get_disk_info()
        print(f"Disk Info:")
        print(f"  Bytes per sector: {disk_info['bytes_per_sector']}")
        print(f"  Sectors per cluster: {disk_info['sectors_per_cluster']}")
        print(f"  FAT copies: {disk_info['fat_copies']}")
        print(f"  Total size: {disk_info['total_size']:,} bytes")
        print(f"  Used space: {disk_info['used_space']:,} bytes")
        print(f"  Free space: {disk_info['free_space']:,} bytes")
        print()
        
        # List files
        files = handler.list_files()
        visible_files = handler.list_visible_files()
        
        print(f"Files and directories in the image ({len(files)} total, {len(visible_files)} visible):")
        if not files:
            print("  (No files found)")
        else:
            print(f"{'Name':<15} {'Size':<10} {'Type':<8} {'Attr':<6}")
            print("-" * 45)
            for file in files:
                file_type = "DIR" if file.is_directory else "VOL" if file.is_volume else "FILE"
                if file.attr & 0x02:
                    file_type += ",HID"
                if file.attr & 0x04:
                    file_type += ",SYS"
                print(f"{file.full_name:<15} {file.size:<10,} {file_type:<8} 0x{file.attr:02X}")
        
        # Extract files if requested
        if extract_dir:
            print(f"\nExtracting files to directory: {extract_dir}")
            print("-" * 50)
            
            extracted_files = handler.extract_files(extract_dir)
            
            if extracted_files:
                print(f"\nSuccessfully extracted {len(extracted_files)} files to '{extract_dir}'")
            else:
                print("\nNo files were extracted (no regular files found)")

if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python list_fat_contents.py <img_path> [extract_dir]")
        print("  img_path: Path to the FAT image file (.img) or TD0 file (.td0)")
        print("  extract_dir: Optional directory to extract files to")
        print("")
        print("Supported formats: IMG, TD0 (automatically converted)")
        sys.exit(1)
    else:
        img_path = sys.argv[1]
        extract_dir = sys.argv[2] if len(sys.argv) == 3 else None
        main(img_path, extract_dir)
