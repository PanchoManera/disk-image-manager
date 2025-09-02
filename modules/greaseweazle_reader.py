#!/usr/bin/env python3
"""
Módulo backend para leer discos usando Greaseweazle.

Este módulo proporciona funcionalidad para leer discos reales usando Greaseweazle
y generar archivos de imagen y definición.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any


class GreaseweazleReader:
    """
    Clase para manejar la lectura de discos usando Greaseweazle.
    """
    
    def __init__(self, progress_callback: Optional[Callable[[str], None]] = None,
                 error_callback: Optional[Callable[[str], None]] = None):
        """
        Inicializa el lector de Greaseweazle.
        
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
            print(f"[ERROR] {message}", file=sys.stderr)
    
    def is_available(self) -> bool:
        """
        Verifica si Greaseweazle está disponible en el sistema.
        
        Returns:
            bool: True si Greaseweazle está disponible, False en caso contrario
        """
        return self.greaseweazle_path is not None
    
    def get_devices(self) -> List[str]:
        """
        Obtiene la lista de dispositivos Greaseweazle disponibles.
        
        Returns:
            List[str]: Lista de dispositivos disponibles
        """
        if not self.is_available():
            return []
        
        try:
            result = subprocess.run([self.greaseweazle_path, "info"], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=10)
            if result.returncode == 0:
                devices = []
                for line in result.stdout.split('\n'):
                    if 'Device' in line or 'Serial' in line:
                        devices.append(line.strip())
                return devices
            else:
                self._report_error(f"Error al obtener dispositivos: {result.stderr}")
                return []
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            self._report_error(f"Error al comunicarse con Greaseweazle: {e}")
            return []
    
    def read_flux(self, output_path: str, drive: int = 0) -> bool:
        """
        Lee el flux level del disco y lo guarda en formato SCP.
        
        Args:
            output_path: Ruta donde guardar el archivo SCP
            drive: Número de unidad a leer (0 o 1)
            
        Returns:
            bool: True si la lectura fue exitosa, False en caso contrario
        """
        if not self.is_available():
            self._report_error("Greaseweazle no está disponible")
            return False
        
        # Construir comando
        cmd = [self.greaseweazle_path, "read", f"--drive={drive}"]
        
        # Agregar archivo de salida
        cmd.append(output_path)
        
        self._report_progress(f"Iniciando lectura de flux del disco a {output_path}")
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
                self._report_progress("Lectura de flux completada exitosamente")
                return True
            else:
                error_output = process.stderr.read()
                self._report_error(f"Error en la lectura de flux: {error_output}")
                return False
                
        except Exception as e:
            self._report_error(f"Error al ejecutar Greaseweazle: {e}")
            return False

    def read_disk(self, output_path: str, device: Optional[str] = None,
                  format_type: str = "ibm.mfm", retries: int = 3) -> bool:
        """
        Lee un disco real y guarda la imagen.
        
        Args:
            output_path: Ruta donde guardar la imagen (sin extensión)
            device: Dispositivo específico a usar (opcional)
            format_type: Tipo de formato del disco (por defecto "ibm.mfm")
            retries: Número de reintentos para sectores defectuosos
            
        Returns:
            bool: True si la lectura fue exitosa, False en caso contrario
        """
        if not self.is_available():
            self._report_error("Greaseweazle no está disponible")
            return False
        
        # Construir comando
        cmd = [self.greaseweazle_path, "read"]
        
        # Agregar dispositivo si se especifica
        if device:
            cmd.extend(["--device", device])
        
        # Agregar formato
        cmd.extend(["--format", format_type])
        
        # Agregar reintentos
        cmd.extend(["--retries", str(retries)])
        
        # Agregar archivo de salida
        cmd.append(output_path)
        
        self._report_progress(f"Iniciando lectura del disco a {output_path}")
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
                self._report_progress("Lectura completada exitosamente")
                return True
            else:
                error_output = process.stderr.read()
                self._report_error(f"Error en la lectura: {error_output}")
                return False
                
        except Exception as e:
            self._report_error(f"Error al ejecutar Greaseweazle: {e}")
            return False
    
    def get_read_command(self, output_path: str, device: Optional[str] = None,
                        format_type: str = "ibm.mfm", retries: int = 3) -> Optional[str]:
        """
        Genera el comando que sería ejecutado para leer el disco.
        
        Args:
            output_path: Ruta donde guardar la imagen (sin extensión)
            device: Dispositivo específico a usar (opcional)
            format_type: Tipo de formato del disco (por defecto "ibm.mfm")
            retries: Número de reintentos para sectores defectuosos
            
        Returns:
            str: Comando que sería ejecutado, o None si hay errores
        """
        if not self.is_available():
            return None
        
        # Construir comando
        cmd = [self.greaseweazle_path, "read"]
        
        # Agregar dispositivo si se especifica
        if device:
            cmd.extend(["--device", device])
        
        # Agregar formato
        cmd.extend(["--format", format_type])
        
        # Agregar reintentos
        cmd.extend(["--retries", str(retries)])
        
        # Agregar archivo de salida
        cmd.append(output_path)
        
        return ' '.join(cmd)


def read_flux_simple(output_path: str, drive: int = 0) -> bool:
    """
    Función simple para leer flux de un disco sin necesidad de instanciar la clase.
    
    Args:
        output_path: Ruta donde guardar el archivo SCP
        drive: Número de unidad a leer (0 o 1)
        
    Returns:
        bool: True si la lectura fue exitosa, False en caso contrario
    """
    reader = GreaseweazleReader()
    return reader.read_flux(output_path, drive)


def read_disk_simple(output_path: str, device: Optional[str] = None,
                    format_type: str = "ibm.mfm", retries: int = 3) -> bool:
    """
    Función simple para leer un disco sin necesidad de instanciar la clase.
    
    Args:
        output_path: Ruta donde guardar la imagen (sin extensión)
        device: Dispositivo específico a usar (opcional)
        format_type: Tipo de formato del disco (por defecto "ibm.mfm")
        retries: Número de reintentos para sectores defectuosos
        
    Returns:
        bool: True si la lectura fue exitosa, False en caso contrario
    """
    reader = GreaseweazleReader()
    return reader.read_disk(output_path, device, format_type, retries)


def get_available_devices() -> List[str]:
    """
    Función simple para obtener dispositivos disponibles.
    
    Returns:
        List[str]: Lista de dispositivos disponibles
    """
    reader = GreaseweazleReader()
    return reader.get_devices()


def is_greaseweazle_available() -> bool:
    """
    Función simple para verificar si Greaseweazle está disponible.
    
    Returns:
        bool: True si Greaseweazle está disponible, False en caso contrario
    """
    reader = GreaseweazleReader()
    return reader.is_available()


if __name__ == "__main__":
    # Ejemplo de uso
    print("=== Greaseweazle Reader Test ===")
    
    reader = GreaseweazleReader()
    
    print(f"Greaseweazle disponible: {reader.is_available()}")
    
    if reader.is_available():
        print("Dispositivos disponibles:")
        devices = reader.get_devices()
        for device in devices:
            print(f"  - {device}")
        
        # Ejemplo de comando (sin ejecutar)
        example_cmd = reader.get_read_command("test_disk")
        if example_cmd:
            print(f"Comando de ejemplo: {example_cmd}")
    else:
        print("Greaseweazle no está disponible en el sistema")
