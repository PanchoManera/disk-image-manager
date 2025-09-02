#!/usr/bin/env python3
"""
TD0/IMG/IMD Web File Manager
A web-based interface for managing TD0, IMG, and IMD disk image files
"""

import os
import sys
import tempfile
import uuid
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash
from werkzeug.utils import secure_filename
import threading
import time

# Add modules to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

from modules.auto_converter import EnhancedGenericDiskHandler
from modules.td0_converter_lib import FixedTD0Converter, ConversionOptions
from modules.geometry_detector import GeometryDetector
from modules.def_generator import DefGenerator, DefGenerationOptions
from modules.imd_handler import IMD2IMGConverter

app = Flask(__name__)
app.secret_key = 'td0_manager_secret_key_2024'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Global storage for active sessions
active_sessions = {}
UPLOAD_FOLDER = tempfile.gettempdir()
ALLOWED_EXTENSIONS = {'td0', 'img', 'imd', 'TD0', 'IMG', 'IMD'}

class SessionData:
    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.current_file = None
        self.original_filename = None  # Store original filename
        self.original_format = None  # Store original file format
        self.temp_converted_file = None
        self.files = []
        self.disk_info = {}
        self.format_info = {}
        self.sector_info = None
        self.last_activity = datetime.now()
        
    def cleanup(self):
        """Clean up temporary files"""
        for temp_file in [self.current_file, self.temp_converted_file]:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except:
                    pass
        # Clear the references
        self.current_file = None
        self.temp_converted_file = None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

def get_session(session_id):
    """Get or create session data"""
    if session_id not in active_sessions:
        active_sessions[session_id] = SessionData()
    
    # Update last activity
    active_sessions[session_id].last_activity = datetime.now()
    return active_sessions[session_id]

def cleanup_old_sessions():
    """Clean up sessions older than 2 hours"""
    cutoff = datetime.now() - timedelta(hours=2)
    to_remove = []
    
    for session_id, session_data in active_sessions.items():
        if session_data.last_activity < cutoff:
            session_data.cleanup()
            to_remove.append(session_id)
    
    for session_id in to_remove:
        del active_sessions[session_id]

def start_cleanup_thread():
    """Start background thread to clean up old sessions"""
    def cleanup_worker():
        while True:
            time.sleep(300)  # Check every 5 minutes
            cleanup_old_sessions()
    
    thread = threading.Thread(target=cleanup_worker, daemon=True)
    thread.start()

@app.route('/')
def index():
    """Main page"""
    session_id = request.args.get('session', str(uuid.uuid4()))
    return render_template('index.html', session_id=session_id)

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload"""
    session_id = request.form.get('session_id', str(uuid.uuid4()))
    session_data = get_session(session_id)
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file selected'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        # Clean up previous files first
        session_data.cleanup()
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        timestamp = int(time.time())
        safe_filename = f"{timestamp}_{session_id[:8]}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, safe_filename)
        file.save(filepath)
        
        session_data.current_file = filepath
        session_data.original_filename = filename  # Store original filename
        session_data.original_format = filename.split('.')[-1].upper()  # Store original format
        session_data.temp_converted_file = None  # Clear any previous conversion
        
        # If it's IMD, convert to IMG for internal use
        if filename.lower().endswith('.imd'):
            try:
                temp_img = tempfile.NamedTemporaryFile(suffix=f'_{session_id[:8]}_converted.img', delete=False)
                temp_img_path = temp_img.name
                temp_img.close()
                
                converter = IMD2IMGConverter(verbose=False)
                success = converter.convert(filepath, temp_img_path)
                
                if success:
                    session_data.temp_converted_file = temp_img_path
                else:
                    # Clean up failed temp file
                    try:
                        os.unlink(temp_img_path)
                    except:
                        pass
                    return jsonify({'error': 'Failed to convert IMD file'}), 500
                    
            except Exception as e:
                return jsonify({'error': f'Error converting IMD: {str(e)}'}), 500
        
        return jsonify({
            'success': True,
            'filename': filename,
            'session_id': session_id
        })
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/sector_info/<session_id>')
def sector_info(session_id):
    """Get sector information"""
    session_data = get_session(session_id)
    
    if not session_data.current_file:
        print(f"DEBUG: No file loaded for session {session_id}")
        return jsonify({'error': 'No file loaded'}), 400
    
    try:
        working_file = session_data.temp_converted_file or session_data.current_file
        print(f"DEBUG: Working with file: {working_file}")
        print(f"DEBUG: File exists: {os.path.exists(working_file)}")
        
        if not os.path.exists(working_file):
            print(f"DEBUG: Working file does not exist: {working_file}")
            return jsonify({'error': 'Working file not found'}), 400
            
        geometry = GeometryDetector().detect_from_file(working_file)
        print(f"DEBUG: Geometry detected successfully: {geometry.type}")
        
        # Use original format if available, otherwise use detected format
        source_format = session_data.original_format or geometry.source_format.upper()
        
        session_data.sector_info = {
            'filename': session_data.original_filename or os.path.basename(session_data.current_file),
            'source_format': source_format,
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
        
        print(f"DEBUG: Sector info created successfully")
        return jsonify(session_data.sector_info)
        
    except Exception as e:
        print(f"DEBUG: Exception in sector_info: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error reading sector info: {str(e)}'}), 500

@app.route('/list_files/<session_id>')
def list_files(session_id):
    """List files in the disk image"""
    session_data = get_session(session_id)
    
    if not session_data.current_file:
        return jsonify({'error': 'No file loaded'}), 400
    
    try:
        working_file = session_data.temp_converted_file or session_data.current_file
        
        handler = EnhancedGenericDiskHandler(working_file)
        files = handler.list_files()
        disk_info = handler.get_disk_info()
        format_info = handler.get_format_info()
        
        # Store handler reference to prevent cleanup until session ends
        session_data.handler = handler
        
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
        
        session_data.files = files_data
        session_data.disk_info = disk_info
        session_data.format_info = format_info
        
        return jsonify({
            'files': files_data,
            'disk_info': disk_info,
            'format_info': format_info,
            'total_files': len(files_data)
        })
            
    except Exception as e:
        return jsonify({'error': f'Error listing files: {str(e)}'}), 500

@app.route('/convert', methods=['POST'])
def convert_files():
    """Convert files between formats"""
    session_id = request.form.get('session_id')
    conversion_type = request.form.get('type')
    
    session_data = get_session(session_id)
    
    if not session_data.current_file:
        return jsonify({'error': 'No file loaded'}), 400
    
    try:
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
            result = converter.convert(session_data.current_file, temp_img_path)
            
            if result.success:
                return send_file(temp_img_path, 
                               as_attachment=True, 
                               download_name=f"{os.path.splitext(session_data.original_filename or os.path.basename(session_data.current_file))[0]}.img")
            else:
                return jsonify({'error': f'Conversion failed: {result.error_message}'}), 500
                
        elif conversion_type == 'imd_to_img':
            # IMD to IMG conversion
            temp_img = tempfile.NamedTemporaryFile(suffix='.img', delete=False)
            temp_img_path = temp_img.name
            temp_img.close()
            
            converter = IMD2IMGConverter(verbose=False)
            success = converter.convert(session_data.current_file, temp_img_path)
            
            if success:
                return send_file(temp_img_path, 
                               as_attachment=True, 
                               download_name=f"{os.path.splitext(session_data.original_filename or os.path.basename(session_data.current_file))[0]}.img")
            else:
                return jsonify({'error': 'IMD conversion failed'}), 500
                
        elif conversion_type == 'create_def':
            # Create DEF file
            working_file = session_data.temp_converted_file or session_data.current_file
            
            # For IMD files, convert temporarily if not already done
            temp_img_file = None
            if session_data.current_file.lower().endswith('.imd') and not session_data.temp_converted_file:
                temp_img_file = tempfile.NamedTemporaryFile(suffix='_def_temp.img', delete=False).name
                converter = IMD2IMGConverter(verbose=False)
                success = converter.convert(session_data.current_file, temp_img_file)
                if not success:
                    return jsonify({'error': 'Failed to convert IMD for DEF creation'}), 500
                working_file = temp_img_file
            
            # Generate DEF file
            temp_def = tempfile.NamedTemporaryFile(suffix='.def', delete=False)
            temp_def_path = temp_def.name
            temp_def.close()
            
            geometry = GeometryDetector().detect_from_file(working_file)
            options = DefGenerationOptions()
            generator = DefGenerator(geometry, working_file, options)
            
            if generator.save_def_file(temp_def_path):
                # Clean up temporary IMG if created
                if temp_img_file and os.path.exists(temp_img_file):
                    try:
                        os.unlink(temp_img_file)
                    except:
                        pass
                
                return send_file(temp_def_path, 
                               as_attachment=True, 
                               download_name=f"{os.path.splitext(session_data.original_filename or os.path.basename(session_data.current_file))[0]}.def")
            else:
                return jsonify({'error': 'Failed to create DEF file'}), 500
                
        else:
            return jsonify({'error': 'Unknown conversion type'}), 400
            
    except Exception as e:
        return jsonify({'error': f'Conversion error: {str(e)}'}), 500

@app.route('/extract/<session_id>')
def extract_files(session_id):
    """Extract files from disk image"""
    session_data = get_session(session_id)
    
    if not session_data.current_file:
        return jsonify({'error': 'No file loaded'}), 400
    
    try:
        working_file = session_data.temp_converted_file or session_data.current_file
        
        with EnhancedGenericDiskHandler(working_file) as handler:
            format_info = handler.get_format_info()
            
            # Create temporary directory for extraction
            temp_dir = tempfile.mkdtemp(prefix='extracted_files_')
            extracted_files = handler.extract_files(temp_dir)
            
            if not extracted_files:
                return jsonify({'error': 'No files were extracted'}), 400
            
            # Create ZIP file with extracted files
            import zipfile
            temp_zip = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
            temp_zip_path = temp_zip.name
            temp_zip.close()
            
            with zipfile.ZipFile(temp_zip_path, 'w') as zipf:
                for original_name, extracted_path in extracted_files.items():
                    zipf.write(extracted_path, original_name)
            
            # Clean up extraction directory
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            return send_file(temp_zip_path, 
                           as_attachment=True, 
                           download_name=f"{os.path.splitext(session_data.original_filename or os.path.basename(session_data.current_file))[0]}_files.zip")
            
    except Exception as e:
        return jsonify({'error': f'Extraction error: {str(e)}'}), 500

@app.route('/session_status/<session_id>')
def session_status(session_id):
    """Get session status"""
    session_data = get_session(session_id)
    
    return jsonify({
        'has_file': session_data.current_file is not None,
        'filename': session_data.original_filename or (os.path.basename(session_data.current_file) if session_data.current_file else None),
        'is_converted': session_data.temp_converted_file is not None,
        'session_id': session_id
    })

# Cleanup thread
start_cleanup_thread()

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    # Get port from environment variable for Railway deployment
    port = int(os.environ.get('PORT', 5001))
    debug_mode = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    print("Starting Disk Image Manager Web Interface...")
    print(f"Server will run on port: {port}")
    if not debug_mode:
        print("Running in production mode")
    print("Press Ctrl+C to stop the server")
    
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
