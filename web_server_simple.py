#!/usr/bin/env python3
"""
Disk Image Manager - Simple Async Web Interface
Simplified version based on rt11extract_simple.py pattern
"""

import os
import sys
import tempfile
import uuid
import threading
import time
import zipfile
import shutil
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename

# Add modules to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

from modules.auto_converter import EnhancedGenericDiskHandler
from modules.td0_converter_lib import FixedTD0Converter, ConversionOptions
from modules.geometry_detector import GeometryDetector
from modules.def_generator import DefGenerator, DefGenerationOptions
from modules.imd_handler import IMD2IMGConverter

app = Flask(__name__)
app.secret_key = 'disk_image_manager_2024'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Global storage for active operations
current_operations = {}
UPLOAD_FOLDER = tempfile.gettempdir()
ALLOWED_EXTENSIONS = {'td0', 'img', 'imd', 'TD0', 'IMG', 'IMD'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

def cleanup_old_operations():
    """Clean up operations older than 2 hours"""
    cutoff = datetime.now() - timedelta(hours=2)
    to_remove = []
    
    for operation_id, operation in current_operations.items():
        if operation.get('last_activity', datetime.now()) < cutoff:
            # Clean up temp files
            for file_key in ['uploaded_file', 'temp_converted_file', 'temp_dir']:
                if file_key in operation and operation[file_key]:
                    try:
                        if file_key == 'temp_dir' and os.path.exists(operation[file_key]):
                            shutil.rmtree(operation[file_key], ignore_errors=True)
                        elif os.path.exists(operation[file_key]):
                            os.unlink(operation[file_key])
                    except:
                        pass
            to_remove.append(operation_id)
    
    for operation_id in to_remove:
        del current_operations[operation_id]

def start_cleanup_thread():
    """Start background cleanup thread"""
    def cleanup_worker():
        while True:
            time.sleep(300)  # Check every 5 minutes
            cleanup_old_operations()
    
    thread = threading.Thread(target=cleanup_worker, daemon=True)
    thread.start()

def process_disk_image(operation):
    """Process disk image in background thread"""
    try:
        operation['status'] = 'Processing disk image...'
        operation['progress'] = 50
        operation['logs'].append('Starting disk image processing')
        
        # Handle IMD conversion if needed
        working_file = operation['uploaded_file']
        if operation['original_filename'].lower().endswith('.imd'):
            operation['logs'].append('Converting IMD to IMG for processing...')
            temp_img = tempfile.NamedTemporaryFile(suffix='_converted.img', delete=False)
            temp_img_path = temp_img.name
            temp_img.close()
            
            converter = IMD2IMGConverter(verbose=False)
            success = converter.convert(operation['uploaded_file'], temp_img_path)
            
            if success:
                operation['temp_converted_file'] = temp_img_path
                working_file = temp_img_path
                operation['logs'].append('IMD conversion completed successfully')
            else:
                operation['error'] = 'Failed to convert IMD file'
                operation['success'] = False
                operation['completed'] = True
                return
        
        # Process with EnhancedGenericDiskHandler
        operation['logs'].append('Analyzing disk structure...')
        handler = EnhancedGenericDiskHandler(working_file)
        
        # Get geometry info
        geometry = GeometryDetector().detect_from_file(working_file)
        if geometry:
            operation['sector_info'] = {
                'filename': operation['original_filename'],
                'source_format': operation['original_format'],
                'geometry_type': geometry.type,
                'file_size': geometry.file_size,
                'file_size_kb': round(geometry.file_size / 1024, 1),
                'cylinders': geometry.cylinders,
                'heads': geometry.heads,
                'sectors_per_track': geometry.sectors_per_track,
                'bytes_per_sector': geometry.bytes_per_sector,
                'total_sectors': geometry.total_sectors,
                'has_phantom': geometry.has_phantom,
                'notes': geometry.notes or []
            }
            operation['logs'].append(f'Detected geometry: {geometry.type}')
        
        # Get files list
        operation['logs'].append('Scanning files...')
        files = handler.list_files()
        disk_info = handler.get_disk_info()
        format_info = handler.get_format_info()
        
        # Convert files to JSON-serializable format
        files_data = []
        for file_entry in files:
            files_data.append({
                'name': file_entry.name,
                'ext': file_entry.ext,
                'full_name': file_entry.full_name,
                'size': file_entry.size,
                'attr': file_entry.attr,
                'cluster': file_entry.cluster,
                'offset': file_entry.offset,
                'format_type': getattr(file_entry, 'format_type', 'unknown'),
                'is_directory': file_entry.is_directory,
                'is_volume': file_entry.is_volume,
                'attr_flags': {
                    'readonly': bool(file_entry.attr & 0x01),
                    'hidden': bool(file_entry.attr & 0x02),
                    'system': bool(file_entry.attr & 0x04),
                    'volume': bool(file_entry.attr & 0x08),
                    'directory': bool(file_entry.attr & 0x10),
                    'archive': bool(file_entry.attr & 0x20)
                }
            })
        
        operation['files'] = files_data
        operation['disk_info'] = disk_info
        operation['format_info'] = format_info
        operation['handler'] = handler  # Keep reference
        
        operation['logs'].append(f'Found {len(files_data)} files')
        operation['status'] = f'Processing completed! Found {len(files_data)} files.'
        operation['progress'] = 100
        operation['success'] = True
        operation['completed'] = True
        operation['logs'].append('Processing completed successfully')
        
    except Exception as e:
        operation['status'] = f'Processing failed: {str(e)}'
        operation['error'] = str(e)
        operation['success'] = False
        operation['completed'] = True
        operation['logs'].append(f'Error: {str(e)}')

@app.route('/')
def index():
    """Main page"""
    return render_template('index_simple.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and start async processing"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file selected'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400
    
    try:
        # Save uploaded file
        filename = secure_filename(file.filename)
        if not filename:
            return jsonify({'error': 'Invalid filename'}), 400
        
        # Create unique operation ID
        operation_id = str(uuid.uuid4())
        timestamp = int(time.time())
        safe_filename = f"{timestamp}_{operation_id[:8]}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, safe_filename)
        
        # Ensure upload directory exists
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        file.save(filepath)
        
        # Verify file was saved
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            return jsonify({'error': 'File upload failed'}), 500
        
        # Create operation
        operation = {
            'id': operation_id,
            'uploaded_file': filepath,
            'original_filename': filename,
            'original_format': filename.split('.')[-1].upper(),
            'temp_converted_file': None,
            'status': 'File uploaded, starting processing...',
            'progress': 25,
            'completed': False,
            'success': False,
            'logs': [f'Uploaded file: {filename} ({os.path.getsize(filepath)} bytes)'],
            'last_activity': datetime.now()
        }
        
        current_operations[operation_id] = operation
        
        # Start processing in background
        threading.Thread(target=process_disk_image, args=(operation,), daemon=True).start()
        
        return jsonify({
            'success': True,
            'operation_id': operation_id,
            'message': 'File uploaded successfully, processing started'
        })
        
    except Exception as e:
        return jsonify({'error': f'Upload error: {str(e)}'}), 500

@app.route('/status/<operation_id>')
def get_status(operation_id):
    """Get operation status"""
    if operation_id not in current_operations:
        return jsonify({'error': 'Operation not found'}), 404
    
    operation = current_operations[operation_id]
    operation['last_activity'] = datetime.now()  # Update activity
    
    # Prepare response
    response = {
        'status': operation.get('status', 'Unknown'),
        'progress': operation.get('progress', 0),
        'completed': operation.get('completed', False),
        'success': operation.get('success', False),
        'logs': operation.get('logs', []),
        'error': operation.get('error'),
        'sector_info': operation.get('sector_info'),
        'files': operation.get('files', []),
        'disk_info': operation.get('disk_info'),
        'format_info': operation.get('format_info')
    }
    
    return jsonify(response)

@app.route('/convert/<operation_id>/<conversion_type>')
def convert_file(operation_id, conversion_type):
    """Convert files"""
    if operation_id not in current_operations:
        return jsonify({'error': 'Operation not found'}), 404
    
    operation = current_operations[operation_id]
    
    if not operation.get('completed') or not operation.get('success'):
        return jsonify({'error': 'Operation not ready for conversion'}), 400
    
    try:
        source_file = operation['uploaded_file']
        filename = operation['original_filename']
        
        if conversion_type == 'td0_to_img':
            # TD0 to IMG conversion
            temp_img = tempfile.NamedTemporaryFile(suffix='.img', delete=False)
            temp_img_path = temp_img.name
            temp_img.close()
            
            options = ConversionOptions(
                warn_only=True,
                force_hp150=True,
                fix_boot_sector=True,
                generate_def=False
            )
            converter = FixedTD0Converter(options)
            result = converter.convert(source_file, temp_img_path)
            
            if result.success:
                return send_file(temp_img_path, 
                               as_attachment=True, 
                               download_name=f"{os.path.splitext(filename)[0]}.img")
            else:
                return jsonify({'error': f'Conversion failed: {result.error_message}'}), 500
                
        elif conversion_type == 'imd_to_img':
            # IMD to IMG conversion
            temp_img = tempfile.NamedTemporaryFile(suffix='.img', delete=False)
            temp_img_path = temp_img.name
            temp_img.close()
            
            converter = IMD2IMGConverter(verbose=False)
            success = converter.convert(source_file, temp_img_path)
            
            if success:
                return send_file(temp_img_path, 
                               as_attachment=True, 
                               download_name=f"{os.path.splitext(filename)[0]}.img")
            else:
                return jsonify({'error': 'IMD conversion failed'}), 500
                
        elif conversion_type == 'create_def':
            # Create DEF file
            working_file = operation.get('temp_converted_file') or source_file
            
            # Generate DEF file
            temp_def = tempfile.NamedTemporaryFile(suffix='.def', delete=False)
            temp_def_path = temp_def.name
            temp_def.close()
            
            geometry = GeometryDetector().detect_from_file(working_file)
            if not geometry:
                return jsonify({'error': 'Failed to detect disk geometry'}), 500
            
            options = DefGenerationOptions()
            generator = DefGenerator(geometry, working_file, options)
            
            if generator.save_def_file(temp_def_path):
                return send_file(temp_def_path, 
                               as_attachment=True, 
                               download_name=f"{os.path.splitext(filename)[0]}.def")
            else:
                return jsonify({'error': 'Failed to create DEF file'}), 500
                
        else:
            return jsonify({'error': 'Unknown conversion type'}), 400
            
    except Exception as e:
        return jsonify({'error': f'Conversion error: {str(e)}'}), 500

@app.route('/extract/<operation_id>')
def extract_files(operation_id):
    """Extract all files as ZIP"""
    if operation_id not in current_operations:
        return jsonify({'error': 'Operation not found'}), 404
    
    operation = current_operations[operation_id]
    
    if not operation.get('completed') or not operation.get('success'):
        return jsonify({'error': 'Operation not ready for extraction'}), 400
    
    try:
        working_file = operation.get('temp_converted_file') or operation['uploaded_file']
        
        # Create temporary directory for extraction
        temp_dir = tempfile.mkdtemp(prefix='extracted_files_')
        
        # Extract using handler
        handler = operation.get('handler')
        if not handler:
            handler = EnhancedGenericDiskHandler(working_file)
        
        extracted_files = handler.extract_files(temp_dir)
        
        if not extracted_files:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return jsonify({'error': 'No files were extracted'}), 400
        
        # Create ZIP file
        temp_zip = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
        temp_zip_path = temp_zip.name
        temp_zip.close()
        
        with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for original_name, extracted_path in extracted_files.items():
                if os.path.exists(extracted_path):
                    zipf.write(extracted_path, original_name)
        
        # Clean up extraction directory
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        # Verify ZIP was created
        if os.path.exists(temp_zip_path) and os.path.getsize(temp_zip_path) > 0:
            return send_file(temp_zip_path, 
                           as_attachment=True, 
                           download_name=f"{os.path.splitext(operation['original_filename'])[0]}_files.zip")
        else:
            return jsonify({'error': 'Failed to create ZIP file'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Extraction error: {str(e)}'}), 500

# Start cleanup thread
start_cleanup_thread()

if __name__ == '__main__':
    # Create required directories
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    # Get port from environment
    port = int(os.environ.get('PORT', 5001))
    debug_mode = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    print("🖥️  Disk Image Manager - Simple Web Interface")
    print(f"📊 Supports: TD0, IMG, IMD disk images")
    print(f"🌐 Server starting on http://0.0.0.0:{port}")
    print(f"🚀 Server ready on port {port}")
    print("📝 Press Ctrl+C to stop the server")
    
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
