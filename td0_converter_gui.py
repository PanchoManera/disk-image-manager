import tkinter as tk
from tkinter import filedialog, messagebox
import os
import subprocess
from modules.fat_lister import FATHandler
from modules.td0_converter_lib import FixedTD0Converter, ConversionOptions
from modules.geometry_detector import GeometryDetector
from modules.def_generator import DefGenerator, DefGenerationOptions

import threading

class TD0ImageGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("TD0/IMG File Manager")
        self.current_file = None
        self.greaseweazle_path = None
        self.create_widgets()

    def create_widgets(self):
        # Frame for file operations
        self.frame = tk.Frame(self.root)
        self.frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.load_button = tk.Button(self.frame, text="Load TD0/IMG", command=self.load_image)
        self.load_button.pack(fill=tk.X)

        self.info_button = tk.Button(self.frame, text="Sector Info", command=self.show_sector_info)
        self.info_button.pack(fill=tk.X)

        self.list_button = tk.Button(self.frame, text="List Files", command=self.list_files)
        self.list_button.pack(fill=tk.X)

        self.extract_button = tk.Button(self.frame, text="Extract Files", command=self.extract_files)
        self.extract_button.pack(fill=tk.X)

        # Botones para funciones de Greaseweazle
        self.read_disk_button = tk.Button(self.frame, text="Read Disk", command=self.read_disk, state=tk.DISABLED)
        self.read_disk_button.pack(fill=tk.X)

        self.write_disk_button = tk.Button(self.frame, text="Write Disk (Future)", state=tk.DISABLED)
        self.write_disk_button.pack(fill=tk.X)
        
        # Verificar si Greaseweazle está disponible y activar botones
        self.check_greaseweazle_available()

        # Menu
        self.menu = tk.Menu(self.root)
        self.root.config(menu=self.menu)

        self.file_menu = tk.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(label="Convert TD0 to IMG", command=self.convert_td0_to_img)
        self.file_menu.add_command(label="Create .def from IMG/TD0", command=self.create_def)

    def load_image(self):
        filetypes = [
            ("TD0 files", "*.td0"),
            ("TD0 files", "*.TD0"),
            ("IMG files", "*.img"),
            ("IMG files", "*.IMG"),
            ("All files", "*.*")
        ]
        filepath = filedialog.askopenfilename(title="Open Image File", filetypes=filetypes)
        if filepath:
            self.current_file = filepath
            self.root.title(f"TD0/IMG File Manager - {os.path.basename(filepath)}")
    
    def run_in_thread(self, target, *args):
        """Run a function in a separate thread to avoid blocking the GUI"""
        thread = threading.Thread(target=target, args=args)
        thread.daemon = True  # Dies when main thread dies
        thread.start()

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
                        self.greaseweazle_path = path
                        # Activar el botón Read Disk solo si el dispositivo está conectado
                        self.read_disk_button.config(state=tk.NORMAL)
                        return
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                continue
        
        # Si no se encontró Greaseweazle o no está conectado, desactivar el botón
        self.greaseweazle_path = None
        self.read_disk_button.config(state=tk.DISABLED)

    def is_greaseweazle_available(self) -> bool:
        """Verifica si Greaseweazle está disponible en el sistema."""
        return self.greaseweazle_path is not None

    def show_sector_info(self):
        if not self.current_file:
            messagebox.showerror("Error", "No file loaded")
            return
        self.run_in_thread(self._show_sector_info)

    def _show_sector_info(self):
        try:
            geometry = GeometryDetector().detect_from_file(self.current_file)
            
            # Use after() to safely update GUI from thread
            self.root.after(0, self._display_sector_info, geometry)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error reading sector info: {str(e)}"))

    def _display_sector_info(self, geometry):
        # Create sector info window
        sector_window = tk.Toplevel(self.root)
        sector_window.title("Sector Information")
        sector_window.geometry("600x400")
        
        # Create text widget with scrollbar
        text_frame = tk.Frame(sector_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        text_widget = tk.Text(text_frame, wrap=tk.WORD, state=tk.NORMAL)
        scrollbar = tk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
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
        
        text_widget.insert(tk.END, info_text)
        text_widget.config(state=tk.DISABLED)

    def list_files(self):
        if not self.current_file:
            messagebox.showerror("Error", "No file loaded")
            return
        self.run_in_thread(self._list_files)

    def _list_files(self):
        try:
            with FATHandler(self.current_file) as handler:
                files = handler.list_visible_files()
                # Use after() to safely update GUI from thread
                self.root.after(0, self._display_file_list, files)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error reading files: {str(e)}"))
    
    def _display_file_list(self, files):
        file_list_window = tk.Toplevel(self.root)
        file_list_window.title("List of Files")
        file_list_window.geometry("500x400")
        
        # Create frame for file list with scrollbar
        list_frame = tk.Frame(file_list_window)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create listbox with scrollbar
        listbox = tk.Listbox(list_frame)
        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL, command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Add files to listbox
        for file in files:
            listbox.insert(tk.END, f"{file.full_name} - {file.size} bytes")

    def extract_files(self):
        if not self.current_file:
            messagebox.showerror("Error", "No file loaded")
            return

        directory = filedialog.askdirectory(title="Select Extraction Directory")
        if directory:
            self.run_in_thread(self._extract_files, directory)
    
    def _extract_files(self, directory):
        try:
            with FATHandler(self.current_file) as handler:
                extracted_files = handler.extract_files(directory)
                success_msg = f"Files extracted to {directory}\n{len(extracted_files)} files extracted"
                self.root.after(0, lambda: messagebox.showinfo("Extraction Complete", success_msg))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error extracting files: {str(e)}"))

    def convert_td0_to_img(self):
        if not self.current_file:
            messagebox.showerror("Error", "No file loaded")
            return

        save_path = filedialog.asksaveasfilename(defaultextension=".img", filetypes=[("IMG files", "*.img")])
        if save_path:
            self.run_in_thread(self._convert_td0_to_img, save_path)
    
    def _convert_td0_to_img(self, save_path):
        try:
            options = ConversionOptions(warn_only=True, force_hp150=True, fix_boot_sector=True, verbose=False)
            converter = FixedTD0Converter(options)
            result = converter.convert(self.current_file, save_path)
            if result.success:
                self.root.after(0, lambda: messagebox.showinfo("Conversion Success", f"Converted to {save_path}"))
                # Cargar la imagen resultante
                self.current_file = save_path
                self.root.title(f"TD0/IMG File Manager - {os.path.basename(save_path)}")
                self.root.after(0, lambda: messagebox.showinfo("Conversion Success", f"Converted to {save_path}\nImagen cargada en la GUI."))
            else:
                self.root.after(0, lambda: messagebox.showerror("Conversion Error", result.error_message))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error during conversion: {str(e)}"))

    def create_def(self):
        if not self.current_file:
            messagebox.showerror("Error", "No file loaded")
            return

        save_path = filedialog.asksaveasfilename(defaultextension=".def", filetypes=[("DEF files", "*.def")])
        if save_path:
            self.run_in_thread(self._create_def, save_path)
    
    def _create_def(self, save_path):
        try:
            geometry = GeometryDetector().detect_from_file(self.current_file)
            options = DefGenerationOptions()
            generator = DefGenerator(geometry, self.current_file, options)
            if generator.save_def_file(save_path):
                self.root.after(0, lambda: messagebox.showinfo("DEF File Created", f"DEF file saved as {save_path}"))
            else:
                self.root.after(0, lambda: messagebox.showerror("Error", "Failed to create DEF file"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error creating DEF file: {str(e)}"))

    def read_disk(self):
        """Función para leer un disco usando Greaseweazle"""
        if not self.is_greaseweazle_available():
            messagebox.showerror("Error", "Greaseweazle no está disponible")
            return

        # Ruta donde se guardará la imagen SCP
        save_path = filedialog.asksaveasfilename(
            defaultextension=".scp",
            filetypes=[("SCP files", "*.scp")],
            title="Guardar imagen de disco como..."
        )
        if not save_path:
            return

        # Ejecutar la lectura en un hilo separado
        self.run_in_thread(self._read_disk, save_path)

    def _read_disk(self, save_path: str):
        """Ejecuta el comando de lectura de Greaseweazle"""
        try:
            # Construir el comando para leer el disco
            cmd = [self.greaseweazle_path, "read", "--format", "scp", save_path]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                universal_newlines=True
            )
            
            # Procesar la salida en tiempo real
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    # Actualizar GUI con el progreso
                    self.root.after(0, lambda msg=output.strip(): 
                        messagebox.showinfo("Progreso", msg))
            
            return_code = process.wait()
            if return_code == 0:
                # Éxito - cargar la imagen en la GUI
                self.root.after(0, lambda: [
                    messagebox.showinfo("Éxito", f"Disco leído exitosamente y guardado como {save_path}"),
                    self.load_scp_image(save_path)
                ])
            else:
                error = process.stderr.read()
                self.root.after(0, lambda: 
                    messagebox.showerror("Error", f"Error al leer el disco: {error}"))
                
        except Exception as e:
            self.root.after(0, lambda: 
                messagebox.showerror("Error", f"Error al ejecutar Greaseweazle: {str(e)}"))

    def load_scp_image(self, scp_path: str):
        """Carga una imagen SCP en la GUI principal"""
        self.current_file = scp_path
        self.root.title(f"TD0/IMG File Manager - {os.path.basename(scp_path)}")

def run_gui():
    root = tk.Tk()
    app = TD0ImageGUI(root)
    root.mainloop()

if __name__ == "__main__":
    run_gui()
