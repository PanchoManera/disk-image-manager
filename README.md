# HP150/TD0 Disk Image Manager

A comprehensive suite of tools for managing vintage disk images including TD0 (Teledisk), IMG, and IMD formats. Features both GUI and web interfaces for easy file management and conversion, with specialized support for HP150 systems.

## 📁 Project Structure

```
hp150-td0-manager/
├── td0_converter_gui_unified.py     # Desktop GUI application
├── web_server.py                    # Web interface server
├── td0_to_img_converter.py          # Command line TD0→IMG converter
├── imd2img_converter.py             # Command line IMD→IMG converter
├── img_to_def_converter.py          # Command line IMG→DEF converter
├── list_fat_files.py                # FAT filesystem inspector
├── modules/                         # Core library modules
│   ├── td0_converter_lib.py         # TD0 conversion engine
│   ├── imd_handler.py               # IMD format support
│   ├── auto_converter.py            # Multi-format handler
│   ├── enhanced_format_detector.py  # Intelligent format detection
│   ├── generic_disk_handler.py      # Unified disk operations
│   ├── hp150_fat_handler.py         # HP150 specific support
│   ├── geometry_detector.py         # Disk geometry detection
│   ├── def_generator.py             # Greaseweazle .def generation
│   ├── greaseweazle_reader.py       # Hardware disk reading
│   └── greaseweazle_writer.py       # Hardware disk writing
├── templates/                       # Web interface templates
│   └── index.html                   # Main web UI
├── static/                          # Web static assets
│   └── style.css                    # Web interface styling
├── tools/                           # Analysis utilities
├── batch/                           # Batch processing scripts
├── legacy/                          # Legacy conversion scripts
└── disks/                           # Test disk images (gitignored)
```

## 🖥️ User Interfaces

### Desktop GUI (`td0_converter_gui_unified.py`)

User-friendly desktop application with full functionality:

```bash
python3 td0_converter_gui_unified.py
```

**Features:**
- File upload with drag & drop support
- Real-time sector information display
- File listing with filtering options
- One-click file extraction
- TD0 → IMG and IMD → IMG conversion
- DEF file generation
- Greaseweazle integration (read/write disks)

### Web Interface (`web_server.py`)

Modern web-based interface accessible from any browser:

```bash
python3 web_server.py
# Access at http://localhost:5001
```

**Features:**
- Responsive web design
- Session-based file management
- Real-time processing feedback
- Download converted files
- Support for all formats (TD0, IMG, IMD)
- Batch file extraction as ZIP

## 🚀 Command Line Tools

### 1. TD0 to HP150 Converter (`td0_to_hp150_V3.0_modular.py`)

Converts TD0 files to HP150-compatible disk images.

```bash
# Basic conversion
python3 td0_to_hp150_V3.0_modular.py disk.td0 disk.img

# With verbose output and .def file generation
python3 td0_to_hp150_V3.0_modular.py disk.td0 disk.img -v -g

# Warn-only mode (continue on errors)
python3 td0_to_hp150_V3.0_modular.py disk.td0 disk.img -w
```

**Features:**
- Automatic TD0 decompression (LZSS)
- HP150 geometry detection and optimization
- Phantom sector handling
- Boot sector fixing
- CRC validation
- Detailed conversion statistics

### 2. FAT Content Inspector (`list_fat_contents.py`)

Lists and extracts files from FAT filesystem images (IMG or TD0).

```bash
# List files in an IMG
python3 list_fat_contents.py disk.img

# List files in a TD0 (auto-converts)
python3 list_fat_contents.py disk.td0

# Extract all files to a directory
python3 list_fat_contents.py disk.img extracted_files/
python3 list_fat_contents.py disk.td0 extracted_files/
```

**Features:**
- Supports both IMG and TD0 files
- Automatic TD0 to IMG conversion
- FAT12/16/32 support
- Intelligent format detection
- File extraction with original names
- Disk space analysis

### 3. Greaseweazle DEF Generator (`generate_def.py`)

Generates Greaseweazle .def files for writing to real floppy disks.

```bash
# Analyze geometry
python3 generate_def.py disk.td0 --analyze-only

# Generate .def file
python3 generate_def.py disk.td0 -o disk.def

# Batch process multiple files
python3 generate_def.py *.td0 --batch

# Preview .def content
python3 generate_def.py disk.td0 --preview
```

**Features:**
- Automatic geometry detection
- HP150 format optimization
- Greaseweazle compatibility
- Batch processing
- Custom disk naming

## 🔧 Core Modules

### `modules/td0_converter_lib.py`
- **TD0Converter**: Main conversion class
- **TD0Reader**: TD0 file parsing
- **TD0Decompressor**: LZSS decompression
- **GeometryDetector**: Disk geometry analysis

### `modules/fat_lister.py`
- **FATHandler**: FAT filesystem operations
- **FileEntry**: File metadata representation
- Supports TD0 auto-conversion
- File extraction capabilities

### `modules/geometry_detector.py`
- **GeometryDetector**: Modern geometry detection
- **GeometryDetectorLegacy**: Backward compatibility
- **GeometryInfo**: Geometry data structure

### `modules/def_generator.py`
- **DefGenerator**: .def file creation
- **DefGenerationOptions**: Generation settings
- Greaseweazle format optimization

## 📊 Supported Formats

### Input Formats
- **TD0**: Teledisk format (compressed and uncompressed)
- **IMG**: Raw disk images

### Output Formats
- **IMG**: HP150-compatible disk images
- **DEF**: Greaseweazle disk definitions

### Disk Geometries
- HP150 standard (80 cyl × 1 head × 16 sectors × 256 bytes)
- HP150 with phantom sectors
- Various PC formats (360K, 720K, 1.44M)
- Custom geometries

## 🛠️ Installation

1. Clone or download the project
2. Ensure Python 3.7+ is installed
3. No additional dependencies required (uses only standard library)

## 📝 Usage Examples

### Convert TD0 to IMG and extract files
```bash
# Convert TD0 to IMG
python3 td0_to_hp150_V3.0_modular.py software.td0 software.img -w

# Extract files from the image
python3 list_fat_contents.py software.img extracted/

# Or extract directly from TD0
python3 list_fat_contents.py software.td0 extracted/
```

### Generate Greaseweazle files
```bash
# Analyze disk geometry
python3 generate_def.py software.td0 --analyze-only -v

# Generate .def file
python3 generate_def.py software.td0 -o software.def

# Write to floppy using Greaseweazle
gw write --drive=0 --diskdefs=software.def --format="software" software.img
```

### Batch processing
```bash
# Process multiple TD0 files
python3 generate_def.py disks/*.td0 --batch

# Convert all TD0 files to IMG
for file in disks/*.td0; do
    python3 td0_to_hp150_V3.0_modular.py "$file" "${file%.td0}.img" -w
done
```

## 🔍 Error Handling

The suite includes robust error handling:

- **Warn-only mode**: Continue processing despite errors
- **CRC validation**: Verify data integrity
- **Geometry detection**: Handle non-standard formats
- **Automatic cleanup**: Remove temporary files

## 🎯 Key Features

- **Modular design**: Clean separation of concerns
- **Unified interface**: Both IMG and TD0 support
- **Intelligent detection**: Automatic format recognition
- **Greaseweazle ready**: Direct .def file generation
- **Batch processing**: Handle multiple files efficiently
- **Comprehensive logging**: Detailed operation feedback

## 📈 Performance

- Efficient LZSS decompression
- Minimal memory usage
- Fast FAT parsing
- Optimized geometry detection

## 🤝 Contributing

The codebase is well-structured for contributions:
- Scripts in root directory
- Libraries in `modules/`
- Clear module boundaries
- Comprehensive error handling

## 📄 License

This project is designed for HP150 preservation and archival purposes.
