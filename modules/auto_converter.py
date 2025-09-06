#!/usr/bin/env python3
"""
Auto Converter - Automatic conversion of disk image formats
Handles TD0 -> IMG conversion automatically when needed
"""

import os
import tempfile
import shutil
from typing import Optional, Tuple
from pathlib import Path

class AutoConverter:
    """Automatic disk image format converter"""
    
    def __init__(self):
        self.temp_files = []  # Track temp files for cleanup
    
    def prepare_image_for_analysis(self, image_path: str) -> Tuple[str, bool]:
        """
        Prepare image for analysis, converting if necessary.
        
        Returns:
            (working_path, is_temp_file)
            - working_path: Path to use for analysis (original or converted)
            - is_temp_file: True if working_path is a temporary file that should be cleaned up
        """
        path = Path(image_path)
        
        # Check if conversion is needed
        if path.suffix.lower() == '.td0':
            return self._convert_td0_to_img(image_path)
        elif path.suffix.lower() == '.imd':
            return self._convert_imd_to_img(image_path)
        else:
            # No conversion needed
            return image_path, False
    
    def _convert_td0_to_img(self, td0_path: str) -> Tuple[str, bool]:
        """Convert TD0 to temporary IMG file"""
        try:
            # Import TD0 converter
            from .td0_converter_lib import FixedTD0Converter, ConversionOptions
            
            # Create temporary IMG file
            temp_fd, temp_path = tempfile.mkstemp(suffix='.img', prefix='converted_')
            os.close(temp_fd)
            
            # Configure conversion options respecting original geometry
            options = ConversionOptions(
                warn_only=True,
                force_hp150=False,
                fix_boot_sector=True,
                verbose=False
            )
            
            # Convert TD0 to IMG
            converter = FixedTD0Converter(options)
            result = converter.convert(td0_path, temp_path)
            
            if result.success:
                self.temp_files.append(temp_path)
                print(f"[INFO] Auto-converted TD0 to temporary IMG: {os.path.basename(temp_path)}")
                return temp_path, True
            else:
                # Clean up failed temp file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise Exception(f"TD0 conversion failed: {result.error_message}")
                
        except ImportError:
            raise Exception("TD0 converter not available")
        except Exception as e:
            raise Exception(f"Failed to convert TD0: {e}")
    
    def _convert_imd_to_img(self, imd_path: str) -> Tuple[str, bool]:
        """Convert IMD to temporary IMG file"""
        try:
            # Import IMD converter
            from .imd_handler import IMD2IMGConverter
            
            # Create temporary IMG file
            temp_fd, temp_path = tempfile.mkstemp(suffix='.img', prefix='converted_')
            os.close(temp_fd)
            
            # Convert IMD to IMG
            converter = IMD2IMGConverter(verbose=False)
            success = converter.convert(imd_path, temp_path)
            
            if success:
                self.temp_files.append(temp_path)
                print(f"[INFO] Auto-converted IMD to temporary IMG: {os.path.basename(temp_path)}")
                return temp_path, True
            else:
                # Clean up failed temp file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise Exception("IMD conversion failed")
                
        except ImportError:
            raise Exception("IMD converter not available")
        except Exception as e:
            raise Exception(f"Failed to convert IMD: {e}")
    
    def convert_for_download(self, image_path: str, target_format: str, output_path: str) -> bool:
        """
        Convert image to specified format for download.
        
        Args:
            image_path: Source image path
            target_format: 'img', 'td0', 'def'
            output_path: Where to save converted file
            
        Returns:
            True if conversion succeeded
        """
        try:
            if target_format.lower() == 'img':
                return self._convert_any_to_img(image_path, output_path)
            elif target_format.lower() == 'def':
                return self._create_def_file(image_path, output_path)
            else:
                raise ValueError(f"Unsupported target format: {target_format}")
        except Exception as e:
            print(f"[ERROR] Conversion to {target_format} failed: {e}")
            return False
    
    def _convert_any_to_img(self, source_path: str, output_path: str) -> bool:
        """Convert any supported format to IMG"""
        try:
            # Prepare source (may involve conversion)
            working_path, is_temp = self.prepare_image_for_analysis(source_path)
            
            # If it's already IMG or was converted to IMG, just copy
            if working_path != source_path or Path(source_path).suffix.lower() in ['.td0', '.imd']:
                shutil.copy2(working_path, output_path)
                return True
            else:
                # Direct copy for IMG files
                shutil.copy2(source_path, output_path)
                return True
                
        except Exception as e:
            print(f"[ERROR] Failed to convert to IMG: {e}")
            return False
    
    def _create_def_file(self, source_path: str, output_path: str) -> bool:
        """Create DEF file from source image"""
        try:
            # Prepare source (may involve conversion to IMG)
            working_path, is_temp = self.prepare_image_for_analysis(source_path)
            
            # Import necessary modules
            from .geometry_detector import GeometryDetector
            from .def_generator import DefGenerator, DefGenerationOptions
            
            # Detect geometry and create DEF
            geometry = GeometryDetector().detect_from_file(working_path)
            options = DefGenerationOptions()
            generator = DefGenerator(geometry, working_path, options)
            
            return generator.save_def_file(output_path)
            
        except Exception as e:
            print(f"[ERROR] Failed to create DEF file: {e}")
            return False
    
    def cleanup(self):
        """Clean up any temporary files created during conversion"""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    print(f"[INFO] Cleaned up temporary file: {os.path.basename(temp_file)}")
            except Exception as e:
                print(f"[WARN] Could not clean up {temp_file}: {e}")
        
        self.temp_files.clear()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

# Enhanced Generic Disk Handler with auto-conversion
class EnhancedGenericDiskHandler:
    """Enhanced generic disk handler with automatic format conversion"""
    
    def __init__(self, image_path: str):
        self.original_path = image_path
        self.auto_converter = AutoConverter()
        
        # Prepare image for analysis (convert if needed)
        self.working_path, self.is_converted = self.auto_converter.prepare_image_for_analysis(image_path)
        
        # Initialize the actual disk handler with working path
        from .generic_disk_handler import GenericDiskHandler
        self._handler = GenericDiskHandler(self.working_path)
    
    def list_files(self):
        """List files in the image"""
        return self._handler.list_files()
    
    def get_disk_info(self):
        """Get disk information"""
        info = self._handler.get_disk_info()
        # Add conversion info
        info['original_format'] = Path(self.original_path).suffix.upper()
        info['was_converted'] = self.is_converted
        return info
    
    def get_format_info(self):
        """Get format information"""
        format_info = self._handler.get_format_info()
        # Add source format info
        format_info['source_format'] = Path(self.original_path).suffix.upper()
        return format_info
    
    def extract_files(self, output_dir: str, create_dir: bool = True):
        """Extract files from the image"""
        return self._handler.extract_files(output_dir, create_dir)
    
    def close(self):
        """Close handlers and cleanup"""
        if hasattr(self, '_handler'):
            self._handler.close()
        self.auto_converter.cleanup()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
