#!/usr/bin/env python3
"""
Módulo para convertir archivos SCP a otros formatos usando Greaseweazle.

Este módulo proporciona funcionalidad para convertir archivos SCP (capturados
con flux) a otros formatos usando un archivo de definición.
"""

import os
import subprocess
from typing import Optional, Callable, List, Dict, Any

class SCPConverter:
    """
    Clase para manejar la conversión de archivos SCP.
    """
    
    def __init__(self, progress_callback: Optional[Callable[[str], None]] = None,
                 error_callback: Optional[Callable[[str], None]] = None):
        """
        Inicializa el conversor SCP.
        
        Args:
            progress_callback: Función para reportar progreso (opcional)
            error_callback: Función para reportar errores (opcional)
        """
        self.progress_callback = progress_callback
        self.error_callback = error_callback
        self.greaseweazle_path = None
        self._find_greaseweazle()
    
    def _find_greaseweazle(self) -> None:
        """
        Busca el ejecutable de Greaseweazle en el sistema.
        """
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
                result = subprocess.run([path, "--version"], 
                                      capture_output=True, 
                                      text=True, 
                                      timeout=5)
                if result.returncode == 0:
                    self.greaseweazle_path = path
                    self._report_progress(f"Greaseweazle encontrado en: {path}")
                    return
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                continue
        
        self._report_error("Greaseweazle no encontrado en el sistema")
    
    def _report_progress(self, message: str) -> None:
        """Reporta progreso usando el callback si está disponible."""
        if self.progress_callback:
            self.progress_callback(message)
        else:
            print(f"[INFO] {message}")
    
    def _report_error(self, message: str) -> None:
        """Reporta errores usando el callback si está disponible."""
        if self.error_callback:
            self.error_callback(message)
        else:
            print(f"[ERROR] {message}")
    
    def is_available(self) -> bool:
        """
        Verifica si Greaseweazle está disponible en el sistema.
        
        Returns:
            bool: True si Greaseweazle está disponible, False en caso contrario
        """
        return self.greaseweazle_path is not None
    
    def get_known_formats(self) -> List[str]:
        """
        Obtiene la lista de formatos predefinidos soportados por Greaseweazle.
        
        Returns:
            List[str]: Lista de formatos predefinidos
        """
        if not self.is_available():
            return []
            
        try:
            result = subprocess.run(
                [self.greaseweazle_path, "convert", "--help"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return []
                
            formats = []
            in_formats = False
            for line in result.stdout.split('\n'):
                if 'Known formats:' in line:
                    in_formats = True
                    continue
                elif in_formats and line.strip():
                    # Cada línea puede contener varios formatos separados por espacios
                    formats.extend(line.strip().split())
                elif in_formats and not line.strip():
                    break
                    
            return formats
        except Exception as e:
            self._report_error(f"Error obteniendo formatos: {e}")
            return []

    def convert_with_builtin_format(self, scp_path: str, format_name: str, output_path: str) -> bool:
        """
        Convierte un archivo SCP a IMG usando un formato predefinido de Greaseweazle.
        
        Args:
            scp_path: Ruta al archivo SCP
            format_name: Nombre del formato predefinido
            output_path: Ruta donde guardar el archivo IMG
            
        Returns:
            bool: True si la conversión fue exitosa, False en caso contrario
        """
        if not self.is_available():
            self._report_error("Greaseweazle no está disponible")
            return False
            
        cmd = [self.greaseweazle_path, "convert"]
        cmd.extend(["--format", format_name])
        cmd.extend([scp_path, output_path])
        
        return self._execute_convert(cmd, scp_path, output_path)

    def convert_with_def_file(self, scp_path: str, def_path: str, format_name: str, output_path: str) -> bool:
        """
        Convierte un archivo SCP a IMG usando un archivo de definición específico.
        
        Args:
            scp_path: Ruta al archivo SCP
            def_path: Ruta al archivo DEF
            format_name: Nombre del formato dentro del archivo DEF
            output_path: Ruta donde guardar el archivo IMG
            
        Returns:
            bool: True si la conversión fue exitosa, False en caso contrario
        """
        if not self.is_available():
            self._report_error("Greaseweazle no está disponible")
            return False
            
        cmd = [self.greaseweazle_path, "convert"]
        cmd.extend(["--diskdefs", def_path])
        cmd.extend(["--format", format_name])
        cmd.extend([scp_path, output_path])
        
        return self._execute_convert(cmd, scp_path, output_path)

    def convert_with_def_format(self, scp_path: str, def_path: str, output_path: str) -> bool:
        """
        Convierte un archivo SCP a IMG usando el formato especificado en un archivo DEF.
        Este es el caso donde el archivo DEF ya define el formato.
        
        Args:
            scp_path: Ruta al archivo SCP
            def_path: Ruta al archivo DEF que define el formato
            output_path: Ruta donde guardar el archivo IMG
            
        Returns:
            bool: True si la conversión fue exitosa, False en caso contrario
        """
        if not self.is_available():
            self._report_error("Greaseweazle no está disponible")
            return False
            
        cmd = [self.greaseweazle_path, "convert"]
        cmd.extend(["--format", def_path])
        cmd.extend([scp_path, output_path])
        
        return self._execute_convert(cmd, scp_path, output_path)

    def _execute_convert(self, cmd: List[str], scp_path: str, output_path: str) -> bool:
        """
        Convierte un archivo SCP a IMG usando un archivo de definición.
        
        Args:
            scp_path: Ruta al archivo SCP
            def_path: Ruta al archivo DEF que define el formato
            output_path: Ruta donde guardar el archivo IMG
            
        Returns:
            bool: True si la conversión fue exitosa, False en caso contrario
        """
        if not self.is_available():
            self._report_error("Greaseweazle no está disponible")
            return False
        
        # Construir comando
        cmd = [self.greaseweazle_path, "convert"]
        
        # Agregar archivo def como formato
        cmd.extend(["--format", def_path])
        
        # Agregar archivos de entrada y salida
        cmd.extend([scp_path, output_path])
        
        self._report_progress(f"Iniciando conversión de {scp_path} a {output_path}")
        self._report_progress(f"Usando definición: {def_path}")
        self._report_progress(f"Comando: {' '.join(cmd)}")
        
        try:
            # Ejecutar comando
            process = subprocess.Popen(cmd, 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.PIPE,
                                     text=True,
                                     universal_newlines=True)
            
            # Leer salida en tiempo real
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self._report_progress(output.strip())
            
            # Esperar a que termine
            return_code = process.wait()
            
            if return_code == 0:
                self._report_progress("Conversión completada exitosamente")
                return True
            else:
                error_output = process.stderr.read()
                self._report_error(f"Error en la conversión: {error_output}")
                return False
                
        except Exception as e:
            self._report_error(f"Error al ejecutar Greaseweazle: {e}")
            return False
            

def convert_scp_simple(scp_path: str, def_path: str, output_path: str) -> bool:
    """
    Función simple para convertir un archivo SCP a IMG sin necesidad de instanciar la clase.
    
    Args:
        scp_path: Ruta al archivo SCP
        def_path: Ruta al archivo DEF que define el formato
        output_path: Ruta donde guardar el archivo IMG
        
    Returns:
        bool: True si la conversión fue exitosa, False en caso contrario
    """
    converter = SCPConverter()
    return converter.convert_to_img(scp_path, def_path, output_path)
