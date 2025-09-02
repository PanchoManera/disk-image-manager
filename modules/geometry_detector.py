#!/usr/bin/env python3
"""
Geometry Detection Module
Detects disk geometry from TD0 files or IMG files, providing a unified interface
for geometry analysis across different file formats.
"""

import sys
import os
import struct
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum

# Import TD0 reader for TD0 analysis
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# TD0Reader and TD0Decompressor will be passed as parameters to avoid circular imports

@dataclass
class GeometryInfo:
    """Detected disk geometry information"""
    type: str = "unknown"
    cylinders: int = 0
    heads: int = 0
    sectors_per_track: int = 16
    bytes_per_sector: int = 256
    has_phantom: bool = False
    total_sectors: int = 0
    file_size: int = 0
    source_format: str = "unknown"  # "td0", "img", etc.
    sector_counts: Dict[Tuple[int, int], int] = field(default_factory=dict)
    sector_sizes: Dict[int, int] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

class GeometryDetector:
    """Unified geometry detector for TD0 and IMG files"""
    
    def __init__(self):
        self.debug = False
    
    def detect_from_file(self, filename: str) -> GeometryInfo:
        """
        Detect geometry from a file (TD0 or IMG)
        Automatically determines file type and uses appropriate detection method
        """
        if not os.path.exists(filename):
            raise FileNotFoundError(f"File not found: {filename}")
        
        file_ext = os.path.splitext(filename.lower())[1]
        file_size = os.path.getsize(filename)
        
        if file_ext == '.td0':
            return self.detect_from_td0(filename)
        elif file_ext in ['.img', '.ima', '.dsk']:
            return self.detect_from_img(filename)
        else:
            # Try to detect by content
            return self._detect_by_content(filename)
    
    def detect_from_td0(self, filename: str, td0_reader_class=None) -> GeometryInfo:
        """Detect geometry from TD0 file"""
        try:
            # Import here to avoid circular imports
            from .td0_converter_lib import TD0Reader
            
            reader = TD0Reader(filename)
            header = reader.parse_header()
            
            geometry = GeometryInfo()
            geometry.source_format = "td0"
            geometry.file_size = os.path.getsize(filename)
            
            # Handle compression
            if header['compressed']:
                compressed_data = reader.data[reader.pos:]
                decompressed = reader.decompressor.decompress(compressed_data)
                reader.data = reader.data[:reader.pos] + decompressed
            
            # Skip comment if present
            if header['has_comment']:
                reader.parse_comment()
            
            # Parse all tracks to analyze geometry
            tracks = self._parse_td0_tracks(reader)
            
            if not tracks:
                geometry.notes.append("No tracks found in TD0 file")
                return geometry
            
            # Analyze track data
            geometry = self._analyze_track_data(tracks, geometry)
            
            # Add TD0-specific notes
            geometry.notes.append(f"TD0 version: {header['version']}")
            geometry.notes.append(f"Drive type: {header['drive_type']}")
            geometry.notes.append(f"Compressed: {header['compressed']}")
            
            return geometry
            
        except Exception as e:
            geometry = GeometryInfo()
            geometry.source_format = "td0"
            geometry.file_size = os.path.getsize(filename) if os.path.exists(filename) else 0
            geometry.notes.append(f"Error reading TD0: {str(e)}")
            return geometry
    
    def detect_from_img(self, filename: str) -> GeometryInfo:
        """Detect geometry from IMG file"""
        geometry = GeometryInfo()
        geometry.source_format = "img"
        geometry.file_size = os.path.getsize(filename)
        
        # Standard floppy disk sizes and their typical geometries
        standard_geometries = {
            # Size: (cylinders, heads, sectors_per_track, bytes_per_sector)
            163840:  (40, 1, 16, 256),    # 160K - HP150 single-sided
            327680:  (40, 2, 16, 256),    # 320K - HP150 double-sided
            368640:  (40, 2, 18, 256),    # 360K - PC format adapted
            737280:  (80, 2, 18, 256),    # 720K - PC format adapted
            1228800: (80, 2, 30, 256),    # 1.2M - High density adapted
            1474560: (80, 2, 36, 256),    # 1.44M - HD adapted
            
            # HP150 specific sizes
            655360:  (80, 1, 32, 256),    # 640K - HP150 extended
            1310720: (80, 2, 32, 256),    # 1.28M - HP150 extended DS
        }
        
        # Try to match known geometry
        if geometry.file_size in standard_geometries:
            cyls, heads, spt, bps = standard_geometries[geometry.file_size]
            geometry.cylinders = cyls
            geometry.heads = heads
            geometry.sectors_per_track = spt
            geometry.bytes_per_sector = bps
            geometry.total_sectors = (cyls * heads * spt)
            geometry.type = "standard"
            
            # Determine if it's HP150 format
            if bps == 256 and spt in [16, 32]:
                geometry.type = "hp150_standard"
                geometry.notes.append("Detected HP150 standard format")
            else:
                geometry.notes.append(f"Detected standard PC format: {cyls}x{heads}x{spt}x{bps}")
        else:
            # Try to infer geometry
            geometry = self._infer_img_geometry(filename, geometry)
        
        # Analyze boot sector if present
        self._analyze_boot_sector(filename, geometry)
        
        return geometry
    
    def _detect_by_content(self, filename: str) -> GeometryInfo:
        """Try to detect file type by examining content"""
        try:
            with open(filename, 'rb') as f:
                header = f.read(12)
            
            # Check for TD0 signature
            if header[:2] == b'TD' or header[:2] == b'td':
                return self.detect_from_td0(filename)
            
            # Check for common boot sector signatures
            with open(filename, 'rb') as f:
                f.seek(510)
                boot_sig = f.read(2)
                if boot_sig == b'\x55\xaa':
                    return self.detect_from_img(filename)
            
            # Default to IMG detection
            return self.detect_from_img(filename)
            
        except Exception as e:
            geometry = GeometryInfo()
            geometry.source_format = "unknown"
            geometry.file_size = os.path.getsize(filename) if os.path.exists(filename) else 0
            geometry.notes.append(f"Error detecting file type: {str(e)}")
            return geometry
    
    def _parse_td0_tracks(self, reader) -> List[Dict[str, Any]]:
        """Parse tracks from TD0 file"""
        tracks = []
        
        while True:
            track = reader.parse_track()
            if track is None:
                break
            
            track_data = {
                'cylinder': track['cylinder'],
                'head': track['head'],
                'num_sectors': track['num_sectors'],
                'sectors': {}
            }
            
            # Parse sectors for this track
            for i in range(track['num_sectors']):
                sector = reader.parse_sector()
                if sector is None:
                    break
                
                # Check for special sectors
                sector_num = sector['sector_num']
                is_phantom = sector_num & 0x60 == 0x60
                is_special = sector_num == 0x65
                
                if is_phantom or is_special:
                    continue
                
                # Parse sector data
                sector_data = reader.parse_sector_data(sector)
                if sector_data is not None:
                    track_data['sectors'][sector_num] = sector_data
            
            tracks.append(track_data)
        
        return tracks
    
    def _analyze_track_data(self, tracks: List[Dict[str, Any]], geometry: GeometryInfo) -> GeometryInfo:
        """Analyze track data to determine geometry"""
        if not tracks:
            return geometry
        
        # Find max cylinder and head
        geometry.cylinders = max(t['cylinder'] for t in tracks) + 1
        geometry.heads = max(t['head'] for t in tracks) + 1
        
        # Analyze sector patterns
        sector_counts = {}
        sector_sizes = {}
        total_sectors = 0
        
        for track in tracks:
            track_id = (track['cylinder'], track['head'])
            sector_count = len(track['sectors'])
            sector_counts[track_id] = sector_count
            total_sectors += sector_count
            
            # Check sector sizes
            for sector_num, sector_data in track['sectors'].items():
                if sector_data and len(sector_data) > 0:
                    sector_sizes[sector_num] = len(sector_data)
                    
                # Check for phantom sectors
                if sector_num & 0x60 == 0x60:
                    geometry.has_phantom = True
        
        # Determine most common patterns
        if sector_counts:
            geometry.sectors_per_track = max(set(sector_counts.values()), 
                                           key=list(sector_counts.values()).count)
        if sector_sizes:
            geometry.bytes_per_sector = max(set(sector_sizes.values()), 
                                          key=list(sector_sizes.values()).count)
        
        geometry.total_sectors = total_sectors
        geometry.sector_counts = sector_counts
        geometry.sector_sizes = sector_sizes
        
        # Classify geometry type
        geometry.type = self._classify_geometry_type(geometry, sector_counts)
        
        return geometry
    
    def _classify_geometry_type(self, geometry: GeometryInfo, sector_counts: Dict) -> str:
        """Classify the type of geometry detected"""
        # Check for AKAI format (phantom sectors)
        if geometry.has_phantom:
            return "akai"
        
        # Check for variable sector counts
        unique_counts = set(sector_counts.values())
        if len(unique_counts) > 1:
            return "variable"
        
        # Check for HP150 standard
        if (geometry.bytes_per_sector == 256 and 
            geometry.sectors_per_track in [16, 32]):
            return "hp150_standard"
        
        # Check for PC standard formats
        if (geometry.bytes_per_sector == 512 and 
            geometry.sectors_per_track in [8, 9, 15, 18, 36]):
            return "pc_standard"
        
        return "custom"
    
    def _infer_img_geometry(self, filename: str, geometry: GeometryInfo) -> GeometryInfo:
        """Try to infer geometry from IMG file size and structure"""
        size = geometry.file_size
        
        # Common sector sizes
        sector_sizes = [128, 256, 512, 1024]
        
        for sector_size in sector_sizes:
            total_sectors = size // sector_size
            if size % sector_size != 0:
                continue
            
            # Try common track/head combinations
            combinations = [
                (40, 1),   # Single-sided 40 track
                (40, 2),   # Double-sided 40 track
                (80, 1),   # Single-sided 80 track
                (80, 2),   # Double-sided 80 track
                (77, 1),   # Some CP/M formats
                (77, 2),   # Some CP/M formats
            ]
            
            for cyls, heads in combinations:
                sectors_per_track = total_sectors // (cyls * heads)
                
                if (sectors_per_track > 0 and 
                    sectors_per_track <= 50 and  # Reasonable limit
                    total_sectors == cyls * heads * sectors_per_track):
                    
                    geometry.cylinders = cyls
                    geometry.heads = heads
                    geometry.sectors_per_track = sectors_per_track
                    geometry.bytes_per_sector = sector_size
                    geometry.total_sectors = total_sectors
                    
                    # Classify based on parameters
                    if sector_size == 256 and sectors_per_track in [16, 32]:
                        geometry.type = "hp150_inferred"
                        geometry.notes.append("Inferred HP150 format from file size")
                    else:
                        geometry.type = "inferred"
                        geometry.notes.append(f"Inferred geometry: {cyls}x{heads}x{sectors_per_track}x{sector_size}")
                    
                    return geometry
        
        # If no standard geometry found, make best guess
        geometry.notes.append("Could not determine standard geometry")
        geometry.type = "unknown"
        
        # Default HP150 assumption for unknown files
        if size >= 163840:  # At least 160K
            geometry.cylinders = 80
            geometry.heads = 1 if size <= 500000 else 2
            geometry.sectors_per_track = 16
            geometry.bytes_per_sector = 256
            geometry.total_sectors = size // 256
            geometry.type = "hp150_assumed"
            geometry.notes.append("Assumed HP150 format for unknown file")
        
        return geometry
    
    def _analyze_boot_sector(self, filename: str, geometry: GeometryInfo):
        """Analyze boot sector for additional geometry clues"""
        try:
            with open(filename, 'rb') as f:
                boot_sector = f.read(512)
            
            if len(boot_sector) < 512:
                return
            
            # Check for boot signature
            if boot_sector[510:512] == b'\x55\xaa':
                geometry.notes.append("Valid boot signature found")
                
                # Check for HP150 OEM ID
                oem_id = boot_sector[3:11]
                if oem_id == b'HP150   ':
                    geometry.notes.append("HP150 OEM ID detected")
                    if geometry.type == "inferred":
                        geometry.type = "hp150_confirmed"
                
                # Try to parse BPB (BIOS Parameter Block) if present
                self._parse_bpb(boot_sector, geometry)
            
        except Exception as e:
            geometry.notes.append(f"Error analyzing boot sector: {str(e)}")
    
    def _parse_bpb(self, boot_sector: bytes, geometry: GeometryInfo):
        """Parse BIOS Parameter Block for geometry information"""
        try:
            # DOS BPB structure (basic fields)
            if len(boot_sector) >= 32:
                bytes_per_sector = struct.unpack('<H', boot_sector[11:13])[0]
                sectors_per_cluster = boot_sector[13]
                reserved_sectors = struct.unpack('<H', boot_sector[14:16])[0]
                num_fats = boot_sector[16]
                root_entries = struct.unpack('<H', boot_sector[17:19])[0]
                total_sectors_16 = struct.unpack('<H', boot_sector[19:21])[0]
                media_descriptor = boot_sector[21]
                sectors_per_fat = struct.unpack('<H', boot_sector[22:24])[0]
                sectors_per_track = struct.unpack('<H', boot_sector[24:26])[0]
                num_heads = struct.unpack('<H', boot_sector[26:28])[0]
                
                # Validate and use BPB data if reasonable
                if (bytes_per_sector in [128, 256, 512, 1024] and
                    sectors_per_track > 0 and sectors_per_track <= 50 and
                    num_heads > 0 and num_heads <= 2):
                    
                    geometry.notes.append("BPB found with valid geometry data")
                    
                    # Update geometry if it seems more reliable
                    if geometry.type in ["unknown", "inferred"]:
                        if bytes_per_sector == 256:
                            geometry.bytes_per_sector = bytes_per_sector
                            geometry.sectors_per_track = sectors_per_track
                            geometry.heads = num_heads
                            geometry.type = "bpb_detected"
                            geometry.notes.append(f"Updated from BPB: {sectors_per_track} sectors/track, {num_heads} heads")
                    
        except (struct.error, IndexError):
            pass  # BPB parsing failed, continue with other methods

def detect_geometry(filename: str, debug: bool = False) -> GeometryInfo:
    """
    Convenience function to detect geometry from any supported file
    """
    detector = GeometryDetector()
    detector.debug = debug
    return detector.detect_from_file(filename)

# For backward compatibility
class GeometryDetectorLegacy:
    """Legacy interface for existing code"""
    
    @staticmethod
    def detect_geometry(tracks: List[Dict]) -> Dict[str, Any]:
        """Legacy method for TD0 track data analysis"""
        if not tracks:
            return {"type": "unknown", "sectors_per_track": 16, "bytes_per_sector": 256}
        
        max_cylinder = max(t['cylinder'] for t in tracks)
        max_head = max(t['head'] for t in tracks)
        
        # Analyze sector patterns
        sector_counts = {}
        sector_sizes = {}
        
        for track in tracks:
            track_id = (track['cylinder'], track['head'])
            sector_count = len(track['sectors'])
            sector_counts[track_id] = sector_count
            
            # Check sector sizes
            for sector_num, sector_data in track['sectors'].items():
                if sector_data and len(sector_data) > 0:
                    sector_sizes[sector_num] = len(sector_data)
        
        # Determine most common patterns
        common_sector_count = max(set(sector_counts.values()), key=list(sector_counts.values()).count) if sector_counts else 16
        common_sector_size = max(set(sector_sizes.values()), key=list(sector_sizes.values()).count) if sector_sizes else 256
        
        # Detect special formats
        geometry_type = "hp150_standard"
        
        # Check for AKAI format (phantom sectors)
        has_phantom = any(sector_num & 0x60 == 0x60 for track in tracks for sector_num in track['sectors'].keys())
        if has_phantom:
            geometry_type = "akai"
        
        # Check for variable sector counts
        if len(set(sector_counts.values())) > 1:
            geometry_type = "variable"
        
        return {
            "type": geometry_type,
            "cylinders": max_cylinder + 1,
            "heads": max_head + 1,
            "sectors_per_track": common_sector_count,
            "bytes_per_sector": common_sector_size,
            "has_phantom": has_phantom,
            "sector_counts": sector_counts,
            "sector_sizes": sector_sizes
        }
