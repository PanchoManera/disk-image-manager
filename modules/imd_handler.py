"""
IMD Handler - ImageDisk file format reader
Based on imd2raw.c reference implementation
"""

import struct
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

@dataclass
class IMDTrack:
    mode: int           # 0-5: recording mode
    cylinder: int       # Physical cylinder
    head: int          # Physical head (0-1)
    sector_count: int  # Number of sectors
    sector_size: int   # Sector size in bytes
    sector_map: List[int]  # Sector numbering map
    sector_data: Dict[int, bytes]  # Sector number -> data
    bad_sectors: List[int]  # List of bad/unavailable sector numbers

@dataclass 
class IMDImage:
    header: str         # ASCII header with version/date/time
    comment: str        # Comment text
    tracks: List[IMDTrack]  # Track data

class IMDHandler:
    """Handler for reading ImageDisk (.IMD) files"""
    
    # Mode lookup table from imd2raw.c
    MODE_NAMES = ["500K FM", "300K FM", "250K FM", "500K MFM", "300K MFM", "250K MFM"]
    
    # Sector size lookup (index -> bytes)
    SECTOR_SIZES = {
        0: 128,
        1: 256, 
        2: 512,
        3: 1024,
        4: 2048,
        5: 4096,
        6: 8192
    }
    
    def __init__(self, imd_path: str):
        self.imd_path = imd_path
        self.file_handle = None
        
    def __enter__(self):
        self.file_handle = open(self.imd_path, 'rb')
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.file_handle:
            self.file_handle.close()
    
    def read_imd(self) -> IMDImage:
        """Read and parse an IMD file"""
        if not self.file_handle:
            raise ValueError("File not opened")
        
        self.file_handle.seek(0)
        
        # Check IMD signature
        signature = self.file_handle.read(3)
        if signature != b'IMD':
            raise ValueError("File doesn't start with 'IMD' signature")
        
        # Read header and comment
        header, comment = self._read_header_and_comment()
        
        # Read all tracks
        tracks = []
        while True:
            track = self._read_track()
            if track is None:
                break
            tracks.append(track)
        
        return IMDImage(header=header, comment=comment, tracks=tracks)
    
    def _read_header_and_comment(self) -> Tuple[str, str]:
        """Read ASCII header and comment terminated by 0x1a"""
        header_comment = b''
        
        while True:
            byte = self.file_handle.read(1)
            if not byte:
                break
            if byte[0] == 0x1a:  # End of comment marker
                break
            header_comment += byte
        
        # Split header and comment (first line is header)
        try:
            text = header_comment.decode('ascii', errors='ignore')
            lines = text.split('\n', 1)
            header = lines[0] if lines else ""
            comment = lines[1] if len(lines) > 1 else ""
            return header.strip(), comment.strip()
        except:
            return "", ""
    
    def _read_track(self) -> Optional[IMDTrack]:
        """Read a single track from the IMD file"""
        # Read track header (5 bytes)
        mode_byte = self.file_handle.read(1)
        if not mode_byte:
            return None  # EOF
            
        mode = mode_byte[0]
        if mode > 6:
            raise ValueError(f"Invalid mode {mode}, stream out of sync")
        
        cylinder = self._read_byte()
        if cylinder > 80:
            raise ValueError(f"Invalid cylinder {cylinder}, stream out of sync")
        
        head_flags = self._read_byte()
        head = head_flags & 0x0f
        head_flags = head_flags & 0xf0
        
        if head > 1:
            raise ValueError(f"Invalid head {head}, stream out of sync")
        
        sector_count = self._read_byte()
        sector_size_code = self._read_byte()
        
        if sector_size_code not in self.SECTOR_SIZES:
            raise ValueError(f"Unknown sector size indicator {sector_size_code}")
        
        sector_size = self.SECTOR_SIZES[sector_size_code]
        
        # Read sector numbering map
        sector_map = []
        for i in range(sector_count):
            sector_map.append(self._read_byte())
        
        # Read optional cylinder map (if head_flags & 0x40)
        if head_flags & 0x40:
            for i in range(sector_count):
                self._read_byte()  # Discard cylinder map
        
        # Read optional head map (if head_flags & 0x80) 
        if head_flags & 0x80:
            for i in range(sector_count):
                self._read_byte()  # Discard head map
        
        # Read sector data records
        sector_data = {}
        bad_sectors = []
        
        for i in range(sector_count):
            sector_num = sector_map[i]
            data_type = self._read_byte()
            
            data = self._read_sector_data(data_type, sector_size)
            if data is None:
                bad_sectors.append(sector_num)
                # Fill with 0xE5 for bad sectors
                data = bytes([0xE5] * sector_size)
            
            sector_data[sector_num] = data
        
        return IMDTrack(
            mode=mode,
            cylinder=cylinder, 
            head=head,
            sector_count=sector_count,
            sector_size=sector_size,
            sector_map=sector_map,
            sector_data=sector_data,
            bad_sectors=bad_sectors
        )
    
    def _read_sector_data(self, data_type: int, sector_size: int) -> Optional[bytes]:
        """Read sector data based on type"""
        if data_type == 0:  # Sector data unavailable
            return None
        elif data_type == 1:  # Normal data
            return self.file_handle.read(sector_size)
        elif data_type == 2:  # Compressed - all bytes are same value
            fill_value = self._read_byte()
            return bytes([fill_value] * sector_size)
        elif data_type == 3:  # Deleted data address mark
            return self.file_handle.read(sector_size) 
        elif data_type == 4:  # Compressed deleted data
            fill_value = self._read_byte()
            return bytes([fill_value] * sector_size)
        elif data_type == 5:  # Deleted address marks
            return None
        elif data_type == 6:  # Compressed deleted address marks
            fill_value = self._read_byte()
            return bytes([fill_value] * sector_size)
        elif data_type == 7:  # Bad sector
            return None
        elif data_type == 8:  # Compressed bad sector
            fill_value = self._read_byte()
            return bytes([fill_value] * sector_size)
        else:
            raise ValueError(f"Unknown sector data type: {data_type}")
    
    def _read_byte(self) -> int:
        """Read a single byte from file"""
        byte = self.file_handle.read(1)
        if not byte:
            raise EOFError("Unexpected end of file")
        return byte[0]

class IMD2IMGConverter:
    """Converter from IMD to IMG format"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
    
    def convert(self, imd_path: str, img_path: str) -> bool:
        """Convert IMD file to IMG file"""
        try:
            with IMDHandler(imd_path) as imd_handler:
                imd_image = imd_handler.read_imd()
            
            if self.verbose:
                print(f"IMD Header: {imd_image.header}")
                print(f"Comment: {imd_image.comment}")
                print(f"Tracks: {len(imd_image.tracks)}")
            
            # Convert to linear IMG format
            with open(img_path, 'wb') as img_file:
                tracks_written = 0
                
                for track in imd_image.tracks:
                    # Sort sectors to handle skew correctly (key fix from imd2raw.c)
                    sorted_sectors = sorted(track.sector_map)
                    
                    if self.verbose:
                        print(f"Cyl {track.cylinder:02d} Hd {track.head} {track.sector_size:4d} ", end="")
                        
                        # Show sector status
                        for i, sector_num in enumerate(track.sector_map):
                            if sector_num in track.bad_sectors:
                                print("X", end="")
                            else:
                                print(".", end="")
                        
                        # Show sector order
                        for sector_num in track.sector_map:
                            print(f" {sector_num:2d}", end="")
                        print()
                    
                    # Write sectors in sorted order to handle skew
                    for sector_num in sorted_sectors:
                        if sector_num in track.sector_data:
                            img_file.write(track.sector_data[sector_num])
                        else:
                            # Fill missing sectors with 0xE5
                            img_file.write(bytes([0xE5] * track.sector_size))
                    
                    tracks_written += 1
                
                if self.verbose:
                    print(f"\\nConversion completed: {tracks_written} tracks written")
            
            return True
            
        except Exception as e:
            print(f"Error converting {imd_path}: {e}")
            return False

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python imd_handler.py <input.imd> <output.img>")
        sys.exit(1)
    
    imd_path = sys.argv[1]
    img_path = sys.argv[2]
    
    converter = IMD2IMGConverter(verbose=True)
    success = converter.convert(imd_path, img_path)
    
    if success:
        print(f"Successfully converted {imd_path} to {img_path}")
        sys.exit(0)
    else:
        print(f"Failed to convert {imd_path}")
        sys.exit(1)
