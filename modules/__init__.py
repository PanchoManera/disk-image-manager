"""
TD0 Converter Modules Package

This package contains the core modules for TD0 conversion and FAT handling.
"""

# Import main classes for easier access
from .td0_converter_lib import TD0Converter, ConversionOptions, ConversionResult
from .fat_lister import FATHandler, FileEntry
from .geometry_detector import GeometryDetector, GeometryDetectorLegacy, GeometryInfo
from .def_generator import DefGenerator, DefGenerationOptions

__all__ = [
    'TD0Converter',
    'ConversionOptions', 
    'ConversionResult',
    'FATHandler',
    'FileEntry',
    'GeometryDetector',
    'GeometryDetectorLegacy',
    'GeometryInfo',
    'DefGenerator',
    'DefGenerationOptions'
]
