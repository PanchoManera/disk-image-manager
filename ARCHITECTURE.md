# TD0 Converter Suite - Architecture

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERFACE LAYER                     │
├─────────────────────────────────────────────────────────────────┤
│  td0_to_hp150_V3.0_modular.py │  list_fat_contents.py  │  generate_def.py  │
│  ┌─────────────────────────────┐ ┌─────────────────────┐ ┌─────────────────┐ │
│  │ CLI Interface               │ │ FAT Inspector       │ │ DEF Generator   │ │
│  │ - Argument parsing          │ │ - List files        │ │ - Analyze TD0   │ │
│  │ - Progress display          │ │ - Extract files     │ │ - Create .def   │ │
│  │ - Error handling            │ │ - Disk analysis     │ │ - Batch process │ │
│  └─────────────────────────────┘ └─────────────────────┘ └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                         MODULES LAYER                          │
├─────────────────────────────────────────────────────────────────┤
│                          modules/                               │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                   td0_converter_lib.py                     │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │ │
│  │  │   TD0Converter  │  │   TD0Reader     │  │TD0Decompressor  │ │ │
│  │  │                 │  │                 │  │                 │ │ │
│  │  │ - Main convert  │  │ - Parse header  │  │ - LZSS decomp   │ │ │
│  │  │ - Options mgmt  │  │ - Parse tracks  │  │ - Huffman decode│ │ │
│  │  │ - Callbacks     │  │ - Parse sectors │  │ - Pattern decode│ │ │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                    │                             │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                     fat_lister.py                          │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │ │
│  │  │   FATHandler    │  │   FileEntry     │  │   TD0 Support   │ │ │
│  │  │                 │  │                 │  │                 │ │ │
│  │  │ - FAT parsing   │  │ - File metadata │  │ - Auto convert  │ │ │
│  │  │ - File listing  │  │ - Attributes    │  │ - Temp files    │ │ │
│  │  │ - File extract  │  │ - Size info     │  │ - Cleanup       │ │ │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                    │                             │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                  geometry_detector.py                      │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │ │
│  │  │GeometryDetector │  │  GeometryInfo   │  │GeometryDetector │ │ │
│  │  │                 │  │                 │  │     Legacy      │ │ │
│  │  │ - Auto detect   │  │ - Geometry data │  │ - Backward compat│ │ │
│  │  │ - Format recog  │  │ - Validation    │  │ - Legacy format │ │ │
│  │  │ - HP150 optimize│  │ - Normalization │  │ - Bridge class  │ │ │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                    │                             │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    def_generator.py                        │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │ │
│  │  │  DefGenerator   │  │DefGenerationOpts│  │  File Output    │ │ │
│  │  │                 │  │                 │  │                 │ │ │
│  │  │ - Generate .def │  │ - Configuration │  │ - File writing  │ │ │
│  │  │ - Format optimize│  │ - Normalization │  │ - Validation    │ │ │
│  │  │ - Greaseweazle  │  │ - Comments      │  │ - Error handling│ │ │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                         DATA LAYER                             │
├─────────────────────────────────────────────────────────────────┤
│  Input Files          │  Temporary Files     │  Output Files     │
│  ┌─────────────────┐  │  ┌─────────────────┐  │  ┌─────────────────┐ │
│  │ TD0 Files       │  │  │ Temp IMG Files  │  │  │ IMG Files       │ │
│  │ - Compressed    │  │  │ - Auto cleanup  │  │  │ - HP150 format  │ │
│  │ - Uncompressed  │  │  │ - Memory mgmt   │  │  │ - Bootable      │ │
│  │ - With comments │  │  │ - Secure temp   │  │  │ - FAT filesystem│ │
│  └─────────────────┘  │  └─────────────────┘  │  └─────────────────┘ │
│  ┌─────────────────┐  │                       │  ┌─────────────────┐ │
│  │ IMG Files       │  │                       │  │ DEF Files       │ │
│  │ - Raw images    │  │                       │  │ - Greaseweazle  │ │
│  │ - FAT filesys   │  │                       │  │ - Disk geometry │ │
│  │ - Various sizes │  │                       │  │ - Format specs  │ │
│  └─────────────────┘  │                       │  └─────────────────┘ │
│                       │                       │  ┌─────────────────┐ │
│                       │                       │  │ Extracted Files │ │
│                       │                       │  │ - Original names│ │
│                       │                       │  │ - Preserved data│ │
│                       │                       │  │ - Directory structure│ │
│                       │                       │  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## 🔄 Data Flow

### 1. TD0 to IMG Conversion
```
TD0 File → TD0Reader → TD0Decompressor → GeometryDetector → TD0Converter → IMG File
    ↓
Header Parse → Track Parse → Sector Parse → Image Generation → Boot Fix
    ↓
Optional: DefGenerator → DEF File
```

### 2. FAT Content Processing
```
IMG/TD0 File → FATHandler → FileEntry[] → Extract/List
    ↓
Boot Sector → FAT Table → Root Directory → File Data
    ↓
Optional: TD0Converter (if TD0 input)
```

### 3. DEF Generation
```
IMG/TD0 File → GeometryDetector → GeometryInfo → DefGenerator → DEF File
    ↓
Format Detection → Normalization → Template Generation
```

## 🧩 Module Dependencies

```
td0_to_hp150_V3.0_modular.py
    └── modules.td0_converter_lib
        ├── modules.geometry_detector
        └── modules.def_generator

list_fat_contents.py
    └── modules.fat_lister
        └── modules.td0_converter_lib  (for TD0 support)

generate_def.py
    ├── modules.geometry_detector
    └── modules.def_generator

modules/__init__.py
    ├── modules.td0_converter_lib
    ├── modules.fat_lister
    ├── modules.geometry_detector
    └── modules.def_generator
```

## 🎯 Key Design Principles

### 1. **Separation of Concerns**
- **Scripts**: User interface and command-line handling
- **Modules**: Core business logic and data processing
- **Clean APIs**: Well-defined interfaces between layers

### 2. **Modular Architecture**
- **Independent modules**: Each module has specific responsibilities
- **Loose coupling**: Modules communicate through well-defined interfaces
- **High cohesion**: Related functionality grouped together

### 3. **Error Handling**
- **Graceful degradation**: Warn-only mode for problematic files
- **Resource cleanup**: Automatic temporary file management
- **Comprehensive logging**: Detailed error reporting

### 4. **Extensibility**
- **Plugin architecture**: Easy to add new formats
- **Configuration options**: Flexible behavior modification
- **Callback system**: Customizable progress reporting

## 🔧 Integration Points

### 1. **TD0 to IMG Conversion**
- Direct file conversion
- Geometry detection and optimization
- Optional DEF file generation

### 2. **FAT Processing**
- Unified IMG/TD0 handling
- Automatic format detection
- File extraction capabilities

### 3. **DEF Generation**
- Standalone geometry analysis
- Batch processing support
- Greaseweazle compatibility

## 📊 Performance Characteristics

### 1. **Memory Usage**
- Streaming processing for large files
- Efficient LZSS decompression
- Minimal memory footprint

### 2. **Processing Speed**
- Optimized FAT parsing
- Fast geometry detection
- Efficient file I/O

### 3. **Scalability**
- Batch processing capabilities
- Resource management
- Concurrent file handling

## 🛡️ Security & Reliability

### 1. **Input Validation**
- File format verification
- Size limit checking
- Malformed data handling

### 2. **Resource Management**
- Automatic cleanup
- Temporary file security
- Memory leak prevention

### 3. **Error Recovery**
- Graceful error handling
- Partial processing support
- Consistent state management
