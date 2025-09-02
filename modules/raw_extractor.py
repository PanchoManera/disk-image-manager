#!/usr/bin/env python3
"""
Raw Disk Image Extractor
Extracts useful information from unknown/raw disk formats
"""

import os
import struct
from typing import Dict, List, Optional

class RawExtractor:
    def __init__(self, image_path: str, verbose: bool = False):
        self.image_path = image_path
        self.verbose = verbose
        self.file_size = os.path.getsize(image_path)
    
    def extract_information(self, output_dir: str) -> Dict[str, str]:
        """Extract useful information from raw disk image"""
        os.makedirs(output_dir, exist_ok=True)
        extracted_files = {}
        
        with open(self.image_path, 'rb') as f:
            # 1. Create hex dump of first sectors
            hex_file = self._create_hex_dump(f, output_dir)
            if hex_file:
                extracted_files["first_sectors.hex"] = hex_file
            
            # 2. Extract boot sector
            boot_file = self._extract_boot_sector(f, output_dir)
            if boot_file:
                extracted_files["boot_sector.bin"] = boot_file
            
            # 3. Create ASCII dump for text search
            ascii_file = self._create_ascii_dump(f, output_dir)
            if ascii_file:
                extracted_files["ascii_dump.txt"] = ascii_file
            
            # 4. Extract sector analysis
            analysis_file = self._create_sector_analysis(f, output_dir)
            if analysis_file:
                extracted_files["sector_analysis.txt"] = analysis_file
            
            # 5. Look for potential file signatures
            signatures_file = self._search_file_signatures(f, output_dir)
            if signatures_file:
                extracted_files["file_signatures.txt"] = signatures_file
        
        return extracted_files
    
    def _create_hex_dump(self, f, output_dir: str) -> Optional[str]:
        """Create hex dump of first 8KB"""
        try:
            hex_file = os.path.join(output_dir, "first_sectors.hex")
            
            f.seek(0)
            data = f.read(8192)  # First 8KB
            
            with open(hex_file, 'w') as out:
                out.write("Hex dump of first 8KB of disk image:\n")
                out.write("=" * 50 + "\n\n")
                
                for i in range(0, len(data), 16):
                    chunk = data[i:i+16]
                    hex_part = ' '.join(f'{b:02X}' for b in chunk)
                    ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
                    out.write(f"{i:08X}: {hex_part:<48} |{ascii_part}|\n")
            
            return hex_file
        except Exception as e:
            if self.verbose:
                print(f"Error creating hex dump: {e}")
            return None
    
    def _extract_boot_sector(self, f, output_dir: str) -> Optional[str]:
        """Extract potential boot sector"""
        try:
            boot_file = os.path.join(output_dir, "boot_sector.bin")
            
            f.seek(0)
            boot_data = f.read(512)
            
            if len(boot_data) == 512:
                with open(boot_file, 'wb') as out:
                    out.write(boot_data)
                return boot_file
        except Exception as e:
            if self.verbose:
                print(f"Error extracting boot sector: {e}")
        return None
    
    def _create_ascii_dump(self, f, output_dir: str) -> Optional[str]:
        """Create ASCII dump for text search"""
        try:
            ascii_file = os.path.join(output_dir, "ascii_dump.txt")
            
            f.seek(0)
            
            with open(ascii_file, 'w') as out:
                out.write("ASCII strings found in disk image:\n")
                out.write("=" * 40 + "\n\n")
                
                chunk_size = 4096
                offset = 0
                
                while offset < self.file_size:
                    f.seek(offset)
                    data = f.read(chunk_size)
                    if not data:
                        break
                    
                    # Extract strings of printable characters
                    current_string = ""
                    string_start = 0
                    
                    for i, byte in enumerate(data):
                        if 32 <= byte <= 126:  # Printable ASCII
                            if not current_string:
                                string_start = offset + i
                            current_string += chr(byte)
                        else:
                            if len(current_string) >= 4:  # Only strings of 4+ chars
                                out.write(f"{string_start:08X}: {current_string}\n")
                            current_string = ""
                    
                    # Handle string at end of chunk
                    if len(current_string) >= 4:
                        out.write(f"{string_start:08X}: {current_string}\n")
                    
                    offset += chunk_size
            
            return ascii_file
        except Exception as e:
            if self.verbose:
                print(f"Error creating ASCII dump: {e}")
            return None
    
    def _create_sector_analysis(self, f, output_dir: str) -> Optional[str]:
        """Analyze sectors for patterns"""
        try:
            analysis_file = os.path.join(output_dir, "sector_analysis.txt")
            
            with open(analysis_file, 'w') as out:
                out.write("Disk Image Sector Analysis\n")
                out.write("=" * 30 + "\n\n")
                
                out.write(f"File size: {self.file_size:,} bytes\n")
                out.write(f"Potential geometries:\n")
                
                # Common sector sizes
                for sector_size in [128, 256, 512, 1024]:
                    sectors = self.file_size // sector_size
                    out.write(f"  {sector_size} bytes/sector: {sectors} sectors\n")
                    
                    # Try common geometries
                    for heads in [1, 2]:
                        for spt in [5, 8, 9, 10, 15, 16, 18, 26]:
                            if sectors % (heads * spt) == 0:
                                tracks = sectors // (heads * spt)
                                if tracks <= 100:  # Reasonable track count
                                    out.write(f"    -> {tracks}C/{heads}H/{spt}S\n")
                
                out.write("\nSector Analysis:\n")
                out.write("-" * 20 + "\n")
                
                # Analyze first few sectors
                for sector_size in [512, 1024]:
                    out.write(f"\nUsing {sector_size}-byte sectors:\n")
                    
                    for sector_num in range(min(8, self.file_size // sector_size)):
                        f.seek(sector_num * sector_size)
                        sector_data = f.read(sector_size)
                        
                        # Analyze sector content
                        zero_bytes = sector_data.count(0)
                        ff_bytes = sector_data.count(0xFF)
                        
                        out.write(f"  Sector {sector_num}: ")
                        out.write(f"Zero={zero_bytes} FF={ff_bytes} ")
                        
                        if zero_bytes == len(sector_data):
                            out.write("[EMPTY]")
                        elif ff_bytes == len(sector_data):
                            out.write("[ERASED]")
                        elif zero_bytes > len(sector_data) * 0.8:
                            out.write("[MOSTLY EMPTY]")
                        else:
                            out.write("[DATA]")
                        
                        # Look for text strings
                        text_chars = sum(1 for b in sector_data if 32 <= b <= 126)
                        if text_chars > len(sector_data) * 0.3:
                            out.write(" [TEXT?]")
                        
                        out.write("\n")
            
            return analysis_file
        except Exception as e:
            if self.verbose:
                print(f"Error creating sector analysis: {e}")
            return None
    
    def _search_file_signatures(self, f, output_dir: str) -> Optional[str]:
        """Search for known file signatures"""
        try:
            signatures_file = os.path.join(output_dir, "file_signatures.txt")
            
            # Common file signatures
            signatures = {
                b'\x4D\x5A': 'DOS Executable (MZ)',
                b'\x50\x4B': 'ZIP Archive',
                b'\x1F\x8B': 'GZIP Archive', 
                b'\x42\x5A': 'BZIP2 Archive',
                b'\x89\x50\x4E\x47': 'PNG Image',
                b'\xFF\xD8\xFF': 'JPEG Image',
                b'\x47\x49\x46\x38': 'GIF Image',
                b'\x42\x4D': 'BMP Image',
                b'\x25\x50\x44\x46': 'PDF Document',
                b'\xD0\xCF\x11\xE0': 'MS Office Document',
                b'\x50\x4B\x03\x04': 'ZIP/Office Document',
                b'\x7F\x45\x4C\x46': 'ELF Executable',
                b'\xCA\xFE\xBA\xBE': 'Java Class File',
                b'\xFE\xED\xFA': 'Mach-O Binary',
                b'\x4C\x01': 'MS COFF Object',
                b'\x4D\x53\x44\x4F\x53': 'MS-DOS System',
                b'\x49\x42\x4D': 'IBM Format',
                # CP/M specific
                b'\xC3': 'CP/M COM file (potential)',
                b'\x31\xC0': 'x86 Assembly start',
            }
            
            with open(signatures_file, 'w') as out:
                out.write("File Signature Search Results\n")
                out.write("=" * 32 + "\n\n")
                
                found_signatures = []
                
                # Search through the disk
                chunk_size = 4096
                offset = 0
                
                while offset < self.file_size:
                    f.seek(offset)
                    data = f.read(chunk_size)
                    if not data:
                        break
                    
                    # Look for signatures
                    for sig_bytes, description in signatures.items():
                        pos = data.find(sig_bytes)
                        if pos != -1:
                            file_offset = offset + pos
                            found_signatures.append((file_offset, description, sig_bytes))
                    
                    offset += chunk_size - len(max(signatures.keys(), key=len))  # Overlap to catch signatures at boundaries
                
                # Write results
                if found_signatures:
                    out.write("Found file signatures:\n")
                    for file_offset, description, sig_bytes in found_signatures:
                        hex_sig = ' '.join(f'{b:02X}' for b in sig_bytes)
                        out.write(f"  0x{file_offset:08X}: {description} ({hex_sig})\n")
                else:
                    out.write("No known file signatures found.\n")
                
                # Additional analysis
                out.write("\nAdditional Analysis:\n")
                out.write("-" * 20 + "\n")
                
                # Check for text files
                f.seek(0)
                sample = f.read(min(4096, self.file_size))
                text_chars = sum(1 for b in sample if 32 <= b <= 126 or b in [9, 10, 13])
                
                if text_chars > len(sample) * 0.7:
                    out.write("Disk appears to contain mostly text data\n")
                elif text_chars > len(sample) * 0.3:
                    out.write("Disk contains significant text data\n")
                else:
                    out.write("Disk appears to contain mostly binary data\n")
                
                # Entropy analysis (simple)
                byte_counts = [0] * 256
                for b in sample:
                    byte_counts[b] += 1
                
                unique_bytes = sum(1 for count in byte_counts if count > 0)
                out.write(f"Byte diversity: {unique_bytes}/256 unique byte values\n")
                
                if unique_bytes < 50:
                    out.write("Low entropy - may be compressed or encrypted\n")
                elif unique_bytes > 200:
                    out.write("High entropy - likely uncompressed data\n")
            
            return signatures_file
        except Exception as e:
            if self.verbose:
                print(f"Error searching file signatures: {e}")
            return None
    
    def extract_sectors_as_files(self, output_dir: str, sector_size: int = 512) -> Dict[str, str]:
        """Extract individual sectors as separate files"""
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            sectors_dir = os.path.join(output_dir, "sectors")
            os.makedirs(sectors_dir, exist_ok=True)
            
            extracted_files = {}
            num_sectors = self.file_size // sector_size
            
            with open(self.image_path, 'rb') as f:
                for sector_num in range(min(num_sectors, 100)):  # Limit to first 100 sectors
                    f.seek(sector_num * sector_size)
                    sector_data = f.read(sector_size)
                    
                    if len(sector_data) != sector_size:
                        break
                    
                    # Skip empty sectors
                    if sector_data.count(0) == len(sector_data):
                        continue
                    
                    sector_file = os.path.join(sectors_dir, f"sector_{sector_num:03d}.bin")
                    with open(sector_file, 'wb') as sector_out:
                        sector_out.write(sector_data)
                    
                    extracted_files[f"sector_{sector_num:03d}.bin"] = sector_file
            
            # Create index file
            index_file = os.path.join(output_dir, "sector_index.txt")
            with open(index_file, 'w') as out:
                out.write(f"Sector extraction from: {os.path.basename(self.image_path)}\n")
                out.write(f"Sector size: {sector_size} bytes\n")
                out.write(f"Total sectors: {num_sectors}\n")
                out.write(f"Extracted sectors: {len(extracted_files)}\n\n")
                
                out.write("Extracted sector files:\n")
                for filename in sorted(extracted_files.keys()):
                    out.write(f"  {filename}\n")
            
            extracted_files["sector_index.txt"] = index_file
            
            return extracted_files
        except Exception as e:
            if self.verbose:
                print(f"Error extracting sectors: {e}")
            return {}
    
    def create_disk_image_copy(self, output_dir: str) -> Optional[str]:
        """Create a copy of the raw disk image"""
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            base_name = os.path.splitext(os.path.basename(self.image_path))[0]
            copy_file = os.path.join(output_dir, f"{base_name}_copy.img")
            
            with open(self.image_path, 'rb') as src:
                with open(copy_file, 'wb') as dst:
                    while True:
                        chunk = src.read(64 * 1024)  # 64KB chunks
                        if not chunk:
                            break
                        dst.write(chunk)
            
            return copy_file
        except Exception as e:
            if self.verbose:
                print(f"Error creating disk copy: {e}")
            return None
