#!/usr/bin/env python3
"""
TD0/IMG File Manager - Unified GUI
A single-window interface for managing TD0 and IMG files with all functionality in one place.
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
import os
import threading
import tempfile
import subprocess
from modules.auto_converter import EnhancedGenericDiskHandler
from modules.td0_converter_lib import FixedTD0Converter, ConversionOptions, ConversionResult
from modules.geometry_detector import GeometryDetector
from modules.def_generator import DefGenerator, DefGenerationOptions
from modules.greaseweazle_writer import GreaseweazleWriter
from modules.greaseweazle_reader import is_greaseweazle_available, get_available_devices
from modules.imd_handler import IMD2IMGConverter

class TD0ImageGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("TD0/IMG File Manager")
        self.root.geometry("800x600")
        self.current_file = None
        self.current_files = []  # Store current file list
        self.current_disk_info = {}  # Store current disk info
        self.temp_converted_file = None  # Store temp converted file (TD0->IMG or IMD->IMG)
        self.create_widgets()
        
        # Register cleanup on window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
    def check_greaseweazle_available(self):
        """Verifica si Greaseweazle está disponible y conectado, y actualiza los botones correspondientes"""
        possible_paths = [
            "gw",  # Si está en PATH
            "/usr/local/bin/gw",
            "/usr/bin/gw",
            "/opt/homebrew/bin/gw",
            "greaseweazle",
            "/usr/local/bin/greaseweazle",
            "/usr/bin/greaseweazle",
            "/opt/homebrew/bin/greaseweazle"
        ]
        
        for path in possible_paths:
            try:
                # Primero verificar si el comando existe
                version_result = subprocess.run([path, "--version"], 
                                              capture_output=True, 
                                              text=True, 
                                              timeout=5)
                if version_result.returncode == 0:
                    # Verificar si el dispositivo está conectado
                    info_result = subprocess.run([path, "info"],
                                               capture_output=True,
                                               text=True,
                                               timeout=5)
                    if info_result.returncode == 0 and "No Greaseweazle device found" not in info_result.stderr:
                        # Activar el botón Read Disk solo si el dispositivo está conectado
                        self.read_disk_button.config(state=tk.NORMAL)
                        return
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                continue
        
        # Si no se encontró Greaseweazle o no está conectado, desactivar el botón
        self.read_disk_button.config(state=tk.DISABLED)

    def create_widgets(self):
        # Create main menu
        self.create_menu()
        
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # File selection frame
        file_frame = ttk.LabelFrame(main_frame, text="File Selection", padding="5")
        file_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        file_frame.columnconfigure(2, weight=1)
        
        ttk.Button(file_frame, text="Load TD0/IMG/IMD", command=self.load_image).grid(row=0, column=0, padx=(0, 5))
        self.read_disk_button = ttk.Button(file_frame, text="Read Disk (SCP)", command=self.load_from_disk)
        self.read_disk_button.grid(row=0, column=1, padx=(0, 5))
        self.file_label = ttk.Label(file_frame, text="No file loaded")
        self.file_label.grid(row=0, column=2, sticky=(tk.W, tk.E))
        
        # Control buttons frame
        control_frame = ttk.LabelFrame(main_frame, text="Operations", padding="5")
        control_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(control_frame, text="Show Sector Info", command=self.show_sector_info).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(control_frame, text="List Files", command=self.list_files).grid(row=0, column=1, padx=(0, 5))
        ttk.Button(control_frame, text="Extract Files", command=self.extract_files).grid(row=0, column=2, padx=(0, 5))
        
        # Write Disk button
        self.write_disk_btn = ttk.Button(control_frame, text="Write Disk", command=self.write_disk, state=tk.DISABLED)
        self.write_disk_btn.grid(row=0, column=3)
        
        # Main display area with notebook tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Sector Info tab
        self.sector_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.sector_frame, text="Sector Information")
        
        self.sector_text = tk.Text(self.sector_frame, wrap=tk.WORD, state=tk.DISABLED)
        sector_scroll = ttk.Scrollbar(self.sector_frame, orient=tk.VERTICAL, command=self.sector_text.yview)
        self.sector_text.configure(yscrollcommand=sector_scroll.set)
        
        self.sector_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        sector_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.sector_frame.columnconfigure(0, weight=1)
        self.sector_frame.rowconfigure(0, weight=1)
        
        # File List tab
        self.files_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.files_frame, text="File List")
        
        # Filter frame
        filter_frame = ttk.LabelFrame(self.files_frame, text="Display Filters", padding="5")
        filter_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Filter checkboxes
        self.show_hidden_var = tk.BooleanVar(value=True)
        self.show_system_var = tk.BooleanVar(value=True)
        self.show_directories_var = tk.BooleanVar(value=True)
        self.show_volume_var = tk.BooleanVar(value=True)
        self.show_zero_size_var = tk.BooleanVar(value=True)
        
        ttk.Checkbutton(filter_frame, text="Show Hidden", variable=self.show_hidden_var, command=self.refresh_file_display).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(filter_frame, text="Show System", variable=self.show_system_var, command=self.refresh_file_display).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(filter_frame, text="Show Directories", variable=self.show_directories_var, command=self.refresh_file_display).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(filter_frame, text="Show Volume", variable=self.show_volume_var, command=self.refresh_file_display).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(filter_frame, text="Show 0-byte", variable=self.show_zero_size_var, command=self.refresh_file_display).pack(side=tk.LEFT, padx=(0, 10))
        
        # Treeview for file listing
        tree_frame = ttk.Frame(self.files_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        columns = ('Name', 'Size', 'Type', 'Attributes')
        self.file_tree = ttk.Treeview(tree_frame, columns=columns, show='headings')
        
        # Define column headings and widths
        self.file_tree.heading('Name', text='Name')
        self.file_tree.heading('Size', text='Size')
        self.file_tree.heading('Type', text='Type')
        self.file_tree.heading('Attributes', text='Attributes')
        
        self.file_tree.column('Name', width=200)
        self.file_tree.column('Size', width=100)
        self.file_tree.column('Type', width=80)
        self.file_tree.column('Attributes', width=100)
        
        # Scrollbar for file tree
        files_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=files_scroll.set)
        
        self.file_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        files_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Extraction Status tab
        self.extract_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.extract_frame, text="Extraction Status")
        
        self.extract_text = tk.Text(self.extract_frame, wrap=tk.WORD, state=tk.DISABLED)
        extract_scroll = ttk.Scrollbar(self.extract_frame, orient=tk.VERTICAL, command=self.extract_text.yview)
        self.extract_text.configure(yscrollcommand=extract_scroll.set)
        
        self.extract_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        extract_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.extract_frame.columnconfigure(0, weight=1)
        self.extract_frame.rowconfigure(0, weight=1)
        
        # Status bar frame with two sections
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        status_frame.columnconfigure(0, weight=1)
        status_frame.columnconfigure(1, weight=0)

        # Main status
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(status_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))

        # Greaseweazle status
        self.gw_status_frame = ttk.Frame(status_frame)
        self.gw_status_frame.grid(row=0, column=1, sticky=(tk.W, tk.E))
        
        self.gw_icon_label = ttk.Label(self.gw_status_frame, text="⚫", font=("Arial", 10))
        self.gw_icon_label.pack(side=tk.LEFT, padx=(0, 2))
        
        self.gw_status_label = ttk.Label(self.gw_status_frame, text="Greaseweazle: Checking...", anchor=tk.E)
        self.gw_status_label.pack(side=tk.LEFT)

        # Start periodic Greaseweazle check
        self.check_greaseweazle_periodic()
        
    def create_menu(self):
        """Create the menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Load TD0/IMG...", command=self.load_image)
        file_menu.add_separator()
        file_menu.add_command(label="Convert TD0 to IMG...", command=self.convert_td0_to_img)
        file_menu.add_command(label="Convert IMD to IMG...", command=self.convert_imd_to_img)
        file_menu.add_command(label="Create .def from IMG/TD0/IMD...", command=self.create_def)
        file_menu.add_separator()
        file_menu.add_command(label="Check Greaseweazle", command=self.check_greaseweazle)
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)
        
    def load_image(self):
        """Load a TD0, IMG, or IMD file"""
        filetypes = [
            ("Disk image files", "*.td0;*.TD0;*.img;*.IMG;*.imd;*.IMD"),
            ("TD0 files", "*.td0;*.TD0"),
            ("IMG files", "*.img;*.IMG"),
            ("IMD files", "*.imd;*.IMD"),
            ("All files", "*.*")
        ]
        filepath = filedialog.askopenfilename(title="Open Image File", filetypes=filetypes)
        if filepath:
            # Clean up any previous temp file
            self._cleanup_temp_file()
            
            self.current_file = filepath
            self.file_label.config(text=os.path.basename(filepath))
            self.root.title(f"TD0/IMG File Manager - {os.path.basename(filepath)}")
            
            # Check if we need internal conversion for IMD files
            if filepath.lower().endswith('.imd'):
                self.status_var.set(f"Converting IMD to IMG...")
                self._convert_imd_for_internal_use(filepath)
            else:
                self.status_var.set(f"Loaded: {os.path.basename(filepath)}")
                # Clear previous data
                self.clear_display()
                
                # Enable Write Disk button if file is loaded
                self.update_button_states()
                
                # Auto-show sector info
                self.show_sector_info()
    
    def _convert_imd_for_internal_use(self, imd_path):
        """Convert IMD to temporary IMG for internal use"""
        def convert_thread():
            try:
                # Create temporary IMG file
                temp_img = tempfile.NamedTemporaryFile(suffix='_converted.img', delete=False)
                temp_img_path = temp_img.name
                temp_img.close()
                
                # Convert IMD to IMG
                converter = IMD2IMGConverter(verbose=False)
                success = converter.convert(imd_path, temp_img_path)
                
                if success:
                    # Store temp file path for cleanup later
                    self.temp_converted_file = temp_img_path
                    
                    # Update UI on main thread
                    self.root.after(0, self._on_imd_converted, temp_img_path)
                else:
                    self.root.after(0, lambda: self._show_error("Failed to convert IMD file"))
                    # Clean up failed temp file
                    try:
                        os.unlink(temp_img_path)
                    except:
                        pass
            except Exception as e:
                error_msg = f"Error converting IMD: {str(e)}"
                self.root.after(0, lambda msg=error_msg: self._show_error(msg))
        
        thread = threading.Thread(target=convert_thread)
        thread.daemon = True
        thread.start()
    
    def _on_imd_converted(self, temp_img_path):
        """Called when IMD conversion completes successfully"""
        self.status_var.set(f"Loaded: {os.path.basename(self.current_file)} (converted from IMD)")
        
        # Clear previous data
        self.clear_display()
        
        # Enable Write Disk button
        self.update_button_states()
        
        # Auto-show sector info using the converted IMG file
        self.show_sector_info()
    
    def _cleanup_temp_file(self):
        """Clean up any temporary converted file"""
        if self.temp_converted_file and os.path.exists(self.temp_converted_file):
            try:
                os.unlink(self.temp_converted_file)
                self.temp_converted_file = None
            except:
                pass
    
    def _get_working_file(self):
        """Get the file to work with (original or converted temp)"""
        if self.temp_converted_file:
            return self.temp_converted_file
        return self.current_file

    def load_from_disk(self):
        """Read disk directly to SCP format using Greaseweazle"""
        # Check if Greaseweazle is available
        if not is_greaseweazle_available():
            messagebox.showerror(
                "Greaseweazle not found",
                "Greaseweazle is not available on this system.\n"
                "Please install Greaseweazle and ensure it's in your PATH."
            )
            return

        # Create temporary file for SCP
        temp_scp = tempfile.NamedTemporaryFile(suffix='.scp', delete=False).name

        # Show read progress dialog
        self._show_read_progress(temp_scp)

    def _show_read_progress(self, temp_scp_path):
        """Show read progress dialog with console output"""
        progress_window = tk.Toplevel(self.root)
        progress_window.title("💾 Reading from Disk")
        progress_window.geometry("700x600")
        progress_window.transient(self.root)
        progress_window.grab_set()
        
        # Center the window
        progress_window.update_idletasks()
        x = (progress_window.winfo_screenwidth() // 2) - (progress_window.winfo_width() // 2)
        y = (progress_window.winfo_screenheight() // 2) - (progress_window.winfo_height() // 2)
        progress_window.geometry(f"+{x}+{y}")
        
        main_frame = ttk.Frame(progress_window, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(header_frame, text="💾 Disk Read Progress", font=('Arial', 14, 'bold')).pack()
        ttk.Label(header_frame, text="Reading raw flux data from disk", font=('Arial', 10)).pack(pady=(5, 0))
        
        # Current step
        status_frame = ttk.LabelFrame(main_frame, text="Current Step", padding="10")
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        current_step = ttk.Label(status_frame, text="Initializing...", font=('Arial', 11, 'bold'))
        current_step.pack(anchor=tk.W)
        
        progress_bar = ttk.Progressbar(status_frame, mode='indeterminate')
        progress_bar.pack(fill=tk.X, pady=(10, 0))
        progress_bar.start()
        
        # Console output
        console_frame = ttk.LabelFrame(main_frame, text="Greaseweazle Output", padding="10")
        console_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        console_text = scrolledtext.ScrolledText(
            console_frame,
            height=15,
            font=('Monaco', 9),
            wrap=tk.WORD
        )
        console_text.pack(fill=tk.BOTH, expand=True)
        
        def on_read_complete(success):
            """Called when read operation completes"""
            progress_bar.stop()
            
            if success:
                # Ask user where to save the SCP file
                save_path = filedialog.asksaveasfilename(
                    title="Save SCP File", 
                    defaultextension=".scp", 
                    filetypes=[("SuperCard Pro files", "*.scp")]
                )
                
                if save_path:
                    try:
                        # Copy temporary SCP to final location
                        import shutil
                        shutil.copy2(temp_scp_path, save_path)
                        messagebox.showinfo(
                            "Success",
                            f"Disk read successfully and saved to {save_path}\n\n"
                            "Would you like to convert this image to a specific format?"
                        )
                        # Limpiar y cerrar
                        progress_window.destroy()
                        try:
                            os.unlink(temp_scp_path)
                        except:
                            pass
                            
                        # Ask if user wants to convert
                        if messagebox.askyesno("Convert Image", "Would you like to convert this image to a specific format?"):
                            self._show_conversion_dialog(save_path)
                    except Exception as e:
                        messagebox.showerror("Error", f"Error saving file: {str(e)}")
            else:
                messagebox.showerror(
                    "Read Error",
                    "Error reading from disk.\n"
                    "Check the console output for details."
                )
                # Limpiar y cerrar
                progress_window.destroy()
                try:
                    os.unlink(temp_scp_path)
                except:
                    pass
        
        def on_progress(message):
            console_text.insert(tk.END, f"{message}\n")
            console_text.see(tk.END)
            
        def on_error(message):
            console_text.insert(tk.END, f"ERROR: {message}\n")
            console_text.see(tk.END)
        
        # Start the read process in a separate thread
        def read_thread():
            from modules.greaseweazle_reader import GreaseweazleReader
            reader = GreaseweazleReader(on_progress, on_error)
            success = reader.read_flux(temp_scp_path)
            self.root.after(0, lambda: on_read_complete(success))
        
        thread = threading.Thread(target=read_thread)
        thread.daemon = True
        thread.start()

    def _show_conversion_dialog(self, scp_path):
        """Show dialog to convert SCP to specific format"""
        # First, get available .def files
        defs_dir = os.path.join(os.path.dirname(__file__), 'defs')
        if not os.path.exists(defs_dir):
            messagebox.showerror("Error", "Defs directory not found")
            return
            
        def_files = [f for f in os.listdir(defs_dir) if f.endswith('.def')]
        if not def_files:
            messagebox.showerror("Error", "No .def files found in defs directory")
            return
            
        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Convert Image")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Format selection
        ttk.Label(main_frame, text="Select target format:").pack(anchor=tk.W)
        
        format_var = tk.StringVar(value=def_files[0])
        format_combo = ttk.Combobox(main_frame, textvariable=format_var, values=def_files, state='readonly')
        format_combo.pack(fill=tk.X, pady=(0, 10))
        
        def convert():
            selected_def = os.path.join(defs_dir, format_var.get())
            save_path = filedialog.asksaveasfilename(
                title="Save Converted Image", 
                defaultextension=".img", 
                filetypes=[("Disk Image", "*.img")]
            )
            if save_path:
                # Close the dialog
                dialog.destroy()
                # Show conversion progress
                self._show_conversion_progress(scp_path, selected_def, save_path)
            else:
                dialog.destroy()

    def _show_conversion_progress(self, scp_path, def_path, output_path):
        """Show conversion progress dialog"""
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Converting Image")
        progress_window.geometry("700x400")
        progress_window.transient(self.root)
        progress_window.grab_set()
        
        # Center the window
        progress_window.update_idletasks()
        x = (progress_window.winfo_screenwidth() // 2) - (progress_window.winfo_width() // 2)
        y = (progress_window.winfo_screenheight() // 2) - (progress_window.winfo_height() // 2)
        progress_window.geometry(f"+{x}+{y}")
        
        main_frame = ttk.Frame(progress_window, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        ttk.Label(main_frame, text="Converting SCP to IMG", font=('Arial', 14, 'bold')).pack(pady=(0, 10))
        ttk.Label(main_frame, text=f"Using format: {os.path.basename(def_path)}", font=('Arial', 10)).pack()
        
        # Progress indicator
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=10)
        
        progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate')
        progress_bar.pack(fill=tk.X)
        progress_bar.start()
        
        # Console output
        console_frame = ttk.LabelFrame(main_frame, text="Conversion Output", padding="10")
        console_frame.pack(fill=tk.BOTH, expand=True)
        
        console_text = scrolledtext.ScrolledText(
            console_frame,
            height=10,
            font=('Monaco', 9),
            wrap=tk.WORD
        )
        console_text.pack(fill=tk.BOTH, expand=True)
        
        def on_progress(message):
            console_text.insert(tk.END, f"{message}\n")
            console_text.see(tk.END)
            
        def on_error(message):
            console_text.insert(tk.END, f"ERROR: {message}\n")
            console_text.see(tk.END)
            
        def on_complete(success):
            progress_bar.stop()
            if success:
                messagebox.showinfo(
                    "Success",
                    f"Image converted successfully to {os.path.basename(output_path)}"
                )
                progress_window.destroy()
            else:
                messagebox.showerror(
                    "Error",
                    "Failed to convert image. Check the output for details."
                )
        
        # Start conversion in a separate thread
        def convert_thread():
            from modules.scp_converter import SCPConverter
            converter = SCPConverter(on_progress, on_error)
            success = converter.convert_to_img(scp_path, def_path, output_path)
            self.root.after(0, lambda: on_complete(success))
        
        thread = threading.Thread(target=convert_thread)
        thread.daemon = True
        thread.start()
        
        ttk.Button(main_frame, text="Convert", command=convert).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(main_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT)
            
    def clear_display(self):
        """Clear all display areas"""
        self.sector_text.config(state=tk.NORMAL)
        self.sector_text.delete(1.0, tk.END)
        self.sector_text.config(state=tk.DISABLED)
        
        # Clear file tree
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
            
        self.extract_text.config(state=tk.NORMAL)
        self.extract_text.delete(1.0, tk.END)
        self.extract_text.config(state=tk.DISABLED)
        
        # Clear stored data
        self.current_files = []
        self.current_disk_info = {}
        
    def run_in_thread(self, target, *args):
        """Run a function in a separate thread to avoid blocking the GUI"""
        thread = threading.Thread(target=target, args=args)
        thread.daemon = True
        thread.start()
        
    def show_sector_info(self):
        """Display sector information"""
        if not self.current_file:
            messagebox.showerror("Error", "No file loaded")
            return
        
        self.status_var.set("Reading sector information...")
        self.notebook.select(self.sector_frame)
        self.run_in_thread(self._show_sector_info)
        
    def _show_sector_info(self):
        """Thread function to read sector information"""
        try:
            working_file = self._get_working_file()
            geometry = GeometryDetector().detect_from_file(working_file)
            self.root.after(0, self._display_sector_info, geometry)
        except Exception as e:
            error_msg = f"Error reading sector info: {str(e)}"
            self.root.after(0, lambda msg=error_msg: self._show_error(msg))
            
    def _display_sector_info(self, geometry):
        """Display sector information in the text widget"""
        info_text = f"""File: {os.path.basename(self.current_file)}
Full Path: {self.current_file}
Source Format: {geometry.source_format.upper()}
Geometry Type: {geometry.type}
File Size: {geometry.file_size:,} bytes ({geometry.file_size/1024:.1f} KB)

Disk Geometry:
- Cylinders: {geometry.cylinders}
- Heads: {geometry.heads}
- Sectors per Track: {geometry.sectors_per_track}
- Bytes per Sector: {geometry.bytes_per_sector}
- Total Sectors: {geometry.total_sectors}
"""
        
        if geometry.has_phantom:
            info_text += "\n⚠️  Contains phantom sectors\n"
        
        if geometry.notes:
            info_text += "\nNotes:\n"
            for note in geometry.notes:
                info_text += f"• {note}\n"
        
        self.sector_text.config(state=tk.NORMAL)
        self.sector_text.delete(1.0, tk.END)
        self.sector_text.insert(tk.END, info_text)
        self.sector_text.config(state=tk.DISABLED)
        
        self.status_var.set("Sector information loaded")
        
    def list_files(self):
        """List files in the image"""
        if not self.current_file:
            messagebox.showerror("Error", "No file loaded")
            return
        
        self.status_var.set("Reading file list...")
        self.notebook.select(self.files_frame)
        self.run_in_thread(self._list_files)
        
    def _list_files(self):
        """Thread function to read file list"""
        try:
            working_file = self._get_working_file()
            with EnhancedGenericDiskHandler(self.current_file) as handler:
                files = handler.list_files()
                disk_info = handler.get_disk_info()
                format_info = handler.get_format_info()
                
                # Add format info to disk_info
                disk_info['format_type'] = format_info
                
                self.root.after(0, self._display_file_list, files, disk_info)
        except Exception as e:
            error_msg = f"Error reading files: {str(e)}"
            self.root.after(0, lambda msg=error_msg: self._show_error(msg))
            
    def _display_file_list(self, files, disk_info):
        """Display file list in the tree view"""
        # Store data for filtering
        self.current_files = files
        self.current_disk_info = disk_info
        
        # Refresh display with current filter settings
        self.refresh_file_display()
        
    def refresh_file_display(self):
        """Refresh file display based on current filter settings"""
        if not hasattr(self, 'current_files') or not self.current_files or not hasattr(self, 'current_disk_info') or not self.current_disk_info:
            return
            
        # Clear existing items
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        
        # Add disk info as first item with volume label if available
        disk_info_name = "[DISK INFO]"
        if self.current_disk_info.get('volume_label'):
            disk_info_name = f"[DISK: {self.current_disk_info['volume_label']}]"
            
        self.file_tree.insert('', 'end', values=(
            disk_info_name,
            f"{self.current_disk_info['total_size']:,} bytes",
            f"{self.current_disk_info['bytes_per_sector']}b/sec",
            f"{self.current_disk_info['sectors_per_cluster']}s/clus"
        ))
        
        # Filter and add files
        displayed_count = 0
        for file_entry in self.current_files:
            # Skip volume labels (they're now shown in disk info)
            if file_entry.is_volume:
                continue
                
            # Apply filters
            if not self.show_hidden_var.get() and (file_entry.attr & 0x02):  # Hidden
                continue
            if not self.show_system_var.get() and (file_entry.attr & 0x04):  # System
                continue
            if not self.show_directories_var.get() and file_entry.is_directory:  # Directory
                continue
            if not self.show_zero_size_var.get() and file_entry.size == 0:  # Zero size
                continue
                
            file_type = "DIR" if file_entry.is_directory else "VOL" if file_entry.is_volume else "FILE"
            
            # Add attribute flags
            attr_flags = []
            if file_entry.attr & 0x01:  # Read-only
                attr_flags.append("R")
            if file_entry.attr & 0x02:  # Hidden
                attr_flags.append("H")
            if file_entry.attr & 0x04:  # System
                attr_flags.append("S")
            if file_entry.attr & 0x08:  # Volume
                attr_flags.append("V")
            if file_entry.attr & 0x10:  # Directory
                attr_flags.append("D")
            if file_entry.attr & 0x20:  # Archive
                attr_flags.append("A")
            
            attr_str = ",".join(attr_flags) if attr_flags else "-"
            
            self.file_tree.insert('', 'end', values=(
                file_entry.full_name,
                f"{file_entry.size:,}",
                file_type,
                attr_str
            ))
            displayed_count += 1
        
        total_files = len(self.current_files)
        if displayed_count != total_files:
            self.status_var.set(f"Showing {displayed_count} of {total_files} files (filtered)")
        else:
            self.status_var.set(f"Found {total_files} files")
        
    def extract_files(self):
        """Extract files from the image"""
        if not self.current_file:
            messagebox.showerror("Error", "No file loaded")
            return
        
        directory = filedialog.askdirectory(title="Select Extraction Directory")
        if not directory:
            return
        
        self.status_var.set("Extracting files...")
        self.notebook.select(self.extract_frame)
        self.run_in_thread(self._extract_files, directory)
        
    def _extract_files(self, directory):
        """Thread function to extract files"""
        try:
            working_file = self._get_working_file()
            with EnhancedGenericDiskHandler(self.current_file) as handler:
                # Clear extraction log
                self.root.after(0, self._clear_extraction_log)
                
                # Extract files (supports all formats now)
                format_info = handler.get_format_info()
                
                # Inform user about extraction type
                if format_info['type'] == 'cp_m':
                    self.root.after(0, lambda: self._log_extraction("Attempting CP/M file extraction..."))
                elif format_info['type'] == 'raw':
                    self.root.after(0, lambda: self._log_extraction("Unknown format - creating analysis files..."))
                else:
                    self.root.after(0, lambda: self._log_extraction("Extracting FAT filesystem files..."))
                
                # Extract files
                extracted_files = handler.extract_files(directory)
                
                self.root.after(0, self._display_extraction_results, extracted_files, directory)
        except Exception as e:
            error_msg = f"Error extracting files: {str(e)}"
            self.root.after(0, lambda msg=error_msg: self._show_error(msg))
            
    def _clear_extraction_log(self):
        """Clear the extraction log"""
        self.extract_text.config(state=tk.NORMAL)
        self.extract_text.delete(1.0, tk.END)
        self.extract_text.config(state=tk.DISABLED)
    
    def _log_extraction(self, message):
        """Log extraction progress message"""
        self.extract_text.config(state=tk.NORMAL)
        self.extract_text.insert(tk.END, f"{message}\n")
        self.extract_text.see(tk.END)
        self.extract_text.config(state=tk.DISABLED)
        
    def _display_extraction_results(self, extracted_files, directory):
        """Display extraction results"""
        self.extract_text.config(state=tk.NORMAL)
        self.extract_text.insert(tk.END, f"Extraction to: {directory}\n")
        self.extract_text.insert(tk.END, f"{'='*50}\n\n")
        
        if extracted_files:
            self.extract_text.insert(tk.END, f"Successfully extracted {len(extracted_files)} files:\n\n")
            for original_name, extracted_path in extracted_files.items():
                self.extract_text.insert(tk.END, f"✓ {original_name} → {os.path.basename(extracted_path)}\n")
        else:
            self.extract_text.insert(tk.END, "No files were extracted (no regular files found)\n")
        
        self.extract_text.config(state=tk.DISABLED)
        self.status_var.set(f"Extracted {len(extracted_files)} files to {os.path.basename(directory)}")
        
    def convert_td0_to_img(self):
        """Convert TD0 to IMG file"""
        filetypes = [
            ("TD0 files", "*.td0"),
            ("TD0 files", "*.TD0"),
            ("All files", "*.*")
        ]
        input_file = filedialog.askopenfilename(title="Select TD0 File", filetypes=filetypes)
        if not input_file:
            return
        
        save_path = filedialog.asksaveasfilename(
            title="Save IMG File", 
            defaultextension=".img", 
            filetypes=[("IMG files", "*.img")]
        )
        if not save_path:
            return
        
        self.status_var.set("Converting TD0 to IMG...")
        self.run_in_thread(self._convert_td0_to_img, input_file, save_path)
        
    def _convert_td0_to_img(self, input_file, save_path):
        """Thread function to convert TD0 to IMG"""
        try:
            options = ConversionOptions(
                warn_only=True,
                force_hp150=True,
                fix_boot_sector=True,
                generate_def=False
            )
            converter = FixedTD0Converter(options)
            result = converter.convert(input_file, save_path)
            
            if result.success:
                success_msg = f"Successfully converted to {os.path.basename(save_path)}"
                status_msg = f"Converted: {os.path.basename(save_path)}"
                self.root.after(0, lambda msg=success_msg: self._show_success(msg))
                self.root.after(0, lambda msg=status_msg: self.status_var.set(msg))
            else:
                error_msg = f"Conversion failed: {result.error_message}"
                self.root.after(0, lambda msg=error_msg: self._show_error(msg))
        except Exception as e:
            error_msg = f"Error during conversion: {str(e)}"
            self.root.after(0, lambda msg=error_msg: self._show_error(msg))
            
    def convert_imd_to_img(self):
        """Convert IMD to IMG file"""
        filetypes = [
            ("IMD files", "*.imd"),
            ("IMD files", "*.IMD"),
            ("All files", "*.*")
        ]
        input_file = filedialog.askopenfilename(title="Select IMD File", filetypes=filetypes)
        if not input_file:
            return
        
        save_path = filedialog.asksaveasfilename(
            title="Save IMG File", 
            defaultextension=".img", 
            filetypes=[("IMG files", "*.img")]
        )
        if not save_path:
            return
        
        self.status_var.set("Converting IMD to IMG...")
        self.run_in_thread(self._convert_imd_to_img, input_file, save_path)
        
    def _convert_imd_to_img(self, input_file, save_path):
        """Thread function to convert IMD to IMG"""
        try:
            converter = IMD2IMGConverter(verbose=False)
            success = converter.convert(input_file, save_path)
            
            if success:
                success_msg = f"Successfully converted to {os.path.basename(save_path)}"
                status_msg = f"Converted: {os.path.basename(save_path)}"
                self.root.after(0, lambda msg=success_msg: self._show_success(msg))
                self.root.after(0, lambda msg=status_msg: self.status_var.set(msg))
            else:
                error_msg = "Conversion failed"
                self.root.after(0, lambda msg=error_msg: self._show_error(msg))
        except Exception as e:
            error_msg = f"Error during conversion: {str(e)}"
            self.root.after(0, lambda msg=error_msg: self._show_error(msg))
            
    def create_def(self):
        """Create .def file from IMG/TD0/IMD"""
        filetypes = [
            ("Disk image files", "*.td0;*.TD0;*.img;*.IMG;*.imd;*.IMD"),
            ("TD0 files", "*.td0;*.TD0"),
            ("IMG files", "*.img;*.IMG"),
            ("IMD files", "*.imd;*.IMD"),
            ("All files", "*.*")
        ]
        input_file = filedialog.askopenfilename(title="Select TD0/IMG/IMD File", filetypes=filetypes)
        if not input_file:
            return
        
        save_path = filedialog.asksaveasfilename(
            title="Save DEF File", 
            defaultextension=".def", 
            filetypes=[("DEF files", "*.def")]
        )
        if not save_path:
            return
        
        self.status_var.set("Creating .def file...")
        self.run_in_thread(self._create_def, input_file, save_path)
        
    def _create_def(self, input_file, save_path):
        """Thread function to create .def file"""
        temp_img_file = None
        try:
            working_file = input_file
            
            # If it's an IMD file, convert to temporary IMG first
            if input_file.lower().endswith('.imd'):
                temp_img_file = tempfile.NamedTemporaryFile(suffix='_def_temp.img', delete=False).name
                
                converter = IMD2IMGConverter(verbose=False)
                success = converter.convert(input_file, temp_img_file)
                
                if not success:
                    self.root.after(0, lambda: self._show_error("Failed to convert IMD to IMG for .def creation"))
                    return
                
                working_file = temp_img_file
            
            # Generate geometry and .def file
            geometry = GeometryDetector().detect_from_file(working_file)
            options = DefGenerationOptions()
            generator = DefGenerator(geometry, working_file, options)
            
            if generator.save_def_file(save_path):
                success_msg = f"DEF file saved as {os.path.basename(save_path)}"
                status_msg = f"Created: {os.path.basename(save_path)}"
                self.root.after(0, lambda msg=success_msg: self._show_success(msg))
                self.root.after(0, lambda msg=status_msg: self.status_var.set(msg))
            else:
                self.root.after(0, lambda: self._show_error("Failed to save DEF file"))
                
        except Exception as e:
            error_msg = f"Error creating DEF file: {str(e)}"
            self.root.after(0, lambda msg=error_msg: self._show_error(msg))
        finally:
            # Clean up temporary IMG file if created
            if temp_img_file and os.path.exists(temp_img_file):
                try:
                    os.unlink(temp_img_file)
                except:
                    pass
            
    def show_about(self):
        """Show about dialog"""
        messagebox.showinfo("About", "TD0/IMG File Manager\nVersion 1.0\n\nA tool for managing TD0 and IMG disk images.")
        
    def check_greaseweazle(self):
        """Check if Greaseweazle is connected and show available devices"""
        if is_greaseweazle_available():
            devices = get_available_devices()
            if devices:
                device_list = "\n".join(devices)
                messagebox.showinfo("Greaseweazle Connected", f"Devices: \n{device_list}")
            else:
                messagebox.showwarning("No Devices", "Greaseweazle is available but no devices are connected.")
        else:
            messagebox.showerror("Greaseweazle Not Available", "Greaseweazle is not available on this system.")

    def _show_error(self, message):
        """Show error message"""
        messagebox.showerror("Error", message)
        self.status_var.set("Error occurred")
        
    def _show_success(self, message):
        """Show success message"""
        messagebox.showinfo("Success", message)
        
    def check_greaseweazle_periodic(self):
        """Check Greaseweazle status periodically and update the indicator"""
        try:
            if is_greaseweazle_available():
                devices = get_available_devices()
                if devices:
                    self.gw_icon_label.config(text="🟢", foreground="green")
                    self.gw_status_label.config(text=f"Greaseweazle: {devices[0]}")
                    self.read_disk_button.config(state=tk.NORMAL)
                else:
                    self.gw_icon_label.config(text="🟡", foreground="orange")
                    self.gw_status_label.config(text="Greaseweazle: No device")
                    self.read_disk_button.config(state=tk.DISABLED)
            else:
                self.gw_icon_label.config(text="🔴", foreground="red")
                self.gw_status_label.config(text="Greaseweazle: Not available")
                self.read_disk_button.config(state=tk.DISABLED)
        except Exception as e:
            self.gw_icon_label.config(text="🔴", foreground="red")
            self.gw_status_label.config(text="Greaseweazle: Error")
            self.read_disk_button.config(state=tk.DISABLED)
        
        # Schedule next check in 5 seconds
        self.root.after(5000, self.check_greaseweazle_periodic)

    def update_button_states(self):
        """Update button states based on current file"""
        has_file = self.current_file is not None
        self.write_disk_btn.config(state=tk.NORMAL if has_file else tk.DISABLED)
        
    def write_disk(self):
        """Write current image to disk using Greaseweazle"""
        if not self.current_file:
            messagebox.showerror("Error", "No file loaded")
            return
            
        # Check if Greaseweazle is available
        if not is_greaseweazle_available():
            messagebox.showerror(
                "Greaseweazle not found",
                "Greaseweazle is not available on this system.\n"
                "Please install Greaseweazle and ensure it's in your PATH."
            )
            return
            
        # Get the working file (already converted for IMD, or original for IMG)
        working_file = self._get_working_file()
        img_file = working_file
        temp_img_file = None
        
        # Check if we need to convert TD0 to IMG first
        if self.current_file.lower().endswith('.td0'):
            # Convert TD0 to temporary IMG file
            temp_img_file = tempfile.NamedTemporaryFile(suffix='.img', delete=False).name
            
            try:
                options = ConversionOptions(
                    warn_only=True,
                    force_hp150=True,
                    fix_boot_sector=True,
                    generate_def=False
                )
                converter = FixedTD0Converter(options)
                result = converter.convert(self.current_file, temp_img_file)
                
                if not result.success:
                    messagebox.showerror("Conversion Error", f"Failed to convert TD0 to IMG: {result.error_message}")
                    return
                    
                img_file = temp_img_file
                
            except Exception as e:
                messagebox.showerror("Error", f"Error converting TD0 to IMG: {str(e)}")
                return
        
        # Generate DEF file
        try:
            geometry = GeometryDetector().detect_from_file(img_file)
            options = DefGenerationOptions()
            generator = DefGenerator(geometry, img_file, options)
            
            # Create temporary DEF file
            temp_def_file = tempfile.NamedTemporaryFile(suffix='.def', delete=False).name
            
            if not generator.save_def_file(temp_def_file):
                messagebox.showerror("Error", "Failed to generate DEF file")
                return
                
        except Exception as e:
            messagebox.showerror("Error", f"Error generating DEF file: {str(e)}")
            return
            
        # Show write dialog
        self._show_write_dialog(img_file, temp_def_file, temp_img_file)
        
    def _show_write_dialog(self, img_file, def_file, temp_img_file=None):
        """Show write dialog similar to HP150 toolkit"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Write Disk")
        dialog.geometry("600x550")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Variables
        drive_var = tk.IntVar(value=0)
        verify_var = tk.BooleanVar(value=True)
        
        # Main frame
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title and warning
        ttk.Label(main_frame, text="💾 Write to Disk", font=('Arial', 14, 'bold')).pack(pady=(0, 10))
        
        warning_frame = ttk.Frame(main_frame)
        warning_frame.pack(fill=tk.X, pady=(0, 20))
        
        warning_text = (
            "⚠️  WARNING: This operation will overwrite\n"
            "the entire contents of the floppy disk.\n"
            "This action cannot be undone!"
        )
        ttk.Label(warning_frame, text=warning_text, foreground='red', font=('Arial', 10, 'bold')).pack()
        
        # Image information
        info_frame = ttk.LabelFrame(main_frame, text="Image to Write", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(info_frame, text=f"Original: {os.path.basename(self.current_file)}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Image: {os.path.basename(img_file)}").pack(anchor=tk.W)
        
        if os.path.exists(img_file):
            size = os.path.getsize(img_file)
            ttk.Label(info_frame, text=f"Size: {size:,} bytes").pack(anchor=tk.W)
        
        # Drive selection
        drive_frame = ttk.LabelFrame(main_frame, text="Select Drive", padding="10")
        drive_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Radiobutton(drive_frame, text="Drive 0 (primary)", variable=drive_var, value=0).pack(anchor=tk.W)
        ttk.Radiobutton(drive_frame, text="Drive 1 (secondary)", variable=drive_var, value=1).pack(anchor=tk.W)
        
        # Options
        options_frame = ttk.LabelFrame(main_frame, text="Options", padding="10")
        options_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Checkbutton(options_frame, text="Verify after write", variable=verify_var).pack(anchor=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        def start_write():
            drive = drive_var.get()
            verify = verify_var.get()
            
            # Final confirmation
            if not messagebox.askyesno(
                "Final Confirmation",
                f"Are you SURE you want to write to drive {drive}?\n\n"
                "This operation will overwrite all contents of the floppy disk."
            ):
                return
            
            # Close dialog and show progress
            dialog.destroy()
            self._show_write_progress(img_file, def_file, drive, verify, temp_img_file)
        
        def cleanup_and_close():
            # Clean up temporary files
            if temp_img_file and os.path.exists(temp_img_file):
                try:
                    os.unlink(temp_img_file)
                except:
                    pass
            if os.path.exists(def_file):
                try:
                    os.unlink(def_file)
                except:
                    pass
            dialog.destroy()
        
        ttk.Button(button_frame, text="💾 Write", command=start_write).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="❌ Cancel", command=cleanup_and_close).pack(side=tk.LEFT)
        
        # Handle dialog close
        dialog.protocol("WM_DELETE_WINDOW", cleanup_and_close)
        
    def _show_write_progress(self, img_file, def_file, drive, verify, temp_img_file=None):
        """Show write progress dialog with console output"""
        progress_window = tk.Toplevel(self.root)
        progress_window.title(f"💾 Writing to Drive {drive}")
        progress_window.geometry("700x600")
        progress_window.transient(self.root)
        progress_window.grab_set()
        
        # Center the window
        progress_window.update_idletasks()
        x = (progress_window.winfo_screenwidth() // 2) - (progress_window.winfo_width() // 2)
        y = (progress_window.winfo_screenheight() // 2) - (progress_window.winfo_height() // 2)
        progress_window.geometry(f"+{x}+{y}")
        
        main_frame = ttk.Frame(progress_window, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(header_frame, text="💾 Disk Write Progress", font=('Arial', 14, 'bold')).pack()
        ttk.Label(header_frame, text=f"Image: {os.path.basename(img_file)} → Drive: {drive}", font=('Arial', 10)).pack(pady=(5, 0))
        
        # Current step
        status_frame = ttk.LabelFrame(main_frame, text="Current Step", padding="10")
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        current_step = ttk.Label(status_frame, text="Initializing...", font=('Arial', 11, 'bold'))
        current_step.pack(anchor=tk.W)
        
        progress_bar = ttk.Progressbar(status_frame, mode='indeterminate')
        progress_bar.pack(fill=tk.X, pady=(10, 0))
        progress_bar.start()
        
        # Console output
        console_frame = ttk.LabelFrame(main_frame, text="Greaseweazle Output", padding="10")
        console_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        console_text = scrolledtext.ScrolledText(
            console_frame,
            height=15,
            font=('Monaco', 9),
            wrap=tk.WORD
        )
        console_text.pack(fill=tk.BOTH, expand=True)
        
        # Control variables
        cancel_requested = {'value': False}
        current_process = {'process': None}
        
        def cancel_write():
            cancel_requested['value'] = True
            if current_process['process']:
                try:
                    current_process['process'].terminate()
                    console_text.insert(tk.END, "\n❌ Write cancelled by user\n")
                    console_text.see(tk.END)
                except:
                    pass
            progress_window.destroy()
        
        def cleanup_and_close():
            # Clean up temporary files
            if temp_img_file and os.path.exists(temp_img_file):
                try:
                    os.unlink(temp_img_file)
                except:
                    pass
            if os.path.exists(def_file):
                try:
                    os.unlink(def_file)
                except:
                    pass
            progress_window.destroy()
        
        # Cancel button
        cancel_frame = ttk.Frame(main_frame)
        cancel_frame.pack(fill=tk.X)
        
        cancel_btn = ttk.Button(cancel_frame, text="❌ Cancel", command=cancel_write)
        cancel_btn.pack(side=tk.RIGHT)
        
        def on_write_complete(return_code):
            """Called when write operation completes"""
            progress_bar.stop()
            
            # Change cancel button to close
            cancel_btn.config(text="✅ Close", command=cleanup_and_close)
            
            if return_code == 0:
                messagebox.showinfo(
                    "Success",
                    f"Image written successfully to drive {drive}\n"
                    f"The floppy disk is ready for use."
                )
                self.status_var.set("Write completed successfully")
            else:
                messagebox.showerror(
                    "Write Error",
                    f"Error writing to drive {drive} (code: {return_code})\n"
                    f"Check the console output for details."
                )
                self.status_var.set("Write failed")
        
        # Start the write process
        self._perform_write(img_file, def_file, drive, verify, console_text, current_step, 
                           progress_bar, on_write_complete, cancel_requested, current_process)
    
    def _perform_write(self, img_file, def_file, drive, verify, console_text, current_step, 
                      progress_bar, on_complete, cancel_requested, current_process):
        """Perform the actual write operation in a separate thread"""
        def write_thread():
            try:
                # Step 1: Reset Greaseweazle
                current_step.config(text="🔄 Resetting Greaseweazle...")
                console_text.insert(tk.END, "Resetting Greaseweazle...\n")
                console_text.see(tk.END)
                
                # Do the reset
                try:
                    # Configure delays
                    delays_result = subprocess.run(
                        ['gw', 'delays', '--step', '20000'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if delays_result.returncode == 0:
                        console_text.insert(tk.END, "✅ Delays configured (--step 20000)\n")
                    else:
                        console_text.insert(tk.END, f"⚠️ Warning configuring delays: {delays_result.stderr}\n")
                    
                    # Reset
                    reset_result = subprocess.run(
                        ['gw', 'reset'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if reset_result.returncode == 0:
                        console_text.insert(tk.END, "✅ Greaseweazle reset successfully\n")
                    else:
                        console_text.insert(tk.END, f"⚠️ Warning resetting: {reset_result.stderr}\n")
                    
                    console_text.see(tk.END)
                    
                except subprocess.TimeoutExpired:
                    console_text.insert(tk.END, "⚠️ Timeout resetting - continuing...\n")
                    console_text.see(tk.END)
                except Exception as e:
                    console_text.insert(tk.END, f"⚠️ Error resetting: {e} - continuing...\n")
                    console_text.see(tk.END)
                
                if cancel_requested['value']:
                    return
                
                # Step 2: Write using our writer module
                current_step.config(text="💾 Writing image to disk...")
                console_text.insert(tk.END, f"\nWriting {os.path.basename(img_file)} to drive {drive}...\n")
                console_text.see(tk.END)
                
                def progress_callback(message):
                    console_text.insert(tk.END, f"{message}\n")
                    console_text.see(tk.END)
                    
                def error_callback(message):
                    console_text.insert(tk.END, f"ERROR: {message}\n")
                    console_text.see(tk.END)
                
                writer = GreaseweazleWriter(progress_callback, error_callback)
                
                if not writer.is_available():
                    console_text.insert(tk.END, "ERROR: Greaseweazle not available\n")
                    console_text.see(tk.END)
                    self.root.after(0, lambda: on_complete(1))
                    return
                
                # Perform the write
                success = writer.write_disk(img_file, def_file, None, verify, False)
                
                if success:
                    console_text.insert(tk.END, "\n✅ Write completed successfully!\n")
                    console_text.see(tk.END)
                    self.root.after(0, lambda: on_complete(0))
                else:
                    console_text.insert(tk.END, "\n❌ Write failed!\n")
                    console_text.see(tk.END)
                    self.root.after(0, lambda: on_complete(1))
                
            except Exception as e:
                console_text.insert(tk.END, f"\nERROR: {str(e)}\n")
                console_text.see(tk.END)
                self.root.after(0, lambda: on_complete(1))
        
        # Start the write thread
        thread = threading.Thread(target=write_thread)
        thread.daemon = True
        thread.start()
    
    def _on_closing(self):
        """Handle application closing - cleanup temp files"""
        self._cleanup_temp_file()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = TD0ImageGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
