#!/usr/bin/env python3
"""
HP150FAT Handler - Specialized FAT handler for HP150 disk images
Compatible with the modular disk handler architecture
"""

import struct
import os
import tempfile
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Import the common FileEntry from the existing modules
try:
    from .generic_disk_handler import FileEntry
except ImportError:
    # Fallback definition for standalone use
    @dataclass
    class FileEntry:
        name: str
        ext: str
        attr: int
        cluster: int
        size: int
        offset: int
        format_type: str = "hp150"

        @property
        def full_name(self) -> str:
            return f"{self.name}.{self.ext}" if self.ext else self.name

        @property
        def is_directory(self) -> bool:
            return bool(self.attr & 0x10)

        @property
        def is_volume(self) -> bool:
            return bool(self.attr & 0x08)

class HP150FATHandler:
    """Specialized FAT handler for HP150 disk images with non-standard sector sizes and offsets"""
    
    def __init__(self, image_path: str, root_dir_offset: Optional[int] = None):
        self.image_path = image_path
        self.file_handle = open(image_path, 'rb')
        self.volume_label = None
        self._files = {}
        self._fat_table = None
        
        # HP150 specific parameters
        self.bytes_per_sector = 256  # HP150 uses 256-byte sectors
        self.sectors_per_cluster = 4
        self.fat_copies = 2
        
        # Auto-detect or use provided root directory offset
        if root_dir_offset:
            self.root_dir_offset = root_dir_offset
        else:
            self.root_dir_offset = self._auto_detect_root_directory()
        
        if not self.root_dir_offset:
            raise ValueError("Could not locate HP150 root directory")
        
        # Calculate HP150 specific offsets
        self._calculate_hp150_layout()
        
        # Load FAT and directory
        self._load_fat_table()
        self._load_directory()
    
    def _auto_detect_root_directory(self) -> Optional[int]:
        """Auto-detect HP150 root directory location"""
        print("[INFO] Auto-detecting HP150 root directory...")
        
        # HP150 common directory offsets (prioritized)
        hp150_offsets = [
            0x700,   # Financial Calculator and VisiCalc
            0x800,   # Touch Games and other software
            0x1100,  # Standard HP150 location
            0x2400,  # Alternative location
            0x5000,  # Some HP150 disks
            0x6000,  # Another alternative
        ]
        
        best_offset = None
        max_entries = 0
        
        for offset in hp150_offsets:
            if offset >= os.path.getsize(self.image_path):
                continue
                
            try:
                entries = self._count_valid_entries_at_offset(offset)
                if entries > max_entries:
                    max_entries = entries
                    best_offset = offset
                    
                print(f"[DEBUG] Offset 0x{offset:x}: {entries} valid entries")
                
            except Exception as e:
                print(f"[DEBUG] Error checking offset 0x{offset:x}: {e}")
                continue
        
        if best_offset and max_entries >= 3:
            print(f"[INFO] Found HP150 directory at 0x{best_offset:x} with {max_entries} entries")
            return best_offset
        
        print("[WARN] Could not auto-detect HP150 directory")
        return None
    
    def _calculate_hp150_layout(self):
        """Calculate HP150 specific disk layout"""
        # FAT starts at beginning of disk
        self.fat_start = 0x200  # After boot sector
        self.fat_size = 0x300   # 3 sectors * 256 bytes
        
        # Data area calculation for HP150
        # Cluster 2 typically starts at 0x1000 for Financial Calculator
        # Cluster 2 starts at 0x1800 for VisiCalc  
        if self.root_dir_offset == 0x700:
            # Financial Calculator pattern: cluster 2 at 0x1000, but directory at 0x700
            self.data_start = 0x1000
        else:
            # Standard pattern: data starts after directory
            self.data_start = 0x1800
            
        self.cluster_size = self.sectors_per_cluster * self.bytes_per_sector
        
        print(f"[INFO] HP150 Layout: root_dir=0x{self.root_dir_offset:x}, data_start=0x{self.data_start:x}, cluster_size={self.cluster_size}")
    
    def _count_valid_entries_at_offset(self, offset: int) -> int:
        """Count valid directory entries at given offset"""
        try:
            self.file_handle.seek(offset)
            dir_data = self.file_handle.read(512)  # Read directory data
            
            valid_count = 0
            for i in range(0, len(dir_data), 32):
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
                    # Try to decode filename
                    name = entry[0:8].decode('ascii', errors='ignore').strip()
                    attr = entry[11]
                    
                    # Check if this looks like a valid entry
                    if (name and 
                        len(name) >= 1 and
                        any(c.isalnum() or c in '._-+$' for c in name) and
                        attr < 0x80):
                        valid_count += 1
                        
                except:
                    continue
            
            return valid_count
        except:
            return 0
    
    def _load_fat_table(self):
        """Load HP150 FAT12 table"""
        self.file_handle.seek(self.fat_start)
        fat_data = self.file_handle.read(self.fat_size)
        
        # Parse FAT12 table
        self._fat_table = []
        for i in range(0, len(fat_data) - 2, 3):  # Ensure we have at least 3 bytes
            # Read 3 bytes and extract 2 FAT12 entries
            three_bytes = fat_data[i:i+3]
            if len(three_bytes) >= 3:
                # Unpack as 3 bytes + 1 padding byte for uint32
                val = struct.unpack('<I', three_bytes + b'\x00')[0]
                entry1 = val & 0xFFF
                entry2 = (val >> 12) & 0xFFF
                self._fat_table.extend([entry1, entry2])
        
        print(f"[INFO] Loaded FAT12 table with {len(self._fat_table)} entries")
    
    def _load_directory(self):
        """Load HP150 directory entries"""
        self.file_handle.seek(self.root_dir_offset)
        
        # Read several sectors of directory data to ensure we get all entries
        dir_size = 16 * 32  # 16 entries max
        root_data = self.file_handle.read(dir_size)
        
        self._files = {}
        entry_count = 0
        
        for i in range(0, len(root_data), 32):
            if i + 32 > len(root_data):
                break
                
            entry_data = root_data[i:i+32]
            first_byte = entry_data[0]
            
            # End of directory
            if first_byte == 0x00:
                break
                
            # Deleted entry
            if first_byte == 0xE5:
                continue
                
            # Directory entry (skip . and ..)
            if first_byte == 0x2E:
                continue
            
            # Invalid entry
            if first_byte < 0x20:
                continue
            
            try:
                # Parse entry - ensure we have enough data
                if len(entry_data) < 32:
                    continue
                    
                name_bytes = entry_data[0:8]
                ext_bytes = entry_data[8:11]
                attr = entry_data[11]
                
                # Safely extract cluster and size
                if len(entry_data) >= 28:
                    cluster = struct.unpack('<H', entry_data[26:28])[0]
                else:
                    cluster = 0
                    
                if len(entry_data) >= 32:
                    size = struct.unpack('<L', entry_data[28:32])[0]
                else:
                    size = 0
                
                # Clean filename
                name = self._clean_filename(name_bytes)
                ext = self._clean_filename(ext_bytes)
                
                if not name:
                    continue
                
                # Check for volume label
                if attr & 0x08:  # Volume label
                    volume_name = f"{name}.{ext}" if ext else name
                    self.volume_label = volume_name.strip()
                    print(f"[INFO] Found volume label: '{self.volume_label}'")
                    continue
                
                # Skip hidden/system files that are clearly HP150 internal
                if attr & 0x02 and name in ['HPSYS', 'HP150', 'SYSTEM']:
                    continue
                
                # Validate file size (HP150 floppies are small)
                if size > 2 * 1024 * 1024:  # 2MB max
                    print(f"[WARN] Skipping {name}.{ext} - size too large: {size}")
                    continue
                
                # Create file entry
                file_entry = FileEntry(
                    name=name,
                    ext=ext,
                    attr=attr,
                    cluster=cluster,
                    size=size,
                    offset=self.root_dir_offset + i,
                    format_type="hp150"
                )
                
                self._files[file_entry.full_name] = file_entry
                entry_count += 1
                
                print(f"[DEBUG] Entry {entry_count}: {file_entry.full_name} ({file_entry.size} bytes, cluster {file_entry.cluster})")
                
            except Exception as e:
                print(f"[WARN] Error parsing entry at offset {i}: {e}")
                continue
        
        print(f"[INFO] Loaded {len(self._files)} files from HP150 directory")
    
    def _clean_filename(self, name_bytes: bytes) -> str:
        """Clean HP150 filename bytes"""
        try:
            # Decode and clean
            decoded = name_bytes.decode('ascii', errors='ignore')
            
            # Remove padding and invalid characters
            clean = ''
            for char in decoded:
                if char.isprintable() and char not in '\x00\xFF ':
                    clean += char
                elif char == ' ':
                    break  # Space padding
                elif char == '\x00':
                    break  # Null terminator
                    
            return clean.rstrip()
        except:
            return ""
    
    def list_files(self) -> List[FileEntry]:
        """Return list of files found on the disk"""
        return list(self._files.values())
    
    def list_visible_files(self) -> List[FileEntry]:
        """Return list of visible files (excluding hidden/system)"""
        visible = []
        for file_entry in self._files.values():
            # Skip volume labels
            if file_entry.is_volume:
                continue
            # Include hidden files unless they're clearly system files
            if file_entry.attr & 0x02 and file_entry.name.upper() in ['HPSYS', 'HP150SYS']:
                continue
            visible.append(file_entry)
        return visible
    
    def get_disk_info(self) -> Dict:
        """Return disk information"""
        total_size = self.file_size = os.path.getsize(self.image_path)
        
        # Calculate used space
        used_space = 0
        for file_entry in self._files.values():
            if not file_entry.is_volume and file_entry.cluster > 0:
                # Calculate clusters needed
                clusters_needed = (file_entry.size + self.cluster_size - 1) // self.cluster_size
                used_space += clusters_needed * self.cluster_size
        
        # Add system space (FAT + directory)
        system_space = self.fat_size * self.fat_copies + 512  # FAT + directory space
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
            'volume_label': self.volume_label,
            'format_type': 'HP150 FAT',
            'root_dir_offset': f"0x{self.root_dir_offset:x}",
            'data_start': f"0x{self.data_start:x}"
        }
    
    def get_format_info(self) -> Dict[str, str]:
        """Return format information"""
        return {
            'type': 'fat_hp150',
            'description': 'HP150 FAT Filesystem',
            'bytes_per_sector': str(self.bytes_per_sector),
            'root_offset': f"0x{self.root_dir_offset:x}"
        }
    
    def extract_files(self, output_dir: str, create_dir: bool = True) -> Dict[str, str]:
        """Extract all files from the HP150 image"""
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
                # Extract file content
                file_content = self._read_file_content(file_entry)
                
                # Create output file
                output_file = os.path.join(output_dir, file_entry.full_name)
                
                with open(output_file, 'wb') as f:
                    f.write(file_content)
                
                extracted_files[file_entry.full_name] = output_file
                print(f"[INFO] Extracted: {file_entry.full_name} ({len(file_content)} bytes)")
                
            except Exception as e:
                print(f"[WARN] Error extracting {file_entry.full_name}: {e}")
        
        return extracted_files
    
    def _read_file_content(self, file_entry: FileEntry) -> bytes:
        """Read file content following HP150 FAT chain"""
        if file_entry.cluster == 0 or file_entry.size == 0:
            return b''
        
        content = b''
        current_cluster = file_entry.cluster
        bytes_remaining = file_entry.size
        
        visited_clusters = set()  # Prevent infinite loops
        
        while current_cluster >= 2 and bytes_remaining > 0:
            # Prevent infinite loops
            if current_cluster in visited_clusters:
                print(f"[WARN] Detected loop in cluster chain for {file_entry.full_name}")
                break
            visited_clusters.add(current_cluster)
            
            # Calculate cluster position in HP150 layout
            cluster_offset = self.data_start + ((current_cluster - 2) * self.cluster_size)
            
            # Validate cluster offset
            if cluster_offset >= os.path.getsize(self.image_path):
                print(f"[WARN] Cluster {current_cluster} offset 0x{cluster_offset:x} beyond file")
                break
            
            # Read cluster data
            self.file_handle.seek(cluster_offset)
            cluster_data = self.file_handle.read(self.cluster_size)
            
            # Take only what we need
            bytes_to_take = min(len(cluster_data), bytes_remaining)
            content += cluster_data[:bytes_to_take]
            bytes_remaining -= bytes_to_take
            
            # Get next cluster from FAT
            if current_cluster < len(self._fat_table):
                next_cluster = self._fat_table[current_cluster]
                
                # Check for end-of-chain markers (FAT12)
                if next_cluster >= 0xFF8:  # End of chain
                    break
                elif next_cluster == 0:  # Free cluster (shouldn't happen in chain)
                    break
                elif next_cluster == 1:  # Reserved (shouldn't happen in chain)
                    break
                
                current_cluster = next_cluster
            else:
                break
        
        return content
    
    def _read_file_clusters(self, start_cluster: int) -> List[int]:
        """Read cluster chain starting from given cluster"""
        if not self._fat_table or start_cluster < 2:
            return []
        
        clusters = []
        current = start_cluster
        visited = set()
        
        while current >= 2 and current < len(self._fat_table):
            if current in visited:  # Loop detection
                break
            visited.add(current)
            clusters.append(current)
            
            next_cluster = self._fat_table[current]
            
            # Check for end-of-chain
            if next_cluster >= 0xFF8:  # FAT12 end-of-chain
                break
            elif next_cluster == 0:  # Free cluster
                break
            elif next_cluster == 1:  # Reserved
                break
                
            current = next_cluster
            
            # Safety limit
            if len(clusters) > 1000:
                print(f"[WARN] Cluster chain too long, stopping at {len(clusters)} clusters")
                break
        
        return clusters
    
    def read_file(self, filename: str) -> Optional[bytes]:
        """Read specific file by name"""
        if filename not in self._files:
            return None
        
        file_entry = self._files[filename]
        return self._read_file_content(file_entry)
    
    def write_file(self, filename: str, content: bytes) -> bool:
        """Write file to image (for future implementation)"""
        # TODO: Implement file writing
        raise NotImplementedError("File writing not yet implemented")
    
    def delete_file(self, filename: str) -> bool:
        """Delete file from image (for future implementation)"""
        # TODO: Implement file deletion
        raise NotImplementedError("File deletion not yet implemented")
    
    def close(self):
        """Close file handle"""
        if self.file_handle:
            self.file_handle.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# Compatibility function for existing code
def create_hp150_handler(image_path: str, **kwargs) -> HP150FATHandler:
    """Factory function to create HP150 handler"""
    return HP150FATHandler(image_path, **kwargs)
