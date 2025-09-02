#!/usr/bin/env python3
"""
CP/M File Extractor
Extracts files from CP/M disk images, particularly Osborne-1 format
"""

import struct
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

@dataclass
class CPMFileInfo:
    name: str
    ext: str
    user_code: int
    extent: int
    record_count: int
    allocation_blocks: List[int]
    size_estimate: int
    directory_offset: int

class CPMExtractor:
    def __init__(self, image_path: str, verbose: bool = False):
        self.image_path = image_path
        self.verbose = verbose
        self.file_handle = None
        
        # CP/M disk parameters (defaulting to Osborne-1)
        self.bytes_per_sector = 1024
        self.sectors_per_track = 5
        self.tracks = 40
        self.block_size = 1024  # Allocation block size
        self.directory_tracks = 2  # Number of tracks for directory
        self.directory_offset = None
        
        # Common Osborne-1 directory offsets to try
        self.osborne_offsets = [
            0x3000,   # Track 3 (15 * 1024)
            0x3C00,   # Track 3 proper calculation 
            0x1400,   # Track 1
            0x2800,   # Track 2  
            0x1100,   # Traditional
            0x2000,   # Common alternative
            0x2400,   # Another alternative
        ]
    
    def open(self):
        """Open the disk image file"""
        self.file_handle = open(self.image_path, 'rb')
        self._detect_directory_location()
    
    def close(self):
        """Close the disk image file"""
        if self.file_handle:
            self.file_handle.close()
            self.file_handle = None
    
    def _detect_directory_location(self):
        """Find the CP/M directory location"""
        for offset in self.osborne_offsets:
            if self._check_cpm_directory_at_offset(offset):
                self.directory_offset = offset
                if self.verbose:
                    print(f"Found CP/M directory at offset 0x{offset:X}")
                return
        
        if self.verbose:
            print("Warning: Could not locate CP/M directory")
    
    def _check_cpm_directory_at_offset(self, offset: int) -> bool:
        """Check if there's a valid CP/M directory at the given offset"""
        try:
            self.file_handle.seek(offset)
            dir_data = self.file_handle.read(2048)
            
            valid_entries = 0
            total_checked = 0
            
            for i in range(0, min(len(dir_data), 1024), 32):
                if i + 32 > len(dir_data):
                    break
                    
                entry = dir_data[i:i+32]
                user_code = entry[0]
                
                if user_code == 0xE5:  # Deleted entry
                    continue
                
                if user_code <= 15:  # Valid user codes
                    filename_area = entry[1:12]
                    
                    # Check for reasonable filename characters
                    printable_chars = 0
                    for byte in filename_area:
                        if 0x20 <= byte <= 0x7E:
                            printable_chars += 1
                        elif byte == 0x00 or byte == 0x20:
                            continue
                        else:
                            break
                    
                    if printable_chars >= 1:
                        valid_entries += 1
                    
                    total_checked += 1
                    if total_checked >= 16:
                        break
            
            return valid_entries >= 2 and total_checked > 0
        except:
            return False
    
    def parse_directory(self) -> List[CPMFileInfo]:
        """Parse the CP/M directory and return file information"""
        if not self.directory_offset:
            return []
        
        files = []
        parsed_files = {}  # Track by name to handle extents
        
        self.file_handle.seek(self.directory_offset)
        dir_data = self.file_handle.read(2048)  # Read directory area
        
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
            
            # Parse filename (8 characters) and extension (3 characters)
            filename_raw = entry[1:9]
            extension_raw = entry[9:12]
            extent = entry[12]
            record_count = entry[15]
            
            # Clean filename and extension
            filename = self._clean_cpm_name(filename_raw)
            extension = self._clean_cpm_name(extension_raw)
            
            if not filename:
                continue
            
            # Parse allocation blocks (16 bytes, each byte is a block number)
            allocation_map = entry[16:32]
            allocation_blocks = [b for b in allocation_map if b != 0]
            
            # Estimate file size
            size_estimate = len(allocation_blocks) * self.block_size
            if record_count > 0:
                # More accurate size for last extent
                last_extent_size = record_count * 128  # CP/M records are 128 bytes
                if extent == 0:  # First/only extent
                    size_estimate = last_extent_size
                else:
                    size_estimate = (extent * 128 * 128) + last_extent_size
            
            full_name = f"{filename}.{extension}" if extension else filename
            
            # Handle multiple extents of the same file
            if full_name in parsed_files:
                # Combine with existing entry
                existing = parsed_files[full_name]
                existing.allocation_blocks.extend(allocation_blocks)
                existing.size_estimate += size_estimate
            else:
                file_info = CPMFileInfo(
                    name=filename,
                    ext=extension,
                    user_code=user_code,
                    extent=extent,
                    record_count=record_count,
                    allocation_blocks=allocation_blocks,
                    size_estimate=size_estimate,
                    directory_offset=self.directory_offset + i
                )
                parsed_files[full_name] = file_info
                files.append(file_info)
        
        return files
    
    def _clean_cpm_name(self, name_bytes: bytes) -> str:
        """Clean CP/M filename bytes"""
        try:
            # CP/M uses high bit for attributes, mask it off
            clean_bytes = bytes(b & 0x7F for b in name_bytes)
            decoded = clean_bytes.decode('ascii', errors='ignore')
            
            # Remove spaces and control characters
            clean = ''.join(c for c in decoded if c.isprintable() and c != ' ')
            return clean.rstrip()
        except:
            return ""
    
    def extract_file(self, file_info: CPMFileInfo, output_path: str) -> bool:
        """Extract a single CP/M file"""
        try:
            if not file_info.allocation_blocks:
                if self.verbose:
                    print(f"No allocation blocks for {file_info.name}")
                return False
            
            with open(output_path, 'wb') as output_file:
                bytes_written = 0
                
                for block_num in file_info.allocation_blocks:
                    if block_num == 0:
                        continue
                    
                    # Calculate block offset
                    # Assume directory starts at track 3, data blocks start after directory
                    data_start_track = (self.directory_offset // (self.bytes_per_sector * self.sectors_per_track)) + self.directory_tracks
                    block_offset = data_start_track * self.bytes_per_sector * self.sectors_per_track + (block_num * self.block_size)
                    
                    self.file_handle.seek(block_offset)
                    block_data = self.file_handle.read(self.block_size)
                    
                    if len(block_data) == 0:
                        break
                    
                    # For the last block, only write the actual file size
                    if bytes_written + len(block_data) > file_info.size_estimate:
                        remaining = file_info.size_estimate - bytes_written
                        if remaining > 0:
                            output_file.write(block_data[:remaining])
                        break
                    else:
                        output_file.write(block_data)
                        bytes_written += len(block_data)
            
            return True
            
        except Exception as e:
            if self.verbose:
                print(f"Error extracting {file_info.name}: {e}")
            return False
    
    def extract_all_files(self, output_dir: str) -> Dict[str, str]:
        """Extract all files from the CP/M disk"""
        if not self.file_handle:
            self.open()
        
        if not self.directory_offset:
            if self.verbose:
                print("No CP/M directory found")
            return {}
        
        os.makedirs(output_dir, exist_ok=True)
        
        files = self.parse_directory()
        extracted_files = {}
        
        for file_info in files:
            if not file_info.name:
                continue
            
            full_name = f"{file_info.name}.{file_info.ext}" if file_info.ext else file_info.name
            safe_name = self._make_safe_filename(full_name)
            output_path = os.path.join(output_dir, safe_name)
            
            if self.extract_file(file_info, output_path):
                extracted_files[full_name] = output_path
                if self.verbose:
                    print(f"Extracted: {full_name} ({file_info.size_estimate} bytes)")
            else:
                if self.verbose:
                    print(f"Failed to extract: {full_name}")
        
        return extracted_files
    
    def _make_safe_filename(self, filename: str) -> str:
        """Make filename safe for modern filesystems"""
        safe_chars = []
        for c in filename:
            if c.isalnum() or c in '.-_':
                safe_chars.append(c)
            else:
                safe_chars.append('_')
        return ''.join(safe_chars)
    
    def __enter__(self):
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
