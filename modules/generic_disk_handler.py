#!/usr/bin/env python3
"""
Generic Disk Handler - Detects and handles different disk formats
Supports FAT12/16/32, HP150 FAT, CP/M, and provides generic hex dump fallback
"""

import struct
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from .enhanced_format_detector import EnhancedFormatDetector, DiskFormat

@dataclass
class FileEntry:
    name: str
    ext: str
    attr: int
    cluster: int
    size: int
    offset: int
    format_type: str = "unknown"

    @property
    def full_name(self) -> str:
        if self.format_type == "cpm":
            # CP/M files don't always have extensions
            return f"{self.name}.{self.ext}" if self.ext and self.ext.strip() else self.name
        else:
            return f"{self.name}.{self.ext}" if self.ext else self.name

    @property
    def is_directory(self) -> bool:
        if self.format_type == "cpm":
            return False  # CP/M doesn't have subdirectories
        return bool(self.attr & 0x10)

    @property
    def is_volume(self) -> bool:
        if self.format_type == "cpm":
            return False  # CP/M doesn't have volume labels in directory
        return bool(self.attr & 0x08)

class GenericDiskHandler:
    def __init__(self, image_path: str):
        self.image_path = image_path
        self.file_handle = open(image_path, 'rb')
        self.format_type = "unknown"
        self.files = []
        self.disk_info = {}
        
        # Detect format and initialize appropriate handler
        self._detect_and_initialize_format()
    
    def _detect_and_initialize_format(self):
        """Detect disk format and initialize appropriate handler"""
        # Use enhanced format detector
        detector = EnhancedFormatDetector(self.image_path)
        detection_result = detector.detect_format()
        
        print(f"[INFO] Format detection: {detection_result.format_type.value} (confidence: {detection_result.confidence:.2f})")
        for note in detection_result.notes:
            print(f"[INFO] {note}")
        
        # Initialize appropriate handler based on detection
        if detection_result.format_type == DiskFormat.FAT_HP150:
            self.format_type = "fat_hp150"
            self._init_hp150_handler(detection_result.parameters)
        elif detection_result.format_type == DiskFormat.FAT_STANDARD:
            self.format_type = "fat"
            self._init_fat_handler()
        elif detection_result.format_type == DiskFormat.CPM:
            self.format_type = "cpm"
            self._init_cpm_handler()
        else:
            self.format_type = "raw"
            self._init_raw_handler()
    
    def _detect_fat_format(self) -> bool:
        """Check if this appears to be a FAT filesystem"""
        try:
            # Check for FAT boot sector signature (standard FAT)
            self.file_handle.seek(0)
            boot_sector = self.file_handle.read(512)
            
            if len(boot_sector) < 512:
                return False
            
            # Check for FAT boot signature (standard)
            if boot_sector[510:512] == b'\x55\xAA':
                print("[DEBUG] Detected FAT by boot signature")
                return True
            
            # Check for FAT structure without boot signature (standard BPB)
            try:
                bytes_per_sector = struct.unpack('<H', boot_sector[11:13])[0]
                sectors_per_cluster = boot_sector[13]
                reserved_sectors = struct.unpack('<H', boot_sector[14:16])[0]
                fat_copies = boot_sector[16]
                root_entries = struct.unpack('<H', boot_sector[17:19])[0]
                
                # Check if values are reasonable for FAT
                fat_indicators = 0
                
                if bytes_per_sector in [256, 512, 1024, 2048]:
                    fat_indicators += 1
                if sectors_per_cluster in [1, 2, 4, 8, 16, 32, 64, 128]:
                    fat_indicators += 1
                if 1 <= reserved_sectors <= 32:
                    fat_indicators += 1
                if 1 <= fat_copies <= 3:
                    fat_indicators += 1
                if root_entries > 0 and root_entries <= 512:
                    fat_indicators += 1
                
                # Also check for recognizable OEM name
                oem_name = boot_sector[3:11].decode('ascii', errors='ignore').strip()
                if oem_name and len(oem_name) >= 3:
                    fat_indicators += 1
                
                print(f"[DEBUG] FAT indicators: {fat_indicators}/6 (bps={bytes_per_sector}, spc={sectors_per_cluster}, res={reserved_sectors}, fats={fat_copies}, root={root_entries}, oem='{oem_name}')")
                
                # If we have at least 4 good indicators, consider it FAT
                if fat_indicators >= 4:
                    print("[DEBUG] Detected FAT by BPB structure")
                    return True
                
            except:
                pass
            
            # Generic FAT detection: Look for valid directory structures at common offsets
            # This works for HP150, non-standard FAT, and converted images
            file_size = os.path.getsize(self.image_path)
            
            # Try common directory offsets used by various systems
            directory_offsets = [
                # HP150 specific offsets (priority order)
                0x700,    # HP150 Financial Calculator main directory
                0x800,    # HP150 Touch Games and other software
                0x1100,   # HP150 standard directory
                0x2400,   # HP150 alternative
                0x5000,   # HP150 specific case
                0x6000,   # HP150 alternative
                
                # Standard FAT calculated offsets (various configurations)
                0x1e00,   # Common standard FAT
                0x2600,   # Another standard calculation
                0x4200,   # Standard FAT for larger disks
                
                # Other common offsets
                0x1000,   # Common round number
                0x2000,   # Another common offset
                0x3000,   # Often used boundary
                0x1400,   # Alternate calculation
                0x1500,   # More alternatives
                0x1600,
            ]
            
            for offset in directory_offsets:
                if offset >= file_size:
                    continue
                    
                valid_files = self._count_valid_fat_entries_at_offset(offset)
                if valid_files >= 3:  # Found enough valid FAT entries
                    print(f"[DEBUG] Detected FAT by directory structure at 0x{offset:x} ({valid_files} valid entries)")
                    return True
            
            return False
        except:
            return False
    
    def _count_valid_fat_entries_at_offset(self, offset: int) -> int:
        """Count valid FAT directory entries at given offset"""
        try:
            self.file_handle.seek(offset)
            dir_data = self.file_handle.read(512)  # Read one sector
            
            valid_entries = 0
            
            for i in range(0, 512, 32):  # FAT entries are 32 bytes
                if i + 32 > len(dir_data):
                    break
                    
                entry = dir_data[i:i+32]
                first_byte = entry[0]
                
                # End of directory
                if first_byte == 0:
                    break
                    
                # Deleted entry
                if first_byte == 0xE5:
                    continue
                
                # Invalid first character
                if first_byte < 0x20:
                    continue
                
                try:
                    name = entry[0:8].decode('ascii', errors='ignore').strip()
                    ext = entry[8:11].decode('ascii', errors='ignore').strip()
                    attr = entry[11]
                    size = struct.unpack('<L', entry[28:32])[0]
                    
                    # Relaxed validation for FAT entries
                    name_valid = (name and 
                                  len(name.strip()) >= 1 and  # At least 1 char (more flexible)
                                  any(c.isalnum() or c in '._-+' for c in name))  # Allow more chars
                    
                    attr_valid = attr < 0x80  # Reasonable attribute value
                    size_valid = size < 10000000  # Less than 10MB (more flexible)
                    
                    if name_valid and attr_valid and size_valid:
                        valid_entries += 1
                        
                except:
                    continue
            
            return valid_entries
            
        except:
            return 0
    
    def _detect_cpm_format(self) -> bool:
        """Check if this appears to be a CP/M filesystem"""
        try:
            file_size = os.path.getsize(self.image_path)
            
            # Common CP/M disk sizes
            cpm_sizes = [
                200704,   # 8" SSSD
                400896,   # 8" DSDD  
                1024000,  # Osborne-1 DD
                204800,   # Osborne-1 SD
                212075,   # HP150 specific size (matches our Wordstar disk)
                746496,   # HP150 converted size
                368640,   # Common 360K size
                102400,   # Some smaller formats
            ]
            
            # Check if size matches common CP/M formats
            size_match = any(abs(file_size - size) < 2048 for size in cpm_sizes)
            
            if size_match:
                print(f"[DEBUG] File size {file_size} matches CP/M format")
                
                # For Osborne-1, try the standard offset first
                # Osborne-1 uses 1024-byte sectors, 5 sectors per track, single head
                # Directory typically starts at track 3 (offset 0x3000)
                osborne_offsets = [
                    0x3000,   # Track 3 * 5 sectors * 1024 bytes = 15360 = 0x3C00 (but try 0x3000 too)
                    0x3C00,   # Track 3 proper calculation 
                    0x1400,   # Track 1
                    0x2800,   # Track 2  
                    0x1100,   # Traditional
                    0x2000,   # Common alternative
                    0x2400,   # Another alternative
                ]
                
                # Look for CP/M directory patterns
                for offset in osborne_offsets:
                    print(f"[DEBUG] Checking CP/M directory at offset 0x{offset:x}")
                    if self._check_cpm_directory_at_offset(offset):
                        print(f"[INFO] Detected CP/M format with directory at 0x{offset:x}")
                        return True
            
            return False
        except:
            return False
    
    def _check_cpm_directory_at_offset(self, offset: int) -> bool:
        """Check if there's a valid CP/M directory at the given offset"""
        try:
            self.file_handle.seek(offset)
            dir_data = self.file_handle.read(2048)  # Read several directory entries
            
            valid_entries = 0
            total_checked = 0
            
            for i in range(0, min(len(dir_data), 1024), 32):  # CP/M entries are 32 bytes
                if i + 32 > len(dir_data):
                    break
                    
                entry = dir_data[i:i+32]
                user_code = entry[0]
                
                # Skip deleted entries
                if user_code == 0xE5:
                    continue
                
                # Check if it looks like a valid CP/M entry
                if user_code <= 15:  # Valid user codes 0-15
                    filename_area = entry[1:12]  # 11 bytes for filename
                    
                    # Check if filename contains reasonable characters
                    printable_chars = 0
                    for byte in filename_area:
                        if 0x20 <= byte <= 0x7E:  # Printable ASCII
                            printable_chars += 1
                        elif byte == 0x00 or byte == 0x20:  # Null or space (padding)
                            continue
                        else:
                            break
                    
                    if printable_chars >= 1:  # At least one printable character
                        valid_entries += 1
                    
                    total_checked += 1
                    
                    if total_checked >= 16:  # Check first 16 entries
                        break
            
            # If we found reasonable CP/M entries, consider it CP/M
            if valid_entries >= 2 and total_checked > 0:
                return True
                
            return False
        except:
            return False
    
    def _init_hp150_handler(self, parameters: Dict):
        """Initialize HP150 FAT handler"""
        try:
            from .hp150_fat_handler import HP150FATHandler
            self._hp150_handler = HP150FATHandler(
                self.image_path, 
                root_dir_offset=parameters.get('root_dir_offset')
            )
            self.files = self._hp150_handler.list_files()
            self.disk_info = self._hp150_handler.get_disk_info()
            
        except Exception as e:
            print(f"[WARN] HP150 handler failed: {e}, falling back to standard FAT")
            self._init_fat_handler()
    
    def _init_fat_handler(self):
        """Initialize FAT handler"""
        try:
            from .fat_lister import FATHandler
            self._fat_handler = FATHandler(self.image_path)
            fat_files = self._fat_handler.list_files()
            self.disk_info = self._fat_handler.get_disk_info()
            
            # Convert FAT FileEntry objects to our format
            self.files = []
            for fat_file in fat_files:
                # Add format_type attribute if it doesn't exist
                if not hasattr(fat_file, 'format_type'):
                    fat_file.format_type = "fat"
                self.files.append(fat_file)
                
        except Exception as e:
            print(f"[WARN] FAT handler failed: {e}, falling back to raw")
            self._init_raw_handler()
    
    def _init_cpm_handler(self):
        """Initialize CP/M handler"""
        self.files = []
        
        # Find CP/M directory location - use same offsets as detection
        cpm_dir_offset = None
        osborne_offsets = [
            0x3000,   # Track 3 * 5 sectors * 1024 bytes
            0x3C00,   # Track 3 proper calculation 
            0x1400,   # Track 1
            0x2800,   # Track 2  
            0x1100,   # Traditional
            0x2000,   # Common alternative
            0x2400,   # Another alternative
        ]
        
        for offset in osborne_offsets:
            if self._check_cpm_directory_at_offset(offset):
                cpm_dir_offset = offset
                break
        
        if not cpm_dir_offset:
            print("[WARN] Could not locate CP/M directory")
            self._init_raw_handler()
            return
        
        # Parse CP/M directory
        self.file_handle.seek(cpm_dir_offset)
        dir_data = self.file_handle.read(2048)
        
        parsed_files = {}  # Track files by name to handle extents
        
        for i in range(0, len(dir_data), 32):
            if i + 32 > len(dir_data):
                break
                
            entry = dir_data[i:i+32]
            user_code = entry[0]
            
            # Skip deleted entries
            if user_code == 0xE5:
                continue
            
            # Skip invalid user codes
            if user_code > 15:
                continue
            
            # Parse CP/M filename (8.3 format)
            filename_raw = entry[1:9]
            extension_raw = entry[9:12]
            extent = entry[12]
            
            # Clean filename
            filename = self._clean_cpm_filename(filename_raw)
            extension = self._clean_cpm_filename(extension_raw)
            
            if not filename:
                continue
            
            # Calculate approximate size from allocation map
            allocation_map = entry[16:32]
            blocks_used = sum(1 for b in allocation_map if b != 0)
            estimated_size = blocks_used * 1024  # Approximate
            
            # Create file entry
            full_name = f"{filename}.{extension}" if extension else filename
            
            if full_name not in parsed_files:
                file_entry = FileEntry(
                    name=filename,
                    ext=extension,
                    attr=0x00,  # CP/M doesn't have attributes like FAT
                    cluster=0,  # CP/M uses different allocation
                    size=estimated_size,
                    offset=cpm_dir_offset + i,
                    format_type="cpm"
                )
                parsed_files[full_name] = file_entry
                self.files.append(file_entry)
        
        # Set disk info
        file_size = os.path.getsize(self.image_path)
        self.disk_info = {
            'total_size': file_size,
            'used_space': 0,  # Would need more complex calculation
            'free_space': file_size,
            'system_space': 0,
            'bytes_per_sector': 1024,  # Common for Osborne-1
            'sectors_per_cluster': 1,
            'fat_copies': 0  # CP/M doesn't use FAT
        }
    
    def _clean_cpm_filename(self, name_bytes: bytes) -> str:
        """Clean CP/M filename bytes"""
        try:
            # CP/M filenames use high bit for attributes, mask it off
            clean_bytes = bytes(b & 0x7F for b in name_bytes)
            decoded = clean_bytes.decode('ascii', errors='ignore')
            
            # Remove padding and control characters
            clean = ''.join(c for c in decoded if c.isprintable() and c != ' ')
            return clean.rstrip()
        except:
            return ""
    
    def _init_raw_handler(self):
        """Initialize raw/hex dump handler"""
        self.format_type = "raw"
        self.files = []
        
        # Create a pseudo-file entry showing format info
        file_size = os.path.getsize(self.image_path)
        
        info_entry = FileEntry(
            name="[UNKNOWN FORMAT]",
            ext="",
            attr=0x00,
            cluster=0,
            size=file_size,
            offset=0,
            format_type="raw"
        )
        self.files.append(info_entry)
        
        self.disk_info = {
            'total_size': file_size,
            'used_space': 0,
            'free_space': file_size,
            'system_space': 0,
            'bytes_per_sector': 512,
            'sectors_per_cluster': 1,
            'fat_copies': 0
        }
    
    def list_files(self) -> List[FileEntry]:
        """Return list of files found on the disk"""
        return self.files
    
    def get_disk_info(self) -> Dict[str, int]:
        """Return disk information"""
        return self.disk_info
    
    def extract_files(self, output_dir: str, create_dir: bool = True) -> Dict[str, str]:
        """Extract files from disk image"""
        if create_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        if self.format_type == "fat_hp150" and hasattr(self, '_hp150_handler'):
            return self._hp150_handler.extract_files(output_dir, create_dir)
        
        elif self.format_type == "fat" and hasattr(self, '_fat_handler'):
            return self._fat_handler.extract_files(output_dir, create_dir)
        
        elif self.format_type == "cpm":
            # Use CP/M extractor
            try:
                from .cpm_extractor import CPMExtractor
                with CPMExtractor(self.image_path, verbose=True) as extractor:
                    return extractor.extract_all_files(output_dir)
            except Exception as e:
                print(f"[WARN] CP/M extraction failed: {e}, falling back to raw analysis")
                return self._extract_raw_analysis(output_dir)
        
        else:
            # Raw format - create comprehensive analysis
            return self._extract_raw_analysis(output_dir)
    
    def _extract_raw_analysis(self, output_dir: str) -> Dict[str, str]:
        """Extract comprehensive analysis for unknown formats"""
        try:
            from raw_extractor import RawExtractor
            extractor = RawExtractor(self.image_path, verbose=True)
            
            # Get information files
            info_files = extractor.extract_information(output_dir)
            
            # Also extract sectors as individual files
            sector_files = extractor.extract_sectors_as_files(output_dir, sector_size=512)
            
            # Add sector files to results
            info_files.update(sector_files)
            
            # Create disk image copy for manual analysis
            copy_file = extractor.create_disk_image_copy(output_dir)
            if copy_file:
                base_name = os.path.basename(copy_file)
                info_files[base_name] = copy_file
            
            return info_files
            
        except Exception as e:
            print(f"[ERROR] Raw analysis failed: {e}")
            # Fallback to simple hex dump
            hex_file = os.path.join(output_dir, "disk_dump.hex")
            with open(hex_file, 'w') as f:
                self.file_handle.seek(0)
                data = self.file_handle.read(4096)  # First 4KB
                f.write(data.hex())
            
            return {"disk_dump.hex": hex_file}
    
    def get_format_info(self) -> Dict[str, str]:
        """Return format information"""
        if self.format_type == "fat_hp150" and hasattr(self, '_hp150_handler'):
            return self._hp150_handler.get_format_info()
        elif self.format_type == "fat":
            return {
                'type': 'fat',
                'description': 'FAT Filesystem'
            }
        elif self.format_type == "cpm":
            return {
                'type': 'cp_m',
                'description': 'CP/M Filesystem'
            }
        else:
            return {
                'type': 'raw',
                'description': 'Unknown/Raw Format'
            }
    
    def close(self):
        """Close file handles and cleanup"""
        if self.file_handle:
            self.file_handle.close()
        
        if hasattr(self, '_hp150_handler'):
            self._hp150_handler.close()
        
        if hasattr(self, '_fat_handler'):
            self._fat_handler.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
