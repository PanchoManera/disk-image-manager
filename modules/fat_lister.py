import struct
import os
import tempfile
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class FileEntry:
    name: str
    ext: str
    attr: int
    cluster: int
    size: int
    offset: int

    @property
    def full_name(self) -> str:
        return f"{self.name}.{self.ext}" if self.ext else self.name

    @property
    def is_directory(self) -> bool:
        return bool(self.attr & 0x10)

    @property
    def is_volume(self) -> bool:
        return bool(self.attr & 0x08)

class FATHandler:
    def __init__(self, image_path: str):
        self.image_path = image_path
        self.temp_img_file = None
        self.is_td0 = False
        
        # Check if it's a TD0 file
        if image_path.lower().endswith('.td0'):
            self.is_td0 = True
            self.image_path = self._convert_td0_to_img(image_path)
        
        self.file_handle = open(self.image_path, 'rb')
        self.boot_sector = self.file_handle.read(512)
        self.parse_boot_sector()

        self.fat_start = self.reserved_sectors * self.bytes_per_sector
        self.fat_size = self.fat_sectors * self.bytes_per_sector

        self.root_dir_start = self.fat_start + (self.fat_copies * self.fat_size)
        self.root_dir_size = self.root_entries * 32
        self.data_start = self.root_dir_start + self.root_dir_size

        self.cluster_size = self.sectors_per_cluster * self.bytes_per_sector

        file_size = os.path.getsize(image_path)
        self.max_sectors = file_size // self.bytes_per_sector

        self._files = {}
        self._fat_table = None
        self.volume_label = None  # Store volume label separately

        self._load_fat_table()
        self._load_directory()

    def parse_boot_sector(self):
        # Try HP150 specific offset first (BPB at 0x100, root dir at 0x1100)
        bpb_offset = 0x100
        self.file_handle.seek(bpb_offset)
        bpb_data = self.file_handle.read(512)
        
        # Check if there's a valid BPB at offset 0x100
        try:
            bytes_per_sector_test = struct.unpack('<H', bpb_data[11:13])[0]
            if bytes_per_sector_test in [256, 512, 1024, 2048, 4096]:
                # Use HP150 offset for BPB
                print(f"[INFO] Using HP150-specific BPB offset at 0x{bpb_offset:x}")
                self.boot_sector = bpb_data
                self.bpb_offset = bpb_offset
                # Force root directory at known HP150 location
                self.root_dir_forced_offset = 0x1100
        except:
            # Fall back to standard offset
            self.boot_sector = self.file_handle.read(512)
            self.file_handle.seek(0)
            self.bpb_offset = 0
            self.root_dir_forced_offset = None
        
        try:
            self.bytes_per_sector = struct.unpack('<H', self.boot_sector[11:13])[0]
            if self.bytes_per_sector not in [256, 512, 1024, 2048, 4096]:
                raise ValueError(f"Bytes per sector not supported: {self.bytes_per_sector}")

            self.sectors_per_cluster = self.boot_sector[13]
            self.reserved_sectors = struct.unpack('<H', self.boot_sector[14:16])[0]
            self.fat_copies = self.boot_sector[16]
            self.root_entries = struct.unpack('<H', self.boot_sector[17:19])[0]
            self.fat_sectors = struct.unpack('<H', self.boot_sector[22:24])[0]

            if self.sectors_per_cluster == 0:
                raise ValueError("Sectors per cluster cannot be 0")
            if self.fat_copies == 0:
                raise ValueError("Number of FAT copies cannot be 0")

        except Exception as e:
            print(f"[WARN] Could not parse BPB, trying format detection: {e}")
            # Try to detect format by analyzing the image
            detected_params = self._detect_fat_format()
            if detected_params:
                print(f"[INFO] Detected format: {detected_params['format_name']}")
                self.bytes_per_sector = detected_params['bytes_per_sector']
                self.sectors_per_cluster = detected_params['sectors_per_cluster']
                self.reserved_sectors = detected_params['reserved_sectors']
                self.fat_copies = detected_params['fat_copies']
                self.fat_sectors = detected_params['fat_sectors']
                self.root_entries = detected_params['root_entries']
            else:
                print("[INFO] Using standard FAT12 defaults")
                self.bytes_per_sector = 512
                self.sectors_per_cluster = 1
                self.reserved_sectors = 1
                self.fat_copies = 2
                self.fat_sectors = 9
                self.root_entries = 224

    def _detect_fat_format(self):
        """Intelligently detect FAT format by analyzing structure and patterns"""
        file_size = os.path.getsize(self.image_path)
        
        # Check if image is empty or unformatted
        if self._is_empty_or_unformatted():
            print("[INFO] Image appears to be empty or unformatted")
            return self._guess_format_from_size(file_size)
        
        # First try known formats
        known_format = self._try_known_formats(file_size)
        if known_format:
            return known_format
        
        # Try to infer format by analyzing the image structure
        return self._infer_fat_parameters(file_size)
    
    def _try_known_formats(self, file_size):
        """Try to match against known FAT formats"""
        fat_formats = [
            (368640, 256, 4, 2, 2, 3, 128, "256-byte sector FAT12"),
            (737280, 512, 2, 1, 2, 3, 224, "720K FAT12"), 
            (1474560, 512, 1, 1, 2, 9, 224, "1.44M FAT12"),
            (2949120, 512, 2, 1, 2, 9, 224, "2.88M FAT12"),
            (163840, 512, 1, 1, 2, 2, 64, "160K FAT12"),
            (184320, 512, 1, 1, 2, 2, 64, "180K FAT12"),
            (327680, 512, 2, 1, 2, 2, 112, "320K FAT12"),
            (368640, 512, 2, 1, 2, 2, 112, "360K FAT12"),
        ]
        
        for config in fat_formats:
            if config[0] == file_size:
                return {
                    'format_name': config[7],
                    'bytes_per_sector': config[1],
                    'sectors_per_cluster': config[2],
                    'reserved_sectors': config[3],
                    'fat_copies': config[4],
                    'fat_sectors': config[5],
                    'root_entries': config[6]
                }
        return None
    
    def _infer_fat_parameters(self, file_size):
        """Infer FAT parameters by analyzing the image structure"""
        # Try different sector sizes
        for sector_size in [256, 512, 1024, 2048]:
            total_sectors = file_size // sector_size
            if total_sectors == 0:
                continue
                
            # Try to find valid FAT structure
            params = self._analyze_fat_structure(sector_size, total_sectors)
            if params:
                params['format_name'] = f"Non-standard FAT ({sector_size}b/sector, inferred)"
                return params
        
        # Fallback to heuristic based on file size
        return self._heuristic_fat_params(file_size)
    
    def _analyze_fat_structure(self, sector_size, total_sectors):
        """Analyze potential FAT structure with given sector size"""
        file_size = os.path.getsize(self.image_path)
        
        # Try common configurations
        configs = [
            (1, 1, 2, 3),   # sectors_per_cluster, reserved, fat_copies, fat_sectors
            (2, 1, 2, 3),
            (4, 2, 2, 3),
            (1, 1, 2, 9),
            (2, 1, 2, 9),
            (4, 1, 2, 9),
        ]
        
        for spc, reserved, fat_copies, fat_sectors in configs:
            # Calculate structure
            fat_start = reserved * sector_size
            fat_size = fat_sectors * sector_size
            root_dir_start = fat_start + (fat_copies * fat_size)
            
            # Try different root directory sizes
            for root_entries in [64, 112, 128, 224, 256]:
                root_dir_size = root_entries * 32
                data_start = root_dir_start + root_dir_size
                
                # Check if this configuration makes sense
                if data_start < file_size:
                    cluster_size = spc * sector_size
                    data_clusters = (file_size - data_start) // cluster_size
                    
                    # Validate if this could be a valid FAT
                    if self._validate_fat_config(fat_start, fat_size, data_clusters, sector_size):
                        return {
                            'bytes_per_sector': sector_size,
                            'sectors_per_cluster': spc,
                            'reserved_sectors': reserved,
                            'fat_copies': fat_copies,
                            'fat_sectors': fat_sectors,
                            'root_entries': root_entries
                        }
        return None
    
    def _validate_fat_config(self, fat_start, fat_size, data_clusters, sector_size):
        """Validate if a FAT configuration could be valid"""
        try:
            # Read potential FAT data
            self.file_handle.seek(fat_start)
            fat_data = self.file_handle.read(min(fat_size, 1024))  # Read first 1KB
            
            # Check for reasonable FAT patterns
            if len(fat_data) < 3:
                return False
            
            # Check if image is mostly empty (filled with 0xFF)
            if all(b == 0xFF for b in fat_data[:100]):
                # This might be an empty/unformatted image
                return False
                
            # FAT12 validation - first entry should be media descriptor
            first_entry = fat_data[0]
            if first_entry not in [0xF0, 0xF8, 0xF9, 0xFA, 0xFB, 0xFC, 0xFD, 0xFE, 0xFF, 0x00]:
                return False
                
            # Check if FAT size can accommodate the number of clusters
            if data_clusters > 0:
                fat12_entries = (fat_size * 8) // 12
                if fat12_entries >= data_clusters:
                    return True
                    
            return False
        except:
            return False
    
    def _heuristic_fat_params(self, file_size):
        """Fallback heuristic based on file size"""
        if file_size <= 400000:  # Small images
            return {
                'format_name': 'Small image (heuristic)',
                'bytes_per_sector': 256,
                'sectors_per_cluster': 4,
                'reserved_sectors': 2,
                'fat_copies': 2,
                'fat_sectors': 3,
                'root_entries': 128
            }
        elif file_size <= 800000:  # Medium images
            return {
                'format_name': 'Medium image (heuristic)',
                'bytes_per_sector': 512,
                'sectors_per_cluster': 2,
                'reserved_sectors': 1,
                'fat_copies': 2,
                'fat_sectors': 3,
                'root_entries': 224
            }
        else:  # Large images
            return {
                'format_name': 'Large image (heuristic)',
                'bytes_per_sector': 512,
                'sectors_per_cluster': 1,
                'reserved_sectors': 1,
                'fat_copies': 2,
                'fat_sectors': 9,
                'root_entries': 224
            }
    
    def _is_empty_or_unformatted(self):
        """Check if the image appears to be empty or unformatted"""
        try:
            # Check first 1KB for patterns
            self.file_handle.seek(0)
            first_kb = self.file_handle.read(1024)
            
            # If mostly filled with 0xFF, it's likely empty
            if first_kb.count(b'\xFF') > 800:
                return True
            
            # If mostly zeros, also likely empty
            if first_kb.count(b'\x00') > 800:
                return True
                
            return False
        except:
            return False
    
    def _guess_format_from_size(self, file_size):
        """Guess format based on file size for empty/unformatted images"""
        # Common diskette sizes and their likely formats
        if file_size == 368640:  # 360KB
            return {
                'format_name': '360KB diskette (empty, guessed)',
                'bytes_per_sector': 256,
                'sectors_per_cluster': 4,
                'reserved_sectors': 2,
                'fat_copies': 2,
                'fat_sectors': 3,
                'root_entries': 128
            }
        elif file_size == 737280:  # 720KB
            return {
                'format_name': '720KB diskette (empty, guessed)',
                'bytes_per_sector': 512,
                'sectors_per_cluster': 2,
                'reserved_sectors': 1,
                'fat_copies': 2,
                'fat_sectors': 3,
                'root_entries': 224
            }
        elif file_size == 1474560:  # 1.44MB
            return {
                'format_name': '1.44MB diskette (empty, guessed)',
                'bytes_per_sector': 512,
                'sectors_per_cluster': 1,
                'reserved_sectors': 1,
                'fat_copies': 2,
                'fat_sectors': 9,
                'root_entries': 224
            }
        else:
            # Default guess based on size ranges
            return self._heuristic_fat_params(file_size)

    def _load_fat_table(self):
        self.file_handle.seek(self.fat_start)
        fat_data = self.file_handle.read(self.fat_size)

        total_clusters = (self.max_sectors * self.bytes_per_sector - self.data_start) // self.cluster_size

        if total_clusters < 4087:
            self._fat_table = self._load_fat12(fat_data)
        elif total_clusters < 65527:
            self._fat_table = self._load_fat16(fat_data)
        else:
            self._fat_table = self._load_fat32(fat_data)

    def _load_fat12(self, fat_data: bytes) -> List[int]:
        fat_table = []
        for i in range(0, len(fat_data), 3):
            if i + 2 < len(fat_data):
                val = struct.unpack('<I', fat_data[i:i+3] + b'\x00')[0]
                entry1 = val & 0xFFF
                entry2 = (val >> 12) & 0xFFF
                fat_table.extend([entry1, entry2])
        return fat_table

    def _load_fat16(self, fat_data: bytes) -> List[int]:
        fat_table = []
        for i in range(0, len(fat_data), 2):
            if i + 1 < len(fat_data):
                entry = struct.unpack('<H', fat_data[i:i+2])[0]
                fat_table.append(entry)
        return fat_table

    def _load_fat32(self, fat_data: bytes) -> List[int]:
        fat_table = []
        for i in range(0, len(fat_data), 4):
            if i + 3 < len(fat_data):
                entry = struct.unpack('<L', fat_data[i:i+4])[0]
                fat_table.append(entry & 0x0FFFFFFF)
        return fat_table

    def _find_root_directory(self):
        """Scan image to find the most likely root directory location"""
        file_size = os.path.getsize(self.image_path)
        candidates = []
        
        # First try common HP150 offsets (including 0x700 for Financial Calculator, 0x800 for Touch Games)
        hp150_offsets = [0x700, 0x800, 0x1100, 0x2400, 0x5000, 0x6000, 0x4a00, 0x3000]
        for offset in hp150_offsets:
            if offset < file_size - 256:
                valid_entries = self._count_valid_entries_at_offset(offset)
                if valid_entries >= 3:
                    print(f"[INFO] HP150 directory found at offset 0x{offset:04x} with {valid_entries} valid entries")
                    return offset
        
        # Scan every sector looking for valid directory entries
        for offset in range(0, file_size - 256, 256):  # Scan every 256 bytes
            try:
                self.file_handle.seek(offset)
                sector_data = self.file_handle.read(256)
                
                valid_entries = 0
                total_entries = 0
                
                for i in range(0, 256, 32):
                    if i + 32 > len(sector_data):
                        break
                        
                    entry = sector_data[i:i+32]
                    first_byte = entry[0]
                    
                    if first_byte == 0:  # End of directory
                        break
                    if first_byte == 0xE5:  # Deleted entry
                        total_entries += 1
                        continue
                    if first_byte < 0x20:  # Invalid
                        continue
                        
                    # Check if it looks like a valid filename
                    name = entry[:8]
                    ext = entry[8:11]
                    attr = entry[11]
                    
                    try:
                        name_str = name.decode('ascii', errors='ignore').strip()
                        ext_str = ext.decode('ascii', errors='ignore').strip()
                        
                        # Valid if name has printable characters and reasonable attributes
                        # Be somewhat flexible with HP150 but still validate
                        if (len(name_str.strip()) >= 2 and 
                            any(c.isalnum() for c in name_str) and  # Has some alphanumeric
                            attr < 0x80):  # Reasonable attribute byte
                            valid_entries += 1
                            
                        total_entries += 1
                        
                    except:
                        continue
                
                # If we found a good ratio of valid entries, this is a candidate
                if valid_entries >= 3 and total_entries > 0:
                    ratio = valid_entries / total_entries
                    if ratio >= 0.5:  # At least 50% valid entries
                        candidates.append((offset, valid_entries, ratio))
            except:
                continue
        
        # Sort candidates by number of valid entries and ratio
        candidates.sort(key=lambda x: (x[1], x[2]), reverse=True)
        
        if candidates:
            best_offset = candidates[0][0]
            print(f"[INFO] Auto-detected root directory at offset 0x{best_offset:04x} with {candidates[0][1]} valid entries")
            return best_offset
        
        return None

    def _count_valid_entries(self, root_data):
        """Count valid directory entries in the given data"""
        valid_count = 0
        for i in range(0, len(root_data), 32):
            if i + 32 > len(root_data):
                break
                
            entry = root_data[i:i+32]
            first_byte = entry[0]
            
            if first_byte == 0:  # End of directory
                break
            if first_byte == 0xE5:  # Deleted entry
                continue
            if first_byte < 0x20:  # Invalid
                continue
                
            # Check if it looks like a valid filename
            name = entry[:8]
            attr = entry[11]
            
            try:
                name_str = name.decode('ascii', errors='ignore').strip()
                
                # Valid if name has printable characters and reasonable attributes
                # Be somewhat flexible with HP150 but still validate
                if (len(name_str.strip()) >= 2 and 
                    any(c.isalnum() for c in name_str) and  # Has some alphanumeric
                    attr < 0x80):  # Reasonable attribute byte
                    valid_count += 1
                    
            except:
                continue
                
        return valid_count
    
    def _count_valid_entries_at_offset(self, offset):
        """Count valid directory entries at a specific offset"""
        try:
            self.file_handle.seek(offset)
            dir_data = self.file_handle.read(512)
            return self._count_valid_entries(dir_data)
        except:
            return 0

    def _parse_nonstandard_entry(self, entry_data):
        """Try to parse non-standard directory entry formats generically"""
        try:
            # Extract basic name (works for most formats)
            name = entry_data[0:8].decode('ascii', errors='ignore').rstrip()
            
            # For non-standard formats, try to find reasonable values
            # Look for potential cluster values (small positive integers)
            potential_clusters = []
            for offset in range(12, 30, 2):
                if offset + 2 <= 32:
                    val = struct.unpack('<H', entry_data[offset:offset+2])[0]
                    if 2 <= val <= 1000:  # Reasonable cluster range
                        potential_clusters.append((offset, val))
            
            # Look for potential size values
            potential_sizes = []
            for offset in range(12, 28, 2):
                if offset + 2 <= 32:
                    val16 = struct.unpack('<H', entry_data[offset:offset+2])[0]
                    if 0 < val16 < 65536:  # Reasonable size range
                        potential_sizes.append((offset, val16))
            
            for offset in range(12, 26, 4):
                if offset + 4 <= 32:
                    val32 = struct.unpack('<L', entry_data[offset:offset+4])[0]
                    if 0 < val32 < 100000:  # Reasonable size range for HP150 floppies
                        potential_sizes.append((offset, val32))
            
            # Try to extract extension from the name area (some formats integrate it)
            ext = ""
            if len(name) > 8:
                # Extension might be integrated
                parts = name.split('.')
                if len(parts) == 2:
                    name = parts[0][:8]
                    ext = parts[1][:3]
            else:
                # Try traditional extension area but be flexible
                ext_area = entry_data[8:11]
                try:
                    ext_candidate = ext_area.decode('ascii', errors='ignore').rstrip()
                    if ext_candidate and all(c.isalnum() or c in '._' for c in ext_candidate):
                        ext = ext_candidate
                except:
                    pass
            
            # Use reasonable defaults or best guesses
            cluster = potential_clusters[0][1] if potential_clusters else 0
            size = potential_sizes[0][1] if potential_sizes else 1024  # Default reasonable size
            
            # For attributes, use a reasonable default instead of 0x32
            attr = 0x20  # Archive bit only, treat as regular file
            
            return name, ext, attr, cluster, size
            
        except Exception as e:
            print(f"[DEBUG] Failed to parse non-standard entry: {e}")
            return None

    def _decode_filename(self, name_bytes):
        """Safely decode filename bytes, handling non-printable characters"""
        try:
            # First try to decode as ASCII
            decoded = name_bytes.decode('ascii', errors='replace')
            
            # Filter out non-printable characters
            clean_name = ''
            for char in decoded:
                if char.isprintable() and ord(char) < 128 and char not in '\x00\xFF':
                    clean_name += char
                elif char == '\x00':  # Null terminator
                    break
                elif char == '\xFF':  # Padding
                    break
                else:
                    # Skip invalid characters instead of replacing with ?
                    continue
            
            return clean_name.rstrip()
            
        except Exception:
            # Fallback: create a hex representation for completely invalid data
            return f"INVALID_{name_bytes.hex()[:8].upper()}"

    def _load_directory(self):
        # First try forced offset for HP150
        root_offset = None
        if hasattr(self, 'root_dir_forced_offset') and self.root_dir_forced_offset:
            print(f"[INFO] Trying HP150 forced root directory offset at 0x{self.root_dir_forced_offset:x}")
            root_offset = self.root_dir_forced_offset
        
        # If no forced offset or forced offset fails, try calculated offset
        if not root_offset:
            root_offset = self.root_dir_start
            print(f"[INFO] Using calculated root directory offset at 0x{root_offset:x}")
        
        # Try the offset
        self.file_handle.seek(root_offset)
        root_data = self.file_handle.read(self.root_dir_size)
        
        # Check if this location has valid directory entries
        valid_entries = self._count_valid_entries(root_data)
        
        if valid_entries < 2:  # If less than 2 valid entries, try auto-detection
            print(f"[WARN] Only {valid_entries} valid entries found at calculated offset, trying auto-detection...")
            auto_offset = self._find_root_directory()
            if auto_offset is not None:
                root_offset = auto_offset
                self.file_handle.seek(root_offset)
                root_data = self.file_handle.read(self.root_dir_size)
            else:
                print(f"[WARN] Auto-detection failed, using calculated offset anyway")
        
        self.root_dir_actual_offset = root_offset

        self._files = {}
        for i in range(0, len(root_data), 32):
            entry_data = root_data[i:i+32]
            if len(entry_data) < 32:
                break

            first_byte = entry_data[0]
            if first_byte == 0x00:
                break
            if first_byte == 0xE5:
                continue
            if first_byte == 0x2E:
                continue

            try:
                # Check for VFAT long filename entries first
                attr = entry_data[11]
                if attr == 0x0F:  # VFAT long filename entry
                    print(f"[DEBUG] Skipping VFAT long filename entry at offset {self.root_dir_actual_offset + i}")
                    continue
                
                # Try standard FAT interpretation
                name_bytes = entry_data[0:8]
                ext_bytes = entry_data[8:11]
                
                # Clean filename decoding
                name = self._decode_filename(name_bytes)
                ext = self._decode_filename(ext_bytes)
                
                cluster = struct.unpack('<H', entry_data[26:28])[0]
                size = struct.unpack('<L', entry_data[28:32])[0]
                
                # Validate size - reject extremely large files (likely corruption)
                # For HP150 disks, use a much smaller threshold since floppies are limited
                max_reasonable_size = 2 * 1024 * 1024  # 2MB for floppy disks
                if size > max_reasonable_size:
                    print(f"[WARN] File '{name}' has unreasonable size: {size:,} bytes, trying alternative parsing")
                    # Try alternative parsing for HP150 specific format
                    alt_result = self._parse_nonstandard_entry(entry_data)
                    if alt_result:
                        name, ext, attr, cluster, size = alt_result
                        print(f"[INFO] Alternative parsing: '{name}' -> size={size}")
                        # Re-validate size after alternative parsing
                        if size > max_reasonable_size:
                            print(f"[WARN] Still unreasonable size after alt parsing: {size:,} bytes, skipping")
                            continue
                    else:
                        continue
                
                # If standard interpretation gives suspicious results, try alternative parsing
                if cluster == 384 and size == 0 and attr == 0x32:
                    # This looks like a non-standard format, try alternative interpretations
                    alt_result = self._parse_nonstandard_entry(entry_data)
                    if alt_result:
                        name, ext, attr, cluster, size = alt_result
                        # Re-validate size after alternative parsing
                        if size > max_reasonable_size:
                            print(f"[WARN] Skipping file '{name}' with unreasonable size after alt parsing: {size:,} bytes")
                            continue

                if name and not name.startswith('\x00') and len(name.strip()) > 0:
                    # Check if this is a volume label
                    if attr & 0x08:  # Volume label attribute
                        volume_name = f"{name}.{ext}" if ext else name
                        self.volume_label = volume_name.strip()
                        print(f"[INFO] Found volume label: '{self.volume_label}'")
                        continue  # Don't add volume labels to file list
                    
                    entry = FileEntry(
                        name=name,
                        ext=ext,
                        attr=attr,
                        cluster=cluster,
                        size=size,
                        offset=self.root_dir_start + i
                    )
                    self._files[entry.full_name] = entry
            except:
                continue

    def list_files(self) -> List[FileEntry]:
        return list(self._files.values())

    def list_visible_files(self) -> List[FileEntry]:
        visible_files = []
        for file in self._files.values():
            if file.attr & 0x08:  # Volume label
                continue
            elif file.attr & 0x02:  # Hidden
                continue
            else:
                visible_files.append(file)
        return visible_files

    def get_disk_info(self) -> Dict[str, int]:
        total_size = self.max_sectors * self.bytes_per_sector
        used_space = 0
        for file_entry in self._files.values():
            if not file_entry.is_volume and file_entry.cluster > 0 and file_entry.size > 0:
                clusters_needed = (file_entry.size + self.cluster_size - 1) // self.cluster_size
                used_space += clusters_needed * self.cluster_size

        system_space = (self.fat_copies * self.fat_size) + self.root_dir_size + (self.reserved_sectors * self.bytes_per_sector)
        used_space += system_space

        free_space = max(0, total_size - used_space)

        return {
            'total_size': total_size,
            'used_space': used_space,
            'free_space': free_space,
            'system_space': system_space,
            'bytes_per_sector': self.bytes_per_sector,
            'sectors_per_cluster': self.sectors_per_cluster,
            'fat_copies': self.fat_copies,
            'volume_label': self.volume_label
        }

    def extract_files(self, output_dir: str, create_dir: bool = True) -> Dict[str, str]:
        """Extract all files from the FAT image to the specified directory.
        
        Args:
            output_dir: Directory where files will be extracted
            create_dir: Whether to create the output directory if it doesn't exist
            
        Returns:
            Dictionary mapping original filenames to extracted file paths
        """
        if create_dir:
            os.makedirs(output_dir, exist_ok=True)
        elif not os.path.exists(output_dir):
            raise ValueError(f"Output directory '{output_dir}' does not exist")
            
        extracted_files = {}
        
        for file_entry in self._files.values():
            # Skip directories and volume labels
            if file_entry.is_directory or file_entry.is_volume:
                continue
                
            # Skip files with no cluster or size
            if file_entry.cluster == 0 or file_entry.size == 0:
                continue
                
            try:
                # Extract the file content
                file_content = self._read_file_content(file_entry)
                
                # Create output file path
                output_file = os.path.join(output_dir, file_entry.full_name)
                
                # Write the file
                with open(output_file, 'wb') as f:
                    f.write(file_content)
                    
                extracted_files[file_entry.full_name] = output_file
                print(f"Extracted: {file_entry.full_name} ({file_entry.size} bytes)")
                
            except Exception as e:
                print(f"Error extracting {file_entry.full_name}: {e}")
                
        return extracted_files
    
    def _read_file_content(self, file_entry: FileEntry) -> bytes:
        """Read the content of a file from the FAT image."""
        if file_entry.cluster == 0 or file_entry.size == 0:
            return b''
            
        content = b''
        current_cluster = file_entry.cluster
        bytes_remaining = file_entry.size
        
        while current_cluster and bytes_remaining > 0:
            # Calculate the sector offset for this cluster
            cluster_offset = self.data_start + ((current_cluster - 2) * self.cluster_size)
            
            # Read the cluster data
            self.file_handle.seek(cluster_offset)
            cluster_data = self.file_handle.read(self.cluster_size)
            
            # Only take what we need for this file
            bytes_to_take = min(len(cluster_data), bytes_remaining)
            content += cluster_data[:bytes_to_take]
            bytes_remaining -= bytes_to_take
            
            # Get the next cluster from the FAT
            if current_cluster < len(self._fat_table):
                next_cluster = self._fat_table[current_cluster]
                
                # Check for end of chain markers
                if next_cluster >= 0xFF8:  # FAT12 end of chain
                    break
                elif next_cluster >= 0xFFF8:  # FAT16 end of chain
                    break
                elif next_cluster >= 0x0FFFFFF8:  # FAT32 end of chain
                    break
                    
                current_cluster = next_cluster
            else:
                break
                
        return content

    def _convert_td0_to_img(self, td0_path: str) -> str:
        """Convert TD0 file to IMG using the td0_converter_lib."""
        try:
            # Import the converter library
            from .td0_converter_lib import FixedTD0Converter, ConversionOptions
            
            # Create temporary file for the converted image
            temp_fd, temp_path = tempfile.mkstemp(suffix='.img')
            os.close(temp_fd)  # Close the file descriptor, we'll write to it later
            self.temp_img_file = temp_path
            
            # Set up conversion options with warn_only (equivalent to -w)
            options = ConversionOptions(
                warn_only=True,
                force_hp150=True,
                fix_boot_sector=True,
                verbose=False
            )
            
            # Convert TD0 to IMG
            converter = FixedTD0Converter(options)
            result = converter.convert(td0_path, temp_path)
            
            if result.success:
                print(f"Successfully converted TD0 to temporary IMG: {temp_path}")
                return temp_path
            else:
                raise Exception(f"TD0 conversion failed: {result.error_message}")
                
        except ImportError:
            raise Exception("TD0 converter library not available. Please ensure td0_converter_lib_enhanced.py is in the same directory.")
        except Exception as e:
            # Clean up temp file if conversion failed
            if self.temp_img_file and os.path.exists(self.temp_img_file):
                os.unlink(self.temp_img_file)
                self.temp_img_file = None
            raise Exception(f"Failed to convert TD0 file: {e}")
    
    def close(self):
        if self.file_handle:
            self.file_handle.close()
        
        # Clean up temporary file if it was created
        if self.temp_img_file and os.path.exists(self.temp_img_file):
            os.unlink(self.temp_img_file)
            self.temp_img_file = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

if __name__ == "__main__":
    image_path = "example.img"
    with FATHandler(image_path) as fat_handler:
        print("Listing files:")
        for file in fat_handler.list_files():
            print(f"{file.full_name}: {file.size} bytes")

        info = fat_handler.get_disk_info()
        print(f"\nDisk info: {info}")
