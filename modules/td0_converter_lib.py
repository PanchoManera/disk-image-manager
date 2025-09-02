#!/usr/bin/env python3
"""
TD0 to IMG Converter Library - Unified Version
Combines functionality from td0_converter_lib.py, td0_converter_lib_enhanced.py, and td0_converter_lib_fixed.py
This unified module provides all TD0 conversion capabilities in a single file.
"""

import sys
import os
import struct
import time
from typing import Dict, List, Optional, Tuple, Any, Callable
from enum import Enum
from dataclasses import dataclass, field

# Import base classes
from .def_generator import DefGenerator, DefGenerationOptions

# Constantes LZSS (basadas en td0_lzss.c)
SBSIZE = 4096           # Size of Ring buffer
LASIZE = 60             # Size of Look-ahead buffer
THRESHOLD = 2           # Minimum match for compress
N_CHAR = 256 - THRESHOLD + LASIZE  # Character code
TSIZE = N_CHAR * 2 - 1  # Size of table
ROOT = TSIZE - 1        # Root position
MAX_FREQ = 0x8000       # Update when cumulative frequency reaches this value

# Tablas de decodificación Huffman (de td0_lzss.c)
d_code_lzss = [
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01,
    0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02,
    0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03,
    0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x05, 0x05, 0x05, 0x05, 0x05, 0x05, 0x05, 0x05,
    0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07,
    0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x09, 0x09, 0x09, 0x09, 0x09, 0x09, 0x09, 0x09,
    0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0B, 0x0B, 0x0B, 0x0B, 0x0B, 0x0B, 0x0B, 0x0B,
    0x0C, 0x0C, 0x0C, 0x0C, 0x0D, 0x0D, 0x0D, 0x0D, 0x0E, 0x0E, 0x0E, 0x0E, 0x0F, 0x0F, 0x0F, 0x0F,
    0x10, 0x10, 0x10, 0x10, 0x11, 0x11, 0x11, 0x11, 0x12, 0x12, 0x12, 0x12, 0x13, 0x13, 0x13, 0x13,
    0x14, 0x14, 0x14, 0x14, 0x15, 0x15, 0x15, 0x15, 0x16, 0x16, 0x16, 0x16, 0x17, 0x17, 0x17, 0x17,
    0x18, 0x18, 0x19, 0x19, 0x1A, 0x1A, 0x1B, 0x1B, 0x1C, 0x1C, 0x1D, 0x1D, 0x1E, 0x1E, 0x1F, 0x1F,
    0x20, 0x20, 0x21, 0x21, 0x22, 0x22, 0x23, 0x23, 0x24, 0x24, 0x25, 0x25, 0x26, 0x26, 0x27, 0x27,
    0x28, 0x28, 0x29, 0x29, 0x2A, 0x2A, 0x2B, 0x2B, 0x2C, 0x2C, 0x2D, 0x2D, 0x2E, 0x2E, 0x2F, 0x2F,
    0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x3B, 0x3C, 0x3D, 0x3E, 0x3F
]

d_len_lzss = [2, 2, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 6, 6, 6, 7]

class TD0Decompressor:
    def __init__(self):
        self.parent = [0] * (TSIZE + N_CHAR)
        self.son = [0] * TSIZE
        self.freq = [0] * (TSIZE + 1)
        self.bits = 0
        self.bitbuff = 0
        self.gb_check = 0
        self.gb_r = 0
        self.gb_i = 0
        self.gb_j = 0
        self.gb_k = 0
        self.gb_state = 0
        self.eof = False
        self.ring_buff = [0] * (SBSIZE + LASIZE - 1)
        self.input_data = None
        self.input_pos = 0
        
    def init_decompress(self):
        """Inicializa el descompresor"""
        self.parent = [0] * (TSIZE + N_CHAR)
        self.son = [0] * TSIZE
        self.freq = [0] * (TSIZE + 1)
        self.bits = 0
        self.bitbuff = 0
        self.gb_check = 0
        self.gb_r = 0
        self.gb_i = 0
        self.gb_j = 0
        self.gb_k = 0
        self.gb_state = 0
        self.eof = False
        self.ring_buff = [0x20] * (SBSIZE + LASIZE - 1)  # Preset to spaces
        
        # Inicializar árboles
        j = 0
        for i in range(N_CHAR):
            self.freq[i] = 1
            self.son[i] = i + TSIZE
            self.parent[i + TSIZE] = i
            
        i = N_CHAR
        while i <= ROOT:
            self.freq[i] = self.freq[j] + self.freq[j + 1]
            self.son[i] = j
            self.parent[j] = self.parent[j + 1] = i
            i += 1
            j += 2
            
        self.freq[TSIZE] = 0xFFFF
        self.parent[ROOT] = 0
        self.gb_r = SBSIZE - LASIZE
        
    def get_char(self):
        """Obtiene un byte del flujo de entrada"""
        if self.eof:
            return 0
        if self.input_pos >= len(self.input_data):
            self.eof = True
            return 0
        c = self.input_data[self.input_pos]
        self.input_pos += 1
        return c
        
    def get_bit(self):
        """Obtiene un bit del flujo de entrada"""
        if self.bits == 0:
            self.bitbuff |= self.get_char() << 8
            self.bits = 7
        else:
            self.bits -= 1
            
        t = self.bitbuff >> 15
        self.bitbuff = (self.bitbuff << 1) & 0xFFFF
        return t
        
    def get_byte(self):
        """Obtiene un byte del flujo de entrada (no alineado a bits)"""
        if self.bits < 8:
            self.bitbuff |= self.get_char() << (8 - self.bits)
        else:
            self.bits -= 8
            
        t = self.bitbuff >> 8
        self.bitbuff = (self.bitbuff << 8) & 0xFFFF
        return t
        
    def update_freq(self, c):
        """Actualiza la frecuencia en el árbol"""
        if self.freq[ROOT] == MAX_FREQ:
            # Reconstruir árbol
            j = 0
            for i in range(TSIZE):
                if self.son[i] >= TSIZE:
                    self.freq[j] = (self.freq[i] + 1) // 2
                    self.son[j] = self.son[i]
                    j += 1
                    
            # Reconstruir conexiones
            i = 0
            j = N_CHAR
            while j < TSIZE:
                k = i + 1
                f = self.freq[j] = self.freq[i] + self.freq[k]
                
                # Encontrar posición correcta
                k = j - 1
                while k >= 0 and f < self.freq[k]:
                    k -= 1
                k += 1
                
                # Mover elementos
                for idx in range(j, k, -1):
                    self.freq[idx] = self.freq[idx - 1]
                    self.son[idx] = self.son[idx - 1]
                    
                self.freq[k] = f
                self.son[k] = i
                i += 2
                j += 1
                
            # Conectar nodos padre
            for i in range(TSIZE):
                k = self.son[i]
                if k >= TSIZE:
                    self.parent[k] = i
                else:
                    self.parent[k] = self.parent[k + 1] = i
                    
        c = self.parent[c + TSIZE]
        while c:
            k = self.freq[c] + 1
            self.freq[c] = k
            
            # Intercambiar nodos si es necesario
            l = c + 1
            if l < len(self.freq) and k > self.freq[l]:
                while l < len(self.freq) and k > self.freq[l]:
                    l += 1
                l -= 1
                
                self.freq[c], self.freq[l] = self.freq[l], k
                
                i = self.son[c]
                self.parent[i] = l
                if i < TSIZE:
                    self.parent[i + 1] = l
                    
                j = self.son[l]
                self.parent[j] = c
                self.son[l] = i
                if j < TSIZE:
                    self.parent[j + 1] = c
                self.son[c] = j
                c = l
                
            c = self.parent[c]
            
    def decode_char(self):
        """Decodifica un carácter del árbol"""
        c = ROOT
        while c < TSIZE:
            c = self.son[c] + self.get_bit()
            
        c -= TSIZE
        self.update_freq(c)
        return c
        
    def decode_position(self):
        """Decodifica una posición comprimida"""
        i = self.get_byte()
        c = d_code_lzss[i] << 6
        
        j = d_len_lzss[i >> 4]
        j -= 1
        while j > 0:
            i = (i << 1) | self.get_bit()
            j -= 1
            
        return (i & 0x3F) | c
        
    def lzss_getbyte(self):
        """Obtiene un byte descomprimido usando LZSS"""
        self.gb_check -= 1
        
        while True:
            if self.eof:
                return -1
                
            if self.gb_state == 0:  # No en medio de una cadena
                c = self.decode_char()
                if c < 256:  # Datos directos
                    self.ring_buff[self.gb_r] = c
                    self.gb_r = (self.gb_r + 1) & (SBSIZE - 1)
                    return c
                    
                # Comenzar extracción de cadena comprimida
                self.gb_state = 255
                self.gb_i = (self.gb_r - self.decode_position() - 1) & (SBSIZE - 1)
                self.gb_j = c - 255 + THRESHOLD
                self.gb_k = 0
                
            if self.gb_k < self.gb_j:  # Extraer cadena comprimida
                self.ring_buff[self.gb_r] = self.ring_buff[(self.gb_k + self.gb_i) & (SBSIZE - 1)]
                c = self.ring_buff[self.gb_r]
                self.gb_r = (self.gb_r + 1) & (SBSIZE - 1)
                self.gb_k += 1
                return c
                
            self.gb_state = 0  # Volver a estado no-cadena
            
    def decompress(self, compressed_data):
        """Descomprime datos LZSS"""
        self.input_data = compressed_data
        self.input_pos = 0
        self.init_decompress()
        
        result = []
        while not self.eof:
            byte = self.lzss_getbyte()
            if byte == -1:
                break
            result.append(byte)
            
        return bytes(result)

class TD0Reader:
    def __init__(self, filename):
        self.filename = filename
        self.data = None
        self.pos = 0
        self.decompressor = TD0Decompressor()
        
        with open(filename, 'rb') as f:
            self.data = f.read()
            
    def read_byte(self):
        if self.pos >= len(self.data):
            return 0
        b = self.data[self.pos]
        self.pos += 1
        return b
        
    def read_word(self):
        lo = self.read_byte()
        hi = self.read_byte()
        return lo | (hi << 8)
        
    def read_bytes(self, count):
        result = self.data[self.pos:self.pos + count]
        self.pos += count
        return result
        
    def parse_header(self):
        """Parsea el header del archivo TD0"""
        header = {}
        
        # Signature (2 bytes)
        signature = self.read_bytes(2)
        header['signature'] = signature
        header['compressed'] = signature == b'td'  # 'td' = compressed, 'TD' = normal
        
        # Sequence, CheckSequence, Version
        header['sequence'] = self.read_byte()
        header['check_sequence'] = self.read_byte()
        header['version'] = self.read_byte()
        
        # Data rate, Drive type, Stepping
        header['data_rate'] = self.read_byte()
        header['drive_type'] = self.read_byte()
        header['stepping'] = self.read_byte()
        
        # DOS allocation, Sides
        header['dos_allocation'] = self.read_byte()
        header['sides'] = self.read_byte()
        
        # CRC
        header['crc'] = self.read_word()
        
        # Check for comment block
        header['has_comment'] = (header['stepping'] & 0x80) != 0
        
        return header
        
    def parse_comment(self):
        """Parsea el bloque de comentarios si existe"""
        if self.pos >= len(self.data):
            return None
            
        comment = {}
        comment['crc'] = self.read_word()
        comment['length'] = self.read_word()
        comment['year'] = self.read_byte() + 1900
        comment['month'] = self.read_byte()
        comment['day'] = self.read_byte()
        comment['hour'] = self.read_byte()
        comment['minute'] = self.read_byte()
        comment['second'] = self.read_byte()
        
        # Leer datos del comentario
        comment['data'] = self.read_bytes(comment['length'])
        
        return comment
        
    def parse_track(self):
        """Parsea un track header"""
        if self.pos >= len(self.data):
            return None
            
        track = {}
        track['num_sectors'] = self.read_byte()
        
        # 255 indica fin de tracks
        if track['num_sectors'] == 255:
            return None
            
        track['cylinder'] = self.read_byte()
        track['head'] = self.read_byte()
        track['crc'] = self.read_byte()
        
        return track
        
    def parse_sector(self):
        """Parsea un sector header"""
        if self.pos >= len(self.data):
            return None
            
        sector = {}
        sector['cylinder'] = self.read_byte()
        sector['head'] = self.read_byte()
        sector['sector_num'] = self.read_byte()
        sector['size_code'] = self.read_byte()
        sector['flags'] = self.read_byte()
        sector['crc'] = self.read_byte()
        
        # Calcular tamaño real del sector
        size_table = [128, 256, 512, 1024, 2048, 4096, 8192, 16384]
        if sector['size_code'] < len(size_table):
            sector['size'] = size_table[sector['size_code']]
        else:
            sector['size'] = 256  # Default para HP150
            
        return sector
        
    def parse_sector_data(self, sector):
        """Parsea los datos de un sector"""
        if self.pos >= len(self.data):
            return None
            
        # Verificar si tiene datos
        if sector['flags'] & 0x30:  # Bits 4 o 5 set = no data
            return None
            
        data_header = {}
        data_header['size'] = self.read_word()
        data_header['encoding'] = self.read_byte()
        
        # Leer datos según encoding
        raw_data = self.read_bytes(data_header['size'] - 1)
        
        # Decodificar según método
        if data_header['encoding'] == 0:  # Raw data
            return raw_data
        elif data_header['encoding'] == 1:  # Repeated pattern
            return self.decode_pattern(raw_data, sector['size'])
        elif data_header['encoding'] == 2:  # RLE
            return self.decode_rle(raw_data, sector['size'])
        else:
            return raw_data
            
    def decode_pattern(self, data, sector_size):
        """Decodifica patrón repetido"""
        result = bytearray()
        pos = 0
        
        while len(result) < sector_size and pos < len(data):
            if pos + 4 > len(data):
                break
                
            count = struct.unpack('<H', data[pos:pos+2])[0]
            pattern = data[pos+2:pos+4]
            pos += 4
            
            for _ in range(count):
                result.extend(pattern)
                if len(result) >= sector_size:
                    break
                    
        return bytes(result[:sector_size])
        
    def decode_rle(self, data, sector_size):
        """Decodifica RLE"""
        result = bytearray()
        pos = 0
        
        while len(result) < sector_size and pos < len(data):
            if pos >= len(data):
                break
                
            length = data[pos]
            pos += 1
            
            if length == 0:  # Literal block
                if pos >= len(data):
                    break
                literal_len = data[pos]
                pos += 1
                
                if pos + literal_len > len(data):
                    break
                    
                result.extend(data[pos:pos+literal_len])
                pos += literal_len
            else:  # Repeated block
                if pos >= len(data):
                    break
                    
                repeat_count = data[pos]
                pos += 1
                block_len = length * 2
                
                if pos + block_len > len(data):
                    break
                    
                block = data[pos:pos+block_len]
                pos += block_len
                
                for _ in range(repeat_count):
                    result.extend(block)
                    if len(result) >= sector_size:
                        break
                        
        return bytes(result[:sector_size])

class SectorType(Enum):
    NORMAL = 0
    PHANTOM = 1
    SKIPPED = 2
    REPEATED = 3
    AKAI_SPECIAL = 4

class DebugLevel(Enum):
    NONE = 0
    HEADERS = 1
    SECTORS = 2
    BLOCKS = 3
    VERBOSE = 4

@dataclass
class ConversionOptions:
    """Options for TD0 conversion"""
    debug_level: DebugLevel = DebugLevel.NONE
    warn_only: bool = False
    force_hp150: bool = True
    fix_boot_sector: bool = True
    verbose: bool = False
    generate_def: bool = False

@dataclass
class ConversionStats:
    """Statistics from conversion process"""
    sectors_read: int = 0
    sectors_skipped: int = 0
    sectors_repeated: int = 0
    phantom_sectors: int = 0
    crc_errors: int = 0
    warnings: int = 0
    tracks_processed: int = 0
    image_size: int = 0
    conversion_time: float = 0.0

@dataclass
class GeometryInfo:
    """Detected disk geometry information"""
    type: str = "unknown"
    cylinders: int = 0
    heads: int = 0
    sectors_per_track: int = 16
    bytes_per_sector: int = 256
    has_phantom: bool = False
    sector_counts: Dict[Tuple[int, int], int] = field(default_factory=dict)
    sector_sizes: Dict[int, int] = field(default_factory=dict)

@dataclass
class ConversionResult:
    """Result of conversion process"""
    success: bool = False
    error_message: str = ""
    stats: ConversionStats = field(default_factory=ConversionStats)
    geometry: Optional[GeometryInfo] = None
    output_file: str = ""
    def_file: str = ""
    greaseweazle_command: str = ""

class ConversionCallbacks:
    """Callbacks for monitoring conversion progress"""
    def __init__(self):
        self.on_progress: Optional[Callable[[str, int, int], None]] = None
        self.on_debug: Optional[Callable[[DebugLevel, str], None]] = None
        self.on_warning: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_info: Optional[Callable[[str], None]] = None

class CRCCalculator:
    """CRC calculation similar to wteledsk"""
    
    def __init__(self):
        self.crc_table = self._generate_crc_table()
    
    def _generate_crc_table(self) -> List[int]:
        """Generate CRC-16 table"""
        table = []
        for i in range(256):
            crc = i
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
            table.append(crc)
        return table
    
    def calculate_crc(self, data: bytes) -> int:
        """Calculate CRC-16 for data"""
        crc = 0
        for byte in data:
            crc = (crc >> 8) ^ self.crc_table[(crc ^ byte) & 0xFF]
        return crc & 0xFFFF
    
    def verify_header_crc(self, header_data: bytes, expected_crc: int) -> bool:
        """Verify header CRC like wteledsk"""
        calculated = self.calculate_crc(header_data[:10])  # First 10 bytes
        return calculated == expected_crc
    
    def verify_track_crc(self, track_data: bytes, expected_crc: int) -> bool:
        """Verify track CRC (only low byte like wteledsk)"""
        calculated = self.calculate_crc(track_data[:3])  # First 3 bytes
        return (calculated & 0xFF) == expected_crc
    
    def verify_sector_crc(self, sector_data: bytes, expected_crc: int) -> bool:
        """Verify sector data CRC"""
        calculated = self.calculate_crc(sector_data)
        return (calculated & 0xFF) == expected_crc

# Import the geometry detector
from .geometry_detector import GeometryDetectorLegacy

class EnhancedTD0Reader(TD0Reader):
    """Enhanced TD0 Reader with wteledsk-like features"""
    
    def __init__(self, filename: str, options: ConversionOptions, callbacks: ConversionCallbacks):
        super().__init__(filename)
        self.options = options
        self.callbacks = callbacks
        self.crc_calc = CRCCalculator()
        self.geometry_detector = GeometryDetectorLegacy()
        self.stats = ConversionStats()
    
    def log_debug(self, level: DebugLevel, message: str):
        """Debug logging"""
        if self.options.debug_level.value >= level.value:
            if self.callbacks.on_debug:
                self.callbacks.on_debug(level, message)
    
    def log_warning(self, message: str):
        """Warning logging"""
        if self.callbacks.on_warning:
            self.callbacks.on_warning(message)
        self.stats.warnings += 1
    
    def log_error(self, message: str):
        """Error logging"""
        if self.callbacks.on_error:
            self.callbacks.on_error(message)
    
    def log_info(self, message: str):
        """Info logging"""
        if self.callbacks.on_info:
            self.callbacks.on_info(message)
    
    def parse_header_enhanced(self) -> Dict[str, Any]:
        """Enhanced header parsing with CRC verification"""
        self.log_debug(DebugLevel.HEADERS, "Parsing file header...")
        
        header = self.parse_header()
        
        # Verify header CRC
        if self.options.debug_level.value >= DebugLevel.HEADERS.value:
            header_bytes = self.data[:10]  # First 10 bytes
            if not self.crc_calc.verify_header_crc(header_bytes, header['crc']):
                self.log_warning("Header CRC verification failed")
                self.stats.crc_errors += 1
            else:
                self.log_debug(DebugLevel.HEADERS, "Header CRC verified ✓")
        
        # Enhanced header info
        drive_types = {1: "360K", 2: "1.2M", 3: "720K", 4: "1.44M"}
        header['drive_type_name'] = drive_types.get(header['drive_type'], "Unknown")
        
        self.log_debug(DebugLevel.HEADERS, f"Signature: {header['signature']}")
        self.log_debug(DebugLevel.HEADERS, f"Version: {header['version']}")
        self.log_debug(DebugLevel.HEADERS, f"Drive type: {header['drive_type_name']}")
        self.log_debug(DebugLevel.HEADERS, f"Sides: {header['sides']}")
        self.log_debug(DebugLevel.HEADERS, f"Compressed: {header['compressed']}")
        
        return header
    
    def parse_track_enhanced(self) -> Optional[Dict[str, Any]]:
        """Enhanced track parsing with CRC verification"""
        track = self.parse_track()
        if track is None:
            return None
        
        # Verify track CRC
        if self.options.debug_level.value >= DebugLevel.HEADERS.value:
            track_pos = self.pos - 4  # Go back to track header
            track_bytes = self.data[track_pos:track_pos + 3]
            if not self.crc_calc.verify_track_crc(track_bytes, track['crc']):
                self.log_warning(f"Track CRC verification failed for track {track['cylinder']}")
                self.stats.crc_errors += 1
            else:
                self.log_debug(DebugLevel.HEADERS, f"Track {track['cylinder']} CRC verified ✓")
        
        self.log_debug(DebugLevel.HEADERS, 
                      f"Track {track['cylinder']}, Head {track['head']}, Sectors: {track['num_sectors']}")
        
        return track
    
    def classify_sector(self, sector: Dict[str, Any]) -> SectorType:
        """Classify sector type similar to wteledsk"""
        sector_num = sector['sector_num']
        
        # Check for AKAI phantom sectors
        if sector_num & 0x60 == 0x60:
            return SectorType.PHANTOM
        
        # Check for termination sector
        if sector_num == 0x65:
            return SectorType.AKAI_SPECIAL
        
        # Check flags for skipped sectors
        if sector['flags'] & 0x30:
            return SectorType.SKIPPED
        
        return SectorType.NORMAL
    
    def parse_sector_enhanced(self) -> Optional[Dict[str, Any]]:
        """Enhanced sector parsing with classification"""
        sector = self.parse_sector()
        if sector is None:
            return None
        
        # Classify sector
        sector_type = self.classify_sector(sector)
        sector['type'] = sector_type
        
        # Handle special sectors
        if sector_type == SectorType.PHANTOM:
            self.log_debug(DebugLevel.SECTORS, f"Phantom sector 0x{sector['sector_num']:02X}")
            self.stats.phantom_sectors += 1
            return sector
        
        if sector_type == SectorType.AKAI_SPECIAL:
            self.log_debug(DebugLevel.SECTORS, "AKAI termination sector (0x65)")
            return sector
        
        if sector_type == SectorType.SKIPPED:
            self.log_debug(DebugLevel.SECTORS, f"Skipped sector {sector['sector_num']}")
            self.stats.sectors_skipped += 1
            return sector
        
        self.log_debug(DebugLevel.SECTORS, f"Normal sector {sector['sector_num']} (size: {sector['size']})")
        self.stats.sectors_read += 1
        
        return sector
    
    def parse_sector_data_enhanced(self, sector: Dict[str, Any]) -> Optional[bytes]:
        """Enhanced sector data parsing with CRC verification"""
        if sector['type'] in [SectorType.PHANTOM, SectorType.AKAI_SPECIAL]:
            return None
        
        sector_data = self.parse_sector_data(sector)
        if sector_data is None:
            return None
        
        # Verify sector data CRC if available
        if self.options.debug_level.value >= DebugLevel.SECTORS.value and sector['crc'] != 0:
            if not self.crc_calc.verify_sector_crc(sector_data, sector['crc']):
                self.log_warning(f"Sector {sector['sector_num']} CRC verification failed")
                self.stats.crc_errors += 1
            else:
                self.log_debug(DebugLevel.SECTORS, f"Sector {sector['sector_num']} CRC verified ✓")
        
        if self.options.debug_level.value >= DebugLevel.BLOCKS.value:
            self.dump_sector_data(sector_data, sector['sector_num'])
        
        return sector_data
    
    def dump_sector_data(self, data: bytes, sector_num: int):
        """Dump sector data in hex format"""
        dump_lines = []
        dump_lines.append(f"--- Sector {sector_num} Data ({len(data)} bytes) ---")
        for i in range(0, min(len(data), 256), 16):
            hex_part = ' '.join(f"{b:02x}" for b in data[i:i+16])
            ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in data[i:i+16])
            dump_lines.append(f"{i:04x}: {hex_part:<48} {ascii_part}")
        
        self.log_debug(DebugLevel.BLOCKS, "\n".join(dump_lines))
    
    def handle_sector_sequence_errors(self, expected_sector: int, actual_sector: int, 
                                    track_num: int) -> Tuple[bool, str]:
        """Handle sector sequence errors"""
        if expected_sector == actual_sector:
            return True, ""
        
        if expected_sector < actual_sector:
            # Skipped sectors
            skipped_count = actual_sector - expected_sector
            message = f"Skipping {skipped_count} sectors ({expected_sector} through {actual_sector-1}) on track {track_num}"
            
            if self.options.warn_only:
                self.log_warning(message)
                self.stats.sectors_skipped += skipped_count
                return True, f"SKIP:{skipped_count}"
            else:
                self.log_error(f"Sector sequence error: {message}")
                return False, "ERROR"
        
        else:
            # Repeated sector
            message = f"Repeating sector {actual_sector} on track {track_num}"
            
            if self.options.warn_only:
                self.log_warning(message)
                self.stats.sectors_repeated += 1
                return True, f"REPEAT:{actual_sector}"
            else:
                self.log_error(f"Sector sequence error: {message}")
                return False, "ERROR"

# DefGenerator is now imported from def_generator module

class TD0Converter:
    """Main TD0 to HP150 converter class with clean interface"""
    
    def __init__(self, options: ConversionOptions = None, callbacks: ConversionCallbacks = None):
        self.options = options or ConversionOptions()
        self.callbacks = callbacks or ConversionCallbacks()
        self.reader = None
        self.geometry = None
        self.tracks = []
    
    def convert(self, input_file: str, output_file: str) -> ConversionResult:
        """Main conversion method"""
        result = ConversionResult()
        result.output_file = output_file
        start_time = time.time()
        
        try:
            self._log_info(f"Converting {input_file} to {output_file}...")
            
            # Initialize reader
            self.reader = EnhancedTD0Reader(input_file, self.options, self.callbacks)
            
            # Parse header
            header = self.reader.parse_header_enhanced()
            
            # Handle compression
            if header['compressed']:
                self._log_info("Decompressing TD0 file...")
                self.reader.log_debug(DebugLevel.VERBOSE, "Starting decompression...")
                compressed_data = self.reader.data[self.reader.pos:]
                decompressed = self.reader.decompressor.decompress(compressed_data)
                self.reader.data = self.reader.data[:self.reader.pos] + decompressed
                self.reader.log_debug(DebugLevel.VERBOSE, f"Decompressed {len(compressed_data)} -> {len(decompressed)} bytes")
            
            # Parse comment
            if header['has_comment']:
                comment = self.reader.parse_comment()
                if comment:
                    self._log_info(f"Comment: {comment['data'].decode('latin-1', errors='replace')}")
            
            # Parse all tracks
            self.tracks = self._parse_all_tracks()
            
            # Detect geometry
            self.geometry = self.reader.geometry_detector.detect_geometry(self.tracks)
            result.geometry = self.geometry
            
            # Generate image
            success = self._generate_image(output_file)
            
            if not success:
                result.error_message = "Failed to generate image"
                return result
            
            # Generate .def file if requested
            if self.options.generate_def:
                def_filename = self._get_def_filename(output_file)
                
                # Convert legacy geometry to new GeometryInfo format
                from .geometry_detector import GeometryInfo
                geometry_info = GeometryInfo(
                    type=self.geometry.get('type', 'hp150_standard'),
                    cylinders=self.geometry.get('cylinders', 80),
                    heads=self.geometry.get('heads', 1),
                    sectors_per_track=self.geometry.get('sectors_per_track', 16),
                    bytes_per_sector=self.geometry.get('bytes_per_sector', 256),
                    has_phantom=self.geometry.get('has_phantom', False),
                    total_sectors=sum(len(track['sectors']) for track in self.tracks),
                    file_size=0,  # Will be set by generator
                    source_format="td0",
                    sector_counts=self.geometry.get('sector_counts', {}),
                    sector_sizes=self.geometry.get('sector_sizes', {})
                )
                
                options = DefGenerationOptions(
                    normalize_to_hp150=True,
                    include_comments=True,
                    include_source_info=True
                )
                
                def_generator = DefGenerator(geometry_info, input_file, options)
                def_success = def_generator.save_def_file(def_filename)
                
                if def_success:
                    result.def_file = def_filename
                    result.greaseweazle_command = self._generate_greaseweazle_command(output_file, True)
                else:
                    self.reader.log_warning("Failed to generate .def file")
            else:
                result.greaseweazle_command = self._generate_greaseweazle_command(output_file, False)
            
            # Finalize stats
            result.stats = self.reader.stats
            result.stats.conversion_time = time.time() - start_time
            result.stats.tracks_processed = len(self.tracks)
            result.success = True
            
            return result
            
        except Exception as e:
            result.error_message = str(e)
            result.stats = self.reader.stats if self.reader else ConversionStats()
            result.stats.conversion_time = time.time() - start_time
            
            if self.options.verbose:
                import traceback
                result.error_message += "\n" + traceback.format_exc()
            
            return result
    
    def _parse_all_tracks(self) -> List[Dict[str, Any]]:
        """Parse all tracks with enhanced error handling"""
        tracks = []
        track_num = 0
        
        while True:
            track = self.reader.parse_track_enhanced()
            if track is None:
                break
            
            track_data = {
                'cylinder': track['cylinder'],
                'head': track['head'],
                'num_sectors': track['num_sectors'],
                'sectors': {}
            }
            
            # Parse sectors for this track
            expected_sector = 0
            
            for i in range(track['num_sectors']):
                sector = self.reader.parse_sector_enhanced()
                if sector is None:
                    break
                
                # Handle sector sequence
                if sector['type'] == SectorType.NORMAL:
                    success, error_info = self.reader.handle_sector_sequence_errors(
                        expected_sector, sector['sector_num'], track_num
                    )
                    
                    if not success and not self.options.warn_only:
                        self.reader.log_error(f"Stopping due to sector sequence error")
                        break
                
                # Parse sector data
                sector_data = self.reader.parse_sector_data_enhanced(sector)
                
                # Handle special sectors
                if sector['type'] == SectorType.AKAI_SPECIAL:
                    self.reader.log_debug(DebugLevel.VERBOSE, "Early termination due to AKAI END sector")
                    break
                
                if sector['type'] == SectorType.PHANTOM:
                    self.reader.log_debug(DebugLevel.SECTORS, f"Ignoring phantom sector 0x{sector['sector_num']:02X}")
                    continue
                
                # Store sector data
                track_data['sectors'][sector['sector_num']] = sector_data
                
                if sector['type'] == SectorType.NORMAL:
                    expected_sector = sector['sector_num'] + 1
            
            tracks.append(track_data)
            track_num += 1
            
            # Progress callback
            if self.callbacks.on_progress:
                self.callbacks.on_progress(f"Processing track {track_num}", track_num, -1)
        
        return tracks
    
    def _generate_image(self, output_file: str) -> bool:
        """Generate HP150 image with flexible geometry"""
        try:
            # Determine output geometry
            if self.options.force_hp150:
                # Force HP150 standard geometry
                output_geometry = {
                    'sectors_per_track': 16,
                    'bytes_per_sector': 256,
                    'cylinders': self.geometry['cylinders'],
                    'heads': self.geometry['heads']
                }
            else:
                # Use detected geometry
                output_geometry = {
                    'sectors_per_track': self.geometry['sectors_per_track'],
                    'bytes_per_sector': self.geometry['bytes_per_sector'],
                    'cylinders': self.geometry['cylinders'],
                    'heads': self.geometry['heads']
                }
            
            # Calculate image size
            total_sectors = (output_geometry['cylinders'] * 
                           output_geometry['heads'] * 
                           output_geometry['sectors_per_track'])
            image_size = total_sectors * output_geometry['bytes_per_sector']
            
            self._log_info(f"Output geometry: {output_geometry['sectors_per_track']} sectors/track, {output_geometry['bytes_per_sector']} bytes/sector")
            self._log_info(f"Image size: {image_size} bytes ({image_size/1024:.1f} KB)")
            
            # Create image
            image = bytearray(b'\xff' * image_size)
            
            # Fill image with track data
            sectors_written = 0
            sectors_missing = 0
            
            for track in self.tracks:
                for sector_num in range(output_geometry['sectors_per_track']):
                    # Calculate sector position
                    track_offset = ((track['cylinder'] * output_geometry['heads'] + track['head']) * 
                                  output_geometry['sectors_per_track'])
                    sector_offset = (track_offset + sector_num) * output_geometry['bytes_per_sector']
                    
                    if sector_offset + output_geometry['bytes_per_sector'] > len(image):
                        continue
                    
                    # Get sector data
                    sector_data = track['sectors'].get(sector_num)
                    
                    if sector_data is not None:
                        # Adjust sector data size
                        if len(sector_data) > output_geometry['bytes_per_sector']:
                            sector_data = sector_data[:output_geometry['bytes_per_sector']]
                        elif len(sector_data) < output_geometry['bytes_per_sector']:
                            sector_data += b'\xff' * (output_geometry['bytes_per_sector'] - len(sector_data))
                        
                        # Write sector
                        image[sector_offset:sector_offset + output_geometry['bytes_per_sector']] = sector_data
                        sectors_written += 1
                    else:
                        sectors_missing += 1
            
            # Apply HP150 corrections
            if self.options.fix_boot_sector:
                self._fix_boot_sector(image)
            
            # Write image
            with open(output_file, 'wb') as f:
                f.write(image)
            
            self._log_info(f"Image created: {output_file}")
            self._log_info(f"Sectors written: {sectors_written}")
            self._log_info(f"Sectors missing: {sectors_missing}")
            
            # Update stats
            self.reader.stats.image_size = image_size
            
            return True
            
        except Exception as e:
            self.reader.log_error(f"Image generation failed: {e}")
            return False
    
    def _fix_boot_sector(self, image: bytearray):
        """Fix HP150 boot sector"""
        if len(image) < 256:
            return
        
        self._log_info("Checking and fixing boot sector...")
        
        # Check and fix boot signature
        boot_signature = image[254:256]
        if boot_signature != b'\x55\xaa':
            self._log_info(f"Boot signature: {boot_signature.hex()} -> Fixed to 55AA")
            image[254] = 0x55
            image[255] = 0xaa
        else:
            self._log_info("Boot signature correct")
        
        # Check OEM ID
        oem_id = image[3:11]
        if oem_id != b'HP150   ':
            self._log_info(f"OEM ID: {repr(oem_id)} (keeping as-is)")
        else:
            self._log_info("OEM ID correct: HP150")
    
    def _get_def_filename(self, output_file: str) -> str:
        """Generate .def filename based on output file"""
        output_base = os.path.splitext(output_file)[0]
        return f"{output_base}.def"
    
    def _generate_greaseweazle_command(self, output_file: str, has_def: bool) -> str:
        """Generate Greaseweazle command string"""
        base_name = os.path.splitext(os.path.basename(output_file))[0]
        img_file = os.path.basename(output_file)
        
        if has_def:
            # Use generated .def file
            def_file = f"{base_name}.def"
            format_name = base_name
            
            command = f"gw write --drive=0 --diskdefs={def_file} --format=\"{format_name}\" {img_file}"
        else:
            # Use placeholder for manual .def creation
            command = f"gw write --drive=0 --diskdefs=your_disk.def --format=\"your_format\" {img_file}"
        
        return command
    
    def _log_info(self, message: str):
        """Log info message"""
        if self.callbacks.on_info:
            self.callbacks.on_info(message)

# Convenience functions for simple usage
def convert_td0_to_hp150(input_file: str, output_file: str, 
                         options: ConversionOptions = None) -> ConversionResult:
    """Simple convenience function to convert TD0 to HP150"""
    converter = TD0Converter(options)
    return converter.convert(input_file, output_file)

def convert_with_callbacks(input_file: str, output_file: str, 
                          options: ConversionOptions = None,
                          callbacks: ConversionCallbacks = None) -> ConversionResult:
    """Convert with custom callbacks for monitoring"""
    converter = TD0Converter(options, callbacks)
    return converter.convert(input_file, output_file)

# ============================================================================
# Fixed Enhanced Classes - Version with improved error handling
# ============================================================================

class FixedEnhancedTD0Reader(EnhancedTD0Reader):
    """Enhanced TD0 Reader con manejo mejorado de errores de secuencia"""
    
    def handle_sector_sequence_errors(self, expected_sector: int, actual_sector: int, 
                                    track_num: int) -> Tuple[bool, str]:
        """Handle sector sequence errors - versión mejorada que no detiene la conversión"""
        if expected_sector == actual_sector:
            return True, ""
        
        if expected_sector < actual_sector:
            # Sectores saltados
            skipped_count = actual_sector - expected_sector
            message = f"Skipping {skipped_count} sectors ({expected_sector} through {actual_sector-1}) on track {track_num}"
            
            # SIEMPRE continuar, solo reportar como warning o info
            self.log_warning(message) if not self.options.warn_only else self.log_info(f"Sector gap: {message}")
            self.stats.sectors_skipped += skipped_count
            return True, f"SKIP:{skipped_count}"
        
        else:
            # Sector repetido
            message = f"Repeating sector {actual_sector} on track {track_num}"
            
            # SIEMPRE continuar, solo reportar como warning o info
            self.log_warning(message) if not self.options.warn_only else self.log_info(f"Sector repeat: {message}")
            self.stats.sectors_repeated += 1
            return True, f"REPEAT:{actual_sector}"

class FixedTD0Converter:
    """Main TD0 to HP150 converter class con manejo mejorado de errores"""
    
    def __init__(self, options: ConversionOptions = None, callbacks: ConversionCallbacks = None):
        self.options = options or ConversionOptions()
        self.callbacks = callbacks or ConversionCallbacks()
        self.reader = None
        self.geometry = None
        self.tracks = []
    
    def convert(self, input_file: str, output_file: str) -> ConversionResult:
        """Main conversion method - versión mejorada"""
        result = ConversionResult()
        result.output_file = output_file
        start_time = time.time()
        
        try:
            self._log_info(f"Converting {input_file} to {output_file}...")
            
            # Initialize reader con la versión mejorada
            self.reader = FixedEnhancedTD0Reader(input_file, self.options, self.callbacks)
            
            # Parse header
            header = self.reader.parse_header_enhanced()
            
            # Handle compression
            if header['compressed']:
                self._log_info("Decompressing TD0 file...")
                self.reader.log_debug(DebugLevel.VERBOSE, "Starting decompression...")
                compressed_data = self.reader.data[self.reader.pos:]
                decompressed = self.reader.decompressor.decompress(compressed_data)
                self.reader.data = self.reader.data[:self.reader.pos] + decompressed
                self.reader.log_debug(DebugLevel.VERBOSE, f"Decompressed {len(compressed_data)} -> {len(decompressed)} bytes")
            
            # Parse comment
            if header['has_comment']:
                comment = self.reader.parse_comment()
                if comment:
                    self._log_info(f"Comment: {comment['data'].decode('latin-1', errors='replace')}")
            
            # Parse all tracks con manejo mejorado de errores
            self.tracks = self._parse_all_tracks_fixed()
            
            # Detect geometry
            self.geometry = self.reader.geometry_detector.detect_geometry(self.tracks)
            result.geometry = self.geometry
            
            # Generate image
            success = self._generate_image_fixed(output_file)
            
            if not success:
                result.error_message = "Failed to generate image"
                return result
            
            # Generate .def file if requested
            if self.options.generate_def:
                def_filename = self._get_def_filename(output_file)
                
                # Get actual file size of output IMG file
                import os
                if os.path.exists(output_file):
                    img_file_size = os.path.getsize(output_file)
                else:
                    img_file_size = self.reader.stats.image_size
                
                # Convert legacy geometry to new GeometryInfo format
                from .geometry_detector import GeometryInfo
                geometry_info = GeometryInfo(
                    type=self.geometry.get('type', 'hp150_standard'),
                    cylinders=self.geometry.get('cylinders', 80),
                    heads=self.geometry.get('heads', 1),
                    sectors_per_track=self.geometry.get('sectors_per_track', 16),
                    bytes_per_sector=self.geometry.get('bytes_per_sector', 256),
                    has_phantom=self.geometry.get('has_phantom', False),
                    total_sectors=sum(len(track['sectors']) for track in self.tracks),
                    file_size=img_file_size,
                    source_format="td0",
                    sector_counts=self.geometry.get('sector_counts', {}),
                    sector_sizes=self.geometry.get('sector_sizes', {})
                )
                
                # Detectar automáticamente si es HP150
                is_hp150 = (
                    self.geometry.get('type', '').startswith('hp150') or
                    (self.geometry.get('sectors_per_track') == 16 and 
                     self.geometry.get('bytes_per_sector') == 256)
                )
                
                options = DefGenerationOptions(
                    normalize_to_hp150=is_hp150,  # Solo normalizar si realmente es HP150
                    include_comments=True,
                    include_source_info=True
                )
                
                def_generator = DefGenerator(geometry_info, input_file, options)
                def_success = def_generator.save_def_file(def_filename)
                
                if def_success:
                    result.def_file = def_filename
                    result.greaseweazle_command = self._generate_greaseweazle_command(output_file, True)
                else:
                    self.reader.log_warning("Failed to generate .def file")
            else:
                result.greaseweazle_command = self._generate_greaseweazle_command(output_file, False)
            
            # Finalize stats
            result.stats = self.reader.stats
            result.stats.conversion_time = time.time() - start_time
            result.stats.tracks_processed = len(self.tracks)
            result.success = True
            
            return result
            
        except Exception as e:
            result.error_message = str(e)
            result.stats = self.reader.stats if self.reader else ConversionStats()
            result.stats.conversion_time = time.time() - start_time
            
            if self.options.verbose:
                import traceback
                result.error_message += "\n" + traceback.format_exc()
            
            return result
    
    def _parse_all_tracks_fixed(self) -> List[Dict[str, Any]]:
        """Parse all tracks con manejo mejorado de errores - NUNCA se detiene"""
        tracks = []
        track_num = 0
        
        while True:
            track = self.reader.parse_track_enhanced()
            if track is None:
                break
            
            track_data = {
                'cylinder': track['cylinder'],
                'head': track['head'],
                'num_sectors': track['num_sectors'],
                'sectors': {}
            }
            
            # Parse sectors for this track
            expected_sector = 0
            sectors_processed = 0
            
            for i in range(track['num_sectors']):
                sector = self.reader.parse_sector_enhanced()
                if sector is None:
                    break
                
                # Handle sector sequence - SIEMPRE continuar
                if sector['type'] == SectorType.NORMAL:
                    # Solo reportar, no usar para expected_sector logic
                    if expected_sector != sector['sector_num']:
                        success, error_info = self.reader.handle_sector_sequence_errors(
                            expected_sector, sector['sector_num'], track_num
                        )
                    # IGNORAR el resultado 'success' - siempre continuar
                
                # Parse sector data
                sector_data = self.reader.parse_sector_data_enhanced(sector)
                
                # Handle special sectors
                if sector['type'] == SectorType.AKAI_SPECIAL:
                    self.reader.log_debug(DebugLevel.VERBOSE, "Early termination due to AKAI END sector")
                    break
                
                if sector['type'] == SectorType.PHANTOM:
                    self.reader.log_debug(DebugLevel.SECTORS, f"Ignoring phantom sector 0x{sector['sector_num']:02X}")
                    continue
                
                # Store sector data incluso si hay errores de secuencia
                if sector_data is not None:
                    track_data['sectors'][sector['sector_num']] = sector_data
                
                if sector['type'] == SectorType.NORMAL:
                    expected_sector = sector['sector_num'] + 1
                
                sectors_processed += 1
            
            # Agregar track incluso si tuvo errores
            tracks.append(track_data)
            track_num += 1
            
            # Progress callback
            if self.callbacks.on_progress:
                self.callbacks.on_progress(f"Processing track {track_num}", track_num, -1)
        
        return tracks
    
    def _generate_image_fixed(self, output_file: str) -> bool:
        """Generate disk image respecting original geometry"""
        try:
            # Always use detected geometry - no forcing
            output_geometry = {
                'sectors_per_track': self.geometry['sectors_per_track'],
                'bytes_per_sector': self.geometry['bytes_per_sector'],
                'cylinders': self.geometry['cylinders'],
                'heads': self.geometry['heads']
            }
            
            # Calculate image size
            total_sectors = (output_geometry['cylinders'] * 
                           output_geometry['heads'] * 
                           output_geometry['sectors_per_track'])
            image_size = total_sectors * output_geometry['bytes_per_sector']
            
            self._log_info(f"Output geometry: {output_geometry['sectors_per_track']} sectors/track, {output_geometry['bytes_per_sector']} bytes/sector")
            self._log_info(f"Image size: {image_size} bytes ({image_size/1024:.1f} KB)")
            
            # Create image filled with zeros for better compatibility
            image = bytearray(b'\x00' * image_size)
            
            # Fill image with track data - improved handling
            sectors_written = 0
            sectors_missing = 0
            
            # Create mapping of all available sectors
            sector_map = {}
            for track in self.tracks:
                track_key = (track['cylinder'], track['head'])
                sector_map[track_key] = track['sectors']
            
            # First, find and extract boot sector from first track
            boot_sector_data = None
            first_track_sectors = sector_map.get((0, 0), {})
            
            # Look for boot sector in sector 1 (common in DOS disks)
            if 1 in first_track_sectors:
                sector_data = first_track_sectors[1]
                if sector_data and (b'MSDOS' in sector_data or b'FAT' in sector_data):
                    self._log_info(f"Boot sector found in sector 1, size: {len(sector_data)} bytes")
                    
                    # Use sector 1 as boot sector (place at position 0)
                    copy_size = min(len(sector_data), output_geometry['bytes_per_sector'])
                    image[0:copy_size] = sector_data[:copy_size]
                    if copy_size < output_geometry['bytes_per_sector']:
                        image[copy_size:output_geometry['bytes_per_sector']] = b'\x00' * (output_geometry['bytes_per_sector'] - copy_size)
                    
                    boot_sector_data = sector_data
                    self._log_info("Boot sector (from sector 1) placed at position 0")
            
            # Fallback: look for boot sector in sector 0
            elif 0 in first_track_sectors:
                sector_data = first_track_sectors[0]
                if sector_data and (b'MSDOS' in sector_data or b'FAT' in sector_data):
                    self._log_info(f"Boot sector found in sector 0, size: {len(sector_data)} bytes")
                    boot_sector_data = bytearray(output_geometry['bytes_per_sector'])
                    
                    if len(sector_data) >= 3 and sector_data[:3] == b'\xeb\x3c\x90':
                        copy_size = min(len(sector_data), output_geometry['bytes_per_sector'])
                        boot_sector_data[:copy_size] = sector_data[:copy_size]
                    else:
                        boot_sector_data[0:3] = b'\xeb\x3c\x90'
                        copy_size = min(len(sector_data), output_geometry['bytes_per_sector'] - 3)
                        boot_sector_data[3:3+copy_size] = sector_data[:copy_size]
                        self._log_info("Added missing jump instruction to boot sector")
                    
                    image[0:output_geometry['bytes_per_sector']] = boot_sector_data
                    self._log_info("Boot sector placed at position 0")
            
            # Fill image sector by sector
            boot_sector_found = boot_sector_data is not None
            
            for cylinder in range(output_geometry['cylinders']):
                for head in range(output_geometry['heads']):
                    track_key = (cylinder, head)
                    track_sectors = sector_map.get(track_key, {})
                    
                    for sector_num in range(output_geometry['sectors_per_track']):
                        track_offset = ((cylinder * output_geometry['heads'] + head) * 
                                      output_geometry['sectors_per_track'])
                        sector_offset = (track_offset + sector_num) * output_geometry['bytes_per_sector']
                        
                        if sector_offset + output_geometry['bytes_per_sector'] > len(image):
                            continue
                        
                        # Skip sector 0 of first track if we already handled boot sector
                        if sector_num == 0 and cylinder == 0 and head == 0 and boot_sector_found:
                            sectors_written += 1
                            continue
                        
                        # Handle sector mapping for TD0 that starts at sector 1
                        lookup_sector_num = sector_num + 1
                        sector_data = track_sectors.get(lookup_sector_num)
                        
                        if sector_data is not None:
                            if len(sector_data) > output_geometry['bytes_per_sector']:
                                sector_data = sector_data[:output_geometry['bytes_per_sector']]
                            elif len(sector_data) < output_geometry['bytes_per_sector']:
                                sector_data += b'\x00' * (output_geometry['bytes_per_sector'] - len(sector_data))
                            
                            image[sector_offset:sector_offset + output_geometry['bytes_per_sector']] = sector_data
                            sectors_written += 1
                        else:
                            sectors_missing += 1
            
            # Apply corrections
            if self.options.fix_boot_sector:
                self._fix_boot_sector_fixed(image)
            
            # Write image
            with open(output_file, 'wb') as f:
                f.write(image)
            
            self._log_info(f"Image created: {output_file}")
            self._log_info(f"Sectors written: {sectors_written}")
            self._log_info(f"Sectors missing: {sectors_missing}")
            
            self.reader.stats.image_size = image_size
            return True
            
        except Exception as e:
            self.reader.log_error(f"Image generation failed: {e}")
            return False
    
    def _parse_all_tracks_fixed(self) -> List[Dict[str, Any]]:
        """Parse all tracks con manejo mejorado de errores - NUNCA se detiene"""
        tracks = []
        track_num = 0
        
        while True:
            track = self.reader.parse_track_enhanced()
            if track is None:
                break
            
            track_data = {
                'cylinder': track['cylinder'],
                'head': track['head'],
                'num_sectors': track['num_sectors'],
                'sectors': {}
            }
            
            # Parse sectors for this track
            expected_sector = 0
            sectors_processed = 0
            
            for i in range(track['num_sectors']):
                sector = self.reader.parse_sector_enhanced()
                if sector is None:
                    break
                
                # Handle sector sequence - SIEMPRE continuar
                if sector['type'] == SectorType.NORMAL:
                    # Solo reportar, no usar para expected_sector logic
                    if expected_sector != sector['sector_num']:
                        success, error_info = self.reader.handle_sector_sequence_errors(
                            expected_sector, sector['sector_num'], track_num
                        )
                    # IGNORAR el resultado 'success' - siempre continuar
                
                # Parse sector data
                sector_data = self.reader.parse_sector_data_enhanced(sector)
                
                # Handle special sectors
                if sector['type'] == SectorType.AKAI_SPECIAL:
                    self.reader.log_debug(DebugLevel.VERBOSE, "Early termination due to AKAI END sector")
                    break
                
                if sector['type'] == SectorType.PHANTOM:
                    self.reader.log_debug(DebugLevel.SECTORS, f"Ignoring phantom sector 0x{sector['sector_num']:02X}")
                    continue
                
                # Store sector data incluso si hay errores de secuencia
                if sector_data is not None:
                    track_data['sectors'][sector['sector_num']] = sector_data
                
                if sector['type'] == SectorType.NORMAL:
                    expected_sector = sector['sector_num'] + 1
                
                sectors_processed += 1
            
            # Agregar track incluso si tuvo errores
            tracks.append(track_data)
            track_num += 1
            
            # Progress callback
            if self.callbacks.on_progress:
                self.callbacks.on_progress(f"Processing track {track_num}", track_num, -1)
        
        return tracks
    
    def _fix_boot_sector_fixed(self, image: bytearray):
        """Fix HP150 boot sector - enhanced version"""
        if len(image) < 256:
            return
        
        self._log_info("Checking and fixing boot sector...")
        
        # Check and fix boot signature
        boot_signature = image[254:256]
        if boot_signature != b'\x55\xaa':
            self._log_info(f"Boot signature: {boot_signature.hex()} -> Fixed to 55AA")
            image[254] = 0x55
            image[255] = 0xaa
        else:
            self._log_info("Boot signature correct")
        
        # Check OEM ID
        oem_id = image[3:11]
        if oem_id != b'HP150   ':
            self._log_info(f"OEM ID: {repr(oem_id)} (keeping as-is)")
        else:
            self._log_info("OEM ID correct: HP150")
    
    def _get_def_filename(self, output_file: str) -> str:
        """Generate .def filename based on output file"""
        output_base = os.path.splitext(output_file)[0]
        return f"{output_base}.def"
    
    def _generate_greaseweazle_command(self, output_file: str, has_def: bool) -> str:
        """Generate Greaseweazle command string"""
        base_name = os.path.splitext(os.path.basename(output_file))[0]
        img_file = os.path.basename(output_file)
        
        if has_def:
            # Use generated .def file
            def_file = f"{base_name}.def"
            format_name = base_name
            
            command = f"gw write --drive=0 --diskdefs={def_file} --format=\"{format_name}\" {img_file}"
        else:
            # Use placeholder for manual .def creation
            command = f"gw write --drive=0 --diskdefs=your_disk.def --format=\"your_format\" {img_file}"
        
        return command
    
    def _log_info(self, message: str):
        """Log info message"""
        if self.callbacks.on_info:
            self.callbacks.on_info(message)

# ============================================================================
# Convenience functions for backward compatibility
# ============================================================================

def convert_td0_to_hp150_fixed(input_file: str, output_file: str, 
                               options: ConversionOptions = None) -> ConversionResult:
    """Simple convenience function to convert TD0 to HP150 - versión mejorada"""
    converter = FixedTD0Converter(options)
    return converter.convert(input_file, output_file)

def convert_with_callbacks_fixed(input_file: str, output_file: str, 
                                options: ConversionOptions = None,
                                callbacks: ConversionCallbacks = None) -> ConversionResult:
    """Convert with custom callbacks for monitoring - versión mejorada"""
    converter = FixedTD0Converter(options, callbacks)
    return converter.convert(input_file, output_file)
