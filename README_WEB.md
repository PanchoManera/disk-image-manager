# TD0/IMG/IMD Web File Manager

A web-based interface for managing TD0, IMG, and IMD disk image files. This provides the same functionality as the GUI application but accessible through any web browser.

## Features

- **File Upload**: Drag and drop or click to upload TD0, IMG, and IMD files
- **Disk Analysis**: View detailed disk geometry and sector information
- **Format Conversion**: 
  - Convert TD0 files to IMG format
  - Convert IMD files to IMG format
  - Generate .def files for Greaseweazle from any supported format
- **File Extraction**: Extract and download all files from disk images as a ZIP archive
- **File Listing**: Browse files in disk images with filtering capabilities
- **Mobile Responsive**: Works on desktop, tablet, and mobile devices
- **Session Management**: Multiple users can use the interface simultaneously

## Installation

1. **Install Dependencies**:
   ```bash
   pip install -r requirements_web.txt
   ```

2. **Ensure Base Requirements**: Make sure you have the main project dependencies installed:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Starting the Web Server

```bash
python web_server.py
```

The server will start on `http://localhost:5000`. You can access it from any web browser.

### Using the Interface

1. **Upload a File**: 
   - Drag and drop a TD0, IMG, or IMD file onto the upload zone
   - Or click "Choose File" to select a file

2. **View Disk Information**: 
   - After upload, the disk geometry and format information will be displayed
   - This includes cylinders, heads, sectors, and total size

3. **List Files**: 
   - Files contained in the disk image are displayed in a table
   - Use the filter controls to search by name or file attributes

4. **Perform Operations**:
   - **Convert to IMG**: Convert TD0 or IMD files to IMG format
   - **Create DEF**: Generate a .def file for Greaseweazle
   - **Extract Files**: Download all files as a ZIP archive

### Supported File Formats

- **TD0**: Teledisk format files
- **IMG**: Raw disk image files  
- **IMD**: ImageDisk format files

## Technical Details

### Session Management

- Each browser session gets a unique session ID
- Sessions automatically clean up after 2 hours of inactivity
- Temporary files are automatically deleted when sessions expire

### File Processing

- IMD files are automatically converted to IMG format internally for processing
- All operations use the existing modules from the main project
- File extraction creates temporary ZIP archives for download

### Security

- File uploads are limited to 16MB
- Only allowed file extensions are accepted
- Temporary files are stored in system temp directory
- Session isolation prevents cross-session data access

## Architecture

The web application consists of:

- **`web_server.py`**: Main Flask application
- **`templates/index.html`**: Single-page web interface
- **`static/style.css`**: Responsive CSS styles
- **Session Management**: In-memory session storage with automatic cleanup

The web server reuses all existing modules:
- `GenericDiskHandler` for file operations
- `TD0Converter` for TD0 processing
- `IMD2IMGConverter` for IMD processing
- `GeometryDetector` for disk analysis
- `DefGenerator` for .def file creation

## Production Deployment

For production use, consider:

1. **Use Gunicorn**:
   ```bash
   gunicorn -w 4 -b 0.0.0.0:5000 web_server:app
   ```

2. **Reverse Proxy**: Use nginx or Apache as a reverse proxy

3. **HTTPS**: Configure SSL/TLS certificates

4. **File Limits**: Adjust `MAX_CONTENT_LENGTH` based on your needs

5. **Session Storage**: Consider Redis or database storage for sessions in multi-server deployments

## Browser Compatibility

- Modern browsers with JavaScript enabled
- Drag and drop support for file uploads
- Bootstrap 5 for responsive design
- Font Awesome icons for better visual experience

## Limitations

- Does not include Greaseweazle hardware interface functionality
- File uploads limited to 16MB (configurable)
- In-memory session storage (not persistent across server restarts)
- Single-server deployment (sessions not shared across multiple instances)
