#!/usr/bin/env python3
"""
Enhanced Format Detector - Improved disk format detection including HP150 specific formats
"""

import struct
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class DiskFormat(Enum):
    """Supported disk formats"""
    FAT_STANDARD = "fat_standard"
    FAT_HP150 = "fat_hp150" 
    CPM = "cpm"
    RAW = "raw"

@dataclass 
class FormatDetectionResult:
    """Result of format detection"""
    format_type: DiskFormat
    confidence: float  # 0.0 to 1.0
    handler_class: str
    parameters: Dict
    notes: List[str]

class EnhancedFormatDetector:
    """Enhanced format detector with HP150 specific support"""
    
    def __init__(self, image_path: str):
        self.image_path = image_path
        self.file_size = os.path.getsize(image_path)
        
    def detect_format(self) -> FormatDetectionResult:
        """Detect the most likely format for this disk image"""
        
        # Try detection methods in order of specificity
        detectors = [
            self._detect_hp150_fat,
            self._detect_standard_fat,
            self._detect_cpm,
            self._detect_raw
        ]
        
        results = []
        for detector in detectors:
            result = detector()
            if result and result.confidence > 0.0:
                results.append(result)
        
        if not results:
            # Fallback to raw
            return FormatDetectionResult(
                format_type=DiskFormat.RAW,
                confidence=0.1,
                handler_class="RawHandler", 
                parameters={},
                notes=["No recognizable format detected"]
            )
        
        # Return highest confidence result
        return max(results, key=lambda x: x.confidence)
    
    def _detect_hp150_fat(self) -> Optional[FormatDetectionResult]:
        """Detect HP150 specific FAT format"""
        notes = []
        confidence = 0.0
        
        # HP150 specific indicators
        hp150_indicators = 0
        
        # 1. Check file size - HP150 disks are typically smaller
        if self.file_size <= 400000:  # Typical HP150 floppy size
            hp150_indicators += 1
            notes.append(f"File size ({self.file_size} bytes) matches HP150 floppy")
        
        # 2. Check for 256-byte sectors
        with open(self.image_path, 'rb') as f:
            # Try to parse boot sector at offset 0 for sector size
            f.seek(0)
            boot_data = f.read(512)
            
            try:
                if len(boot_data) >= 512:
                    bytes_per_sector = struct.unpack('<H', boot_data[11:13])[0]
                    if bytes_per_sector == 256:
                        hp150_indicators += 2
                        notes.append("256-byte sectors detected (HP150 specific)")
                    elif bytes_per_sector in [512, 1024]:
                        hp150_indicators += 0.5
                        notes.append(f"{bytes_per_sector}-byte sectors detected")
            except:
                pass
            
            # 3. Check for HP150 directory structure at known offsets
            hp150_offsets = [0x700, 0x800, 0x1100, 0x2400, 0x5000]
            best_offset = None
            max_valid_entries = 0
            
            for offset in hp150_offsets:
                if offset >= self.file_size:
                    continue
                    
                valid_entries = self._count_fat_entries_at_offset(f, offset)
                if valid_entries > max_valid_entries:
                    max_valid_entries = valid_entries
                    best_offset = offset
                    
            if max_valid_entries >= 3:
                hp150_indicators += 3
                notes.append(f"HP150 directory found at 0x{best_offset:x} with {max_valid_entries} entries")
                
                # 4. Check for HP150 specific file patterns
                hp150_file_patterns = self._check_hp150_file_patterns(f, best_offset)
                if hp150_file_patterns > 0:
                    hp150_indicators += hp150_file_patterns
                    notes.append(f"Found {hp150_file_patterns} HP150-style files")
        
        # Calculate confidence
        max_possible_indicators = 8  # Maximum score possible
        confidence = min(hp150_indicators / max_possible_indicators, 1.0)
        
        if confidence >= 0.3:  # Threshold for HP150 detection
            return FormatDetectionResult(
                format_type=DiskFormat.FAT_HP150,
                confidence=confidence,
                handler_class="HP150FATHandler",
                parameters={
                    'root_dir_offset': best_offset,
                    'bytes_per_sector': 256 if hp150_indicators >= 2 else 512
                },
                notes=notes
            )
        
        return None
    
    def _detect_standard_fat(self) -> Optional[FormatDetectionResult]:
        """Detect standard FAT format with intelligent validation"""
        notes = []
        confidence = 0.0
        
        with open(self.image_path, 'rb') as f:
            # Check boot signature (optional - many disk images don't have it)
            f.seek(510)
            boot_sig = f.read(2)
            if boot_sig == b'\x55\xAA':
                confidence += 0.15
                notes.append("Valid boot signature found")
            elif boot_sig == b'\x00\x00':
                notes.append("No boot signature (common in disk images)")
            
            # Check BPB structure (most important indicator)
            f.seek(0)
            boot_sector = f.read(512)
            
            try:
                bytes_per_sector = struct.unpack('<H', boot_sector[11:13])[0]
                sectors_per_cluster = boot_sector[13]
                reserved_sectors = struct.unpack('<H', boot_sector[14:16])[0]
                fat_copies = boot_sector[16]
                root_entries = struct.unpack('<H', boot_sector[17:19])[0]
                total_sectors = struct.unpack('<H', boot_sector[19:21])[0]
                fat_sectors = struct.unpack('<H', boot_sector[22:24])[0]
                
                # Validate BPB fields
                bpb_score = 0
                if bytes_per_sector in [256, 512, 1024, 2048]:
                    bpb_score += 1
                if sectors_per_cluster in [1, 2, 4, 8, 16, 32, 64]:
                    bpb_score += 1
                if 1 <= reserved_sectors <= 32:
                    bpb_score += 1
                if 1 <= fat_copies <= 3:
                    bpb_score += 1
                if 0 < root_entries <= 512:
                    bpb_score += 1
                if 0 < fat_sectors <= 20:
                    bpb_score += 1
                
                if bpb_score >= 5:  # Strong BPB indicator
                    confidence += 0.4
                    notes.append(f"Strong BPB structure: {bpb_score}/6 valid fields")
                    
                    # INTELLIGENT FAT VALIDATION
                    # Calculate FAT layout
                    fat_start = reserved_sectors * bytes_per_sector
                    fat_size = fat_sectors * bytes_per_sector
                    root_dir_start = fat_start + (fat_copies * fat_size)
                    
                    # 1. Validate FAT table structure
                    fat_confidence = self._validate_fat_table(f, fat_start, fat_size)
                    confidence += fat_confidence * 0.25
                    if fat_confidence > 0.5:
                        notes.append("Valid FAT table structure detected")
                    
                    # 2. Validate root directory structure
                    if root_dir_start < self.file_size:
                        f.seek(root_dir_start)
                        root_data = f.read(min(root_entries * 32, self.file_size - root_dir_start))
                        
                        valid_entries = self._validate_fat_directory(root_data)
                        if valid_entries > 0:
                            confidence += min(valid_entries / 10, 0.2)  # Up to 0.2 bonus
                            notes.append(f"Found {valid_entries} valid FAT directory entries")
                            
                            # 3. Cross-validate cluster chains vs file sizes
                            chain_validation = self._validate_cluster_chains(f, root_data, fat_start, fat_size, root_dir_start)
                            confidence += chain_validation * 0.15
                            if chain_validation > 0.5:
                                notes.append("File cluster chains are consistent")
                elif bpb_score >= 4:
                    notes.append("Good BPB but no valid directory entries")
                    confidence += 0.1  # Still some confidence from BPB
                
                # Check OEM name
                oem_name = boot_sector[3:11].decode('ascii', errors='ignore').strip()
                if oem_name and len(oem_name) >= 3 and oem_name.replace('\x00', '').strip():
                    confidence += 0.05
                    notes.append(f"OEM ID: '{oem_name}'")
                    
            except Exception as e:
                notes.append(f"BPB parsing error: {e}")
        
        # Lower threshold but require some validation
        if confidence >= 0.35:
            return FormatDetectionResult(
                format_type=DiskFormat.FAT_STANDARD,
                confidence=confidence,
                handler_class="StandardFATHandler",
                parameters={},
                notes=notes
            )
        
        return None
    
    def _detect_cpm(self) -> Optional[FormatDetectionResult]:
        """Detect CP/M format"""
        notes = []
        confidence = 0.0
        
        # Check common CP/M disk sizes (remove 368640 - that's standard 360K FAT)
        cmp_sizes = [200704, 400896, 1024000, 204800, 212075, 746496, 102400]
        
        size_match = any(abs(self.file_size - size) < 2048 for size in cmp_sizes)
        if size_match:
            confidence += 0.25  # Reduced from 0.3
            notes.append("File size matches CP/M format")
            
            # Look for CP/M directory patterns
            with open(self.image_path, 'rb') as f:
                offsets = [0x3000, 0x3C00, 0x1400, 0x2800, 0x1100, 0x2000, 0x2400]
                
                for offset in offsets:
                    if self._check_cpm_directory_at_offset(f, offset):
                        confidence += 0.4  # Reduced from 0.5
                        notes.append(f"CP/M directory found at 0x{offset:x}")
                        break
        
        # For 360K images (368640 bytes), be extra cautious - could be FAT
        if self.file_size == 368640:
            confidence *= 0.7  # Reduce confidence for potential FAT images
            notes.append("360K size - could be FAT format")
        
        if confidence >= 0.4:
            return FormatDetectionResult(
                format_type=DiskFormat.CPM,
                confidence=confidence,
                handler_class="CPMHandler",
                parameters={},
                notes=notes
            )
        
        return None
    
    def _detect_raw(self) -> FormatDetectionResult:
        """Fallback to raw format"""
        return FormatDetectionResult(
            format_type=DiskFormat.RAW,
            confidence=0.1,
            handler_class="RawHandler",
            parameters={},
            notes=["Unknown format - will provide hex analysis"]
        )
    
    def _count_fat_entries_at_offset(self, file_handle, offset: int) -> int:
        """Count valid FAT directory entries at given offset"""
        try:
            file_handle.seek(offset)
            dir_data = file_handle.read(512)
            return self._count_fat_entries_in_data(dir_data)
        except:
            return 0
    
    def _count_fat_entries_in_data(self, dir_data: bytes) -> int:
        """Count valid FAT directory entries in data"""
        valid_entries = 0
        
        for i in range(0, min(len(dir_data), 512), 32):
            if i + 32 > len(dir_data):
                break
                
            entry = dir_data[i:i+32]
            first_byte = entry[0]
            
            if first_byte == 0:  # End of directory
                break
            if first_byte == 0xE5:  # Deleted entry
                continue
            if first_byte < 0x20:  # Invalid
                continue
            
            try:
                name = entry[0:8].decode('ascii', errors='ignore').strip()
                attr = entry[11]
                size = struct.unpack('<L', entry[28:32])[0]
                
                if (name and 
                    len(name) >= 1 and
                    any(c.isalnum() or c in '._-+$' for c in name) and
                    attr < 0x80 and
                    size < 10000000):  # Less than 10MB
                    valid_entries += 1
                    
            except:
                continue
        
        return valid_entries
    
    def _check_hp150_file_patterns(self, file_handle, offset: int) -> int:
        """Check for HP150 specific file patterns"""
        patterns_found = 0
        
        try:
            file_handle.seek(offset)
            dir_data = file_handle.read(512)
            
            # Look for common HP150 file extensions and names
            hp150_patterns = [
                b'CAL',      # Calculator files
                b'OVL',      # Overlay files  
                b'PAS',      # Pascal files
                b'EXE',      # Executables
                b'IN$',      # Info files
                b'BAT',      # Batch files
                b'HLP',      # Help files
                b'MSG',      # Message files
                b'US',       # US locale files
                b'VC'        # VisiCalc files
            ]
            
            for pattern in hp150_patterns:
                if pattern in dir_data:
                    patterns_found += 1
                    
        except:
            pass
            
        return patterns_found
    
    def _check_cpm_directory_at_offset(self, file_handle, offset: int) -> bool:
        """Check if there's a valid CP/M directory at given offset"""
        try:
            file_handle.seek(offset)
            dir_data = file_handle.read(1024)
            
            valid_entries = 0
            total_checked = 0
            
            for i in range(0, min(len(dir_data), 512), 32):
                if i + 32 > len(dir_data):
                    break
                    
                entry = dir_data[i:i+32]
                user_code = entry[0]
                
                if user_code == 0xE5:  # Deleted
                    continue
                
                if user_code <= 15:  # Valid user codes
                    filename_area = entry[1:12]
                    printable_chars = sum(1 for b in filename_area if 0x20 <= b <= 0x7E)
                    
                    if printable_chars >= 1:
                        valid_entries += 1
                    
                    total_checked += 1
                    if total_checked >= 16:
                        break
            
            return valid_entries >= 2 and total_checked > 0
        except:
            return False
    
    def _validate_fat_table(self, file_handle, fat_start: int, fat_size: int) -> float:
        """Validate FAT table structure - returns confidence 0.0-1.0"""
        try:
            file_handle.seek(fat_start)
            fat_data = file_handle.read(min(fat_size, 512))  # Read first sector of FAT
            
            if len(fat_data) < 3:
                return 0.0
                
            # Check FAT12 signature in first two entries
            # First entry should be media descriptor (F0, F8, F9, FA, FB, FC, FD, FE, FF)
            # Second entry should be end-of-chain (FFF)
            media_descriptor = fat_data[0]
            if media_descriptor in [0xF0, 0xF8, 0xF9, 0xFA, 0xFB, 0xFC, 0xFD, 0xFE, 0xFF]:
                # Check for typical FAT12 end-of-chain pattern
                val = struct.unpack('<I', fat_data[0:3] + b'\x00')[0]
                entry1 = val & 0xFFF
                entry2 = (val >> 12) & 0xFFF
                
                confidence = 0.5
                if entry2 >= 0xFF8:  # End-of-chain marker
                    confidence = 0.8
                elif entry2 >= 0xFF0:  # Close to end-of-chain
                    confidence = 0.6
                    
                return confidence
                
        except:
            pass
            
        return 0.0
    
    def _validate_fat_directory(self, root_data: bytes) -> int:
        """Validate FAT directory structure - returns number of valid entries"""
        valid_entries = 0
        
        for i in range(0, min(len(root_data), 512), 32):
            if i + 32 > len(root_data):
                break
                
            entry = root_data[i:i+32]
            if len(entry) < 32:
                break
                
            first_byte = entry[0]
            
            if first_byte == 0:  # End of directory
                break
            if first_byte == 0xE5:  # Deleted entry
                continue
            if first_byte < 0x20:  # Invalid first char
                continue
            
            try:
                # Check 8.3 filename structure
                name_part = entry[0:8]
                ext_part = entry[8:11]
                attr = entry[11]
                cluster = struct.unpack('<H', entry[26:28])[0]
                size = struct.unpack('<L', entry[28:32])[0]
                
                # Validate filename characters (ASCII printable)
                name_valid = all(0x20 <= b <= 0x7E or b == 0x20 for b in name_part)
                ext_valid = all(0x20 <= b <= 0x7E or b == 0x20 for b in ext_part)
                
                # Validate attributes (should be reasonable)
                attr_valid = attr < 0x80
                
                # Validate cluster (should be reasonable for floppy)
                cluster_valid = cluster < 1000  # Reasonable for floppy
                
                # Validate size (should be reasonable)
                size_valid = size < 2000000  # Less than 2MB
                
                if name_valid and ext_valid and attr_valid and cluster_valid and size_valid:
                    valid_entries += 1
                    
            except:
                continue
        
        return valid_entries
    
    def _validate_cluster_chains(self, file_handle, root_data: bytes, fat_start: int, fat_size: int, root_dir_start: int) -> float:
        """Validate that cluster chains are consistent with file sizes - returns confidence 0.0-1.0"""
        try:
            # Read FAT table for validation
            file_handle.seek(fat_start)
            fat_data = file_handle.read(fat_size)
            
            # Parse a few FAT12 entries
            fat_table = []
            for i in range(0, min(len(fat_data) - 2, 24), 3):  # Check first 8 clusters
                three_bytes = fat_data[i:i+3]
                if len(three_bytes) >= 3:
                    val = struct.unpack('<I', three_bytes + b'\x00')[0]
                    entry1 = val & 0xFFF
                    entry2 = (val >> 12) & 0xFFF
                    fat_table.extend([entry1, entry2])
            
            consistent_files = 0
            total_files = 0
            
            # Check first few files for consistency
            for i in range(0, min(len(root_data), 160), 32):  # Check up to 5 files
                entry = root_data[i:i+32]
                if len(entry) < 32 or entry[0] == 0 or entry[0] == 0xE5 or entry[0] < 0x20:
                    continue
                    
                try:
                    cluster = struct.unpack('<H', entry[26:28])[0]
                    size = struct.unpack('<L', entry[28:32])[0]
                    attr = entry[11]
                    
                    # Skip directories and volume labels
                    if attr & 0x18:  # Directory or volume
                        continue
                        
                    total_files += 1
                    
                    # For files with size, check if cluster allocation makes sense
                    if size > 0 and 2 <= cluster < len(fat_table):
                        # Estimate clusters needed (assume 512-byte sectors, 1-2 sectors per cluster)
                        cluster_size = 512  # Conservative estimate
                        clusters_needed = (size + cluster_size - 1) // cluster_size
                        
                        if clusters_needed <= 10:  # Reasonable for small files
                            consistent_files += 1
                    elif size == 0 and cluster == 0:
                        consistent_files += 1  # Empty file is consistent
                        
                except:
                    continue
            
            if total_files > 0:
                return consistent_files / total_files
                
        except:
            pass
            
        return 0.0
