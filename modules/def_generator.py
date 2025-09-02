#!/usr/bin/env python3
"""
DEF File Generator Module
Generates Greaseweazle .def files from geometry information, supporting various
disk formats and providing flexible template generation.
"""

import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from .geometry_detector import GeometryInfo

@dataclass
class DefGenerationOptions:
    """Options for .def file generation"""
    normalize_to_hp150: bool = False  # Usar geometría real por defecto
    include_comments: bool = True
    include_source_info: bool = True
    custom_name: Optional[str] = None
    force_format: Optional[str] = None  # "hp150", "pc", "custom"

class DefGenerator:
    """Generates Greaseweazle .def files from detected geometry"""
    
    def __init__(self, geometry: GeometryInfo, source_filename: str = "", options: DefGenerationOptions = None):
        self.geometry = geometry
        self.source_filename = source_filename
        self.options = options or DefGenerationOptions()
        self.disk_name = self._generate_disk_name()
    
    def generate_def_content(self) -> str:
        """Generate the complete .def file content"""
        lines = []
        
        # Header
        lines.append(f"disk {self.disk_name}")
        lines.append(f"    cyls = {self.geometry.cylinders}")
        lines.append(f"    heads = {self.geometry.heads}")
        lines.append("")
        
        # Add comments if enabled
        if self.options.include_comments:
            lines.extend(self._generate_comments())
            lines.append("")
        
        # Generate track definitions based on geometry type and options
        lines.extend(self._generate_track_definitions())
        
        lines.append("end")
        
        return "\n".join(lines)
    
    def save_def_file(self, output_path: str) -> bool:
        """Save .def file to disk"""
        try:
            content = self.generate_def_content()
            
            with open(output_path, 'w') as f:
                f.write(content)
            
            return True
            
        except Exception as e:
            return False
    
    def _generate_disk_name(self) -> str:
        """Generate disk name for .def file"""
        if self.options.custom_name:
            return self._sanitize_name(self.options.custom_name)
        
        if self.source_filename:
            base_name = os.path.splitext(os.path.basename(self.source_filename))[0]
            return self._sanitize_name(base_name)
        
        # Generate name based on geometry
        return f"disk_{self.geometry.cylinders}c_{self.geometry.heads}h_{self.geometry.sectors_per_track}s"
    
    def _sanitize_name(self, name: str) -> str:
        """Sanitize name for use in .def file"""
        # Replace invalid characters with underscores
        sanitized = ""
        for char in name:
            if char.isalnum() or char in "-_":
                sanitized += char
            else:
                sanitized += "_"
        
        # Ensure it starts with a letter or underscore
        if sanitized and not (sanitized[0].isalpha() or sanitized[0] == '_'):
            sanitized = "_" + sanitized
        
        return sanitized or "disk"
    
    def _generate_comments(self) -> List[str]:
        """Generate comment lines for .def file"""
        lines = []
        
        if self.options.include_source_info and self.source_filename:
            lines.append(f"    # Generated from: {os.path.basename(self.source_filename)}")
        
        lines.append(f"    # Source format: {self.geometry.source_format.upper()}")
        lines.append(f"    # Detected geometry: {self.geometry.type}")
        lines.append(f"    # IMG file size: {self.geometry.file_size} bytes ({self.geometry.file_size/1024:.1f} KB)")
        
        if self.geometry.total_sectors > 0:
            lines.append(f"    # Total sectors: {self.geometry.total_sectors}")
        
        # Add geometry details
        lines.append(f"    # Physical: {self.geometry.cylinders} cyl × {self.geometry.heads} head × {self.geometry.sectors_per_track} sec × {self.geometry.bytes_per_sector} bytes")
        
        # Add special notes
        if self.geometry.has_phantom:
            lines.append("    # Note: Original contains phantom sectors (filtered in output)")
        
        if self.geometry.notes:
            lines.append("    # Detection notes:")
            for note in self.geometry.notes:
                lines.append(f"    #   - {note}")
        
        return lines
    
    def _generate_track_definitions(self) -> List[str]:
        """Generate track definitions based on geometry and options"""
        # Determine output format
        if self.options.force_format:
            format_type = self.options.force_format
        elif self.options.normalize_to_hp150:
            format_type = "hp150"
        else:
            format_type = self._auto_detect_format()
        
        if format_type == "hp150":
            return self._generate_hp150_tracks()
        elif format_type == "pc":
            return self._generate_pc_tracks()
        elif format_type == "variable":
            return self._generate_variable_tracks()
        else:
            return self._generate_custom_tracks()
    
    def _auto_detect_format(self) -> str:
        """Auto-detect the best format type for track generation"""
        if self.geometry.type in ["hp150_standard", "hp150_inferred", "hp150_confirmed", "hp150_assumed"]:
            return "hp150"
        elif self.geometry.type == "pc_standard":
            return "pc"
        elif self.geometry.type == "variable":
            return "variable"
        else:
            return "custom"
    
    def _generate_hp150_tracks(self) -> List[str]:
        """Generate HP150-compatible track definitions"""
        lines = []
        
        if self.options.normalize_to_hp150:
            lines.append("    # HP150 Normalized Format")
            lines.append("    # All tracks normalized to HP150 standard (16 sectors × 256 bytes)")
            lines.append("")
            lines.append("    tracks * ibm.mfm")
            lines.append("        secs = 16")
            lines.append("        bps = 256")
            lines.append("        id = 0")
            lines.append("        h = 0")
            lines.append("        gap3 = 32")
            lines.append("        rate = 250")
            lines.append("        rpm = 300")
            lines.append("        interleave = 2")
            lines.append("        cskew = 4")
            lines.append("    end")
        else:
            # Use original geometry but with HP150 parameters
            lines.append(f"    # HP150 Format - {self.geometry.sectors_per_track} sectors per track")
            lines.append("    tracks * ibm.mfm")
            lines.append(f"        secs = {self.geometry.sectors_per_track}")
            lines.append(f"        bps = {self.geometry.bytes_per_sector}")
            lines.append("        id = 0")
            lines.append("        h = 0")
            lines.append("        gap3 = 32")
            lines.append("        rate = 250")
            lines.append("        rpm = 300")
            lines.append("        interleave = 2")
            lines.append("        cskew = 4")
            lines.append("    end")
        
        return lines
    
    def _generate_pc_tracks(self) -> List[str]:
        """Generate PC-compatible track definitions"""
        lines = []
        lines.append(f"    # PC Standard Format")
        lines.append("    tracks * ibm.mfm")
        lines.append(f"        secs = {self.geometry.sectors_per_track}")
        lines.append(f"        bps = {self.geometry.bytes_per_sector}")
        lines.append("        id = 1")
        lines.append("        h = 0")
        
        # Set appropriate gap3 based on sector size and count
        if self.geometry.bytes_per_sector == 512:
            if self.geometry.sectors_per_track <= 9:
                gap3 = 84
            elif self.geometry.sectors_per_track <= 18:
                gap3 = 108
            else:
                gap3 = 84
        else:
            gap3 = 32
        
        lines.append(f"        gap3 = {gap3}")
        
        # Set rate based on track count and density
        if self.geometry.cylinders <= 40:
            rate = 250  # DD
        else:
            rate = 500 if self.geometry.sectors_per_track > 18 else 250
        
        lines.append(f"        rate = {rate}")
        lines.append("        rpm = 300")
        lines.append("        interleave = 1")
        lines.append("        cskew = 1")
        lines.append("    end")
        
        return lines
    
    def _generate_variable_tracks(self) -> List[str]:
        """Generate variable track definitions for disks with different sector counts per track"""
        lines = []
        lines.append("    # Variable Format - different sector counts per track")
        lines.append("")
        
        # Group tracks by sector count
        track_groups = {}
        for track_id, sector_count in self.geometry.sector_counts.items():
            if sector_count not in track_groups:
                track_groups[sector_count] = []
            track_groups[sector_count].append(track_id[0])  # cylinder number
        
        # Generate definitions for each group
        for sector_count, cylinders in sorted(track_groups.items()):
            if not cylinders or sector_count == 0:
                continue
            
            # Find common sector size for this group (use default if not available)
            sector_size = self.geometry.bytes_per_sector
            
            # Create track range
            track_range = self._format_cylinder_range(cylinders)
            
            lines.append(f"    # Cylinders {track_range}: {sector_count} sectors")
            lines.append(f"    tracks {track_range} ibm.mfm")
            lines.append(f"        secs = {sector_count}")
            lines.append(f"        bps = {sector_size}")
            lines.append("        id = 0")
            lines.append("        h = 0")
            lines.append("        gap3 = 32")
            lines.append("        rate = 250")
            lines.append("        rpm = 300")
            lines.append("        interleave = 2")
            lines.append("        cskew = 4")
            lines.append("    end")
            lines.append("")
        
        return lines
    
    def _generate_custom_tracks(self) -> List[str]:
        """Generate custom track definitions for unknown/special formats"""
        lines = []
        lines.append(f"    # Custom Format - {self.geometry.type}")
        
        if self.geometry.type == "akai":
            lines.append("    # Note: AKAI format with phantom sectors")
            lines.append("    # Normalized to remove phantom sectors")
        
        lines.append("")
        lines.append("    tracks * ibm.mfm")
        lines.append(f"        secs = {self.geometry.sectors_per_track}")
        lines.append(f"        bps = {self.geometry.bytes_per_sector}")
        lines.append("        id = 0")
        lines.append("        h = 0")
        
        # Use conservative settings for unknown formats
        lines.append("        gap3 = 32")
        lines.append("        rate = 250")
        lines.append("        rpm = 300")
        lines.append("        interleave = 1")
        lines.append("        cskew = 1")
        lines.append("    end")
        
        return lines
    
    def _format_cylinder_range(self, cylinders: List[int]) -> str:
        """Format cylinder list as compact range notation"""
        if not cylinders:
            return "*"
        
        cylinders = sorted(set(cylinders))
        
        if len(cylinders) == 1:
            return str(cylinders[0])
        
        # Check if it's a continuous range
        if cylinders == list(range(cylinders[0], cylinders[-1] + 1)):
            return f"{cylinders[0]}-{cylinders[-1]}"
        
        # Otherwise, list individual cylinders (up to reasonable limit)
        if len(cylinders) <= 10:
            return ",".join(map(str, cylinders))
        else:
            # For large lists, just use range of first to last
            return f"{cylinders[0]}-{cylinders[-1]}"

def generate_def_from_geometry(geometry: GeometryInfo, source_filename: str = "", 
                              options: DefGenerationOptions = None) -> str:
    """
    Convenience function to generate .def content from geometry
    """
    generator = DefGenerator(geometry, source_filename, options)
    return generator.generate_def_content()

def save_def_file(geometry: GeometryInfo, output_path: str, source_filename: str = "",
                  options: DefGenerationOptions = None) -> bool:
    """
    Convenience function to save .def file from geometry
    """
    generator = DefGenerator(geometry, source_filename, options)
    return generator.save_def_file(output_path)
