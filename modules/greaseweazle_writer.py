#!/usr/bin/env python3
"""
Módulo para escribir imágenes de disco usando Greaseweazle.

Este módulo proporciona funcionalidad para grabar imágenes de disco (.img) 
en discos reales usando Greaseweazle y archivos de definición (.def).
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any

# Importar funciones comunes del módulo reader
from greaseweazle_reader import GreaseweazleReader


class GreaseweazleWriter(GreaseweazleReader):
    """
    Clase para manejar la escritura de imágenes de disco usando Greaseweazle.
    Hereda funcionalidad común de GreaseweazleReader.
    """
    
    def __init__(self, progress_callback: Optional[Callable[[str], None]] = None,
                 error_callback: Optional[Callable[[str], None]] = None):
        """
        Inicializa el escritor de Greaseweazle.
        
        Args:
            progress_callback: Función para reportar progreso (opcional)
            error_callback: Función para reportar errores (opcional)
        """
        super().__init__(progress_callback, error_callback)
    
    
    def validate_files(self, img_path: str, def_path: str) -> bool:
        """
        Valida que los archivos de imagen y definición existan y sean válidos.
        
        Args:
            img_path: Ruta al archivo de imagen (.img)
            def_path: Ruta al archivo de definición (.def)
            
        Returns:
            bool: True si ambos archivos son válidos, False en caso contrario
        """
        # Verificar que los archivos existan
        if not os.path.exists(img_path):
            self._report_error(f"Archivo de imagen no encontrado: {img_path}")
            return False
        
        if not os.path.exists(def_path):
            self._report_error(f"Archivo de definición no encontrado: {def_path}")
            return False
        
        # Verificar extensiones
        if not img_path.lower().endswith('.img'):
            self._report_error(f"El archivo debe tener extensión .img: {img_path}")
            return False
        
        if not def_path.lower().endswith('.def'):
            self._report_error(f"El archivo debe tener extensión .def: {def_path}")
            return False
        
        # Verificar que el archivo de imagen no esté vacío
        if os.path.getsize(img_path) == 0:
            self._report_error(f"El archivo de imagen está vacío: {img_path}")
            return False
        
        # Verificar que el archivo .def sea válido (básico)
        try:
            with open(def_path, 'r') as f:
                content = f.read()
                if 'cyls' not in content or 'heads' not in content:
                    self._report_error(f"El archivo .def no parece válido: {def_path}")
                    return False
        except Exception as e:
            self._report_error(f"Error al leer archivo .def: {e}")
            return False
        
        return True
    
    def write_disk(self, img_path: str, def_path: str, device: Optional[str] = None,
                   verify: bool = True, force: bool = False) -> bool:
        """
        Escribe una imagen de disco en un disco real usando Greaseweazle.
        
        Args:
            img_path: Ruta al archivo de imagen (.img)
            def_path: Ruta al archivo de definición (.def)
            device: Dispositivo específico a usar (opcional)
            verify: Si verificar la escritura después de escribir
            force: Si forzar la escritura sin confirmación
            
        Returns:
            bool: True si la escritura fue exitosa, False en caso contrario
        """
        if not self.is_available():
            self._report_error("Greaseweazle no está disponible")
            return False
        
        if not self.validate_files(img_path, def_path):
            return False
        
        # Construir comando
        cmd = [self.greaseweazle_path, "write"]
        
        # Agregar archivo de definición
        cmd.extend(["--def", def_path])
        
        # Agregar dispositivo si se especifica
        if device:
            cmd.extend(["--device", device])
        
        # Agregar opciones adicionales
        if not verify:
            cmd.append("--no-verify")
        
        if force:
            cmd.append("--force")
        
        # Agregar archivo de imagen
        cmd.append(img_path)
        
        self._report_progress(f"Iniciando escritura de {img_path} usando {def_path}")
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
                self._report_progress("Escritura completada exitosamente")
                if verify:
                    self._report_progress("Verificación completada")
                return True
            else:
                error_output = process.stderr.read()
                self._report_error(f"Error en la escritura: {error_output}")
                return False
                
        except Exception as e:
            self._report_error(f"Error al ejecutar Greaseweazle: {e}")
            return False
    
    def get_write_command(self, img_path: str, def_path: str, device: Optional[str] = None,
                         verify: bool = True, force: bool = False) -> Optional[str]:
        """
        Genera el comando que sería ejecutado para escribir el disco.
        
        Args:
            img_path: Ruta al archivo de imagen (.img)
            def_path: Ruta al archivo de definición (.def)
            device: Dispositivo específico a usar (opcional)
            verify: Si verificar la escritura después de escribir
            force: Si forzar la escritura sin confirmación
            
        Returns:
            str: Comando que sería ejecutado, o None si hay errores
        """
        if not self.is_available():
            return None
        
        if not self.validate_files(img_path, def_path):
            return None
        
        # Construir comando
        cmd = [self.greaseweazle_path, "write"]
        
        # Agregar archivo de definición
        cmd.extend(["--def", def_path])
        
        # Agregar dispositivo si se especifica
        if device:
            cmd.extend(["--device", device])
        
        # Agregar opciones adicionales
        if not verify:
            cmd.append("--no-verify")
        
        if force:
            cmd.append("--force")
        
        # Agregar archivo de imagen
        cmd.append(img_path)
        
        return ' '.join(cmd)


def write_disk_simple(img_path: str, def_path: str, device: Optional[str] = None,
                     verify: bool = True, force: bool = False) -> bool:
    """
    Función simple para escribir un disco sin necesidad de instanciar la clase.
    
    Args:
        img_path: Ruta al archivo de imagen (.img)
        def_path: Ruta al archivo de definición (.def)
        device: Dispositivo específico a usar (opcional)
        verify: Si verificar la escritura después de escribir
        force: Si forzar la escritura sin confirmación
        
    Returns:
        bool: True si la escritura fue exitosa, False en caso contrario
    """
    writer = GreaseweazleWriter()
    return writer.write_disk(img_path, def_path, device, verify, force)


# Usar las funciones del reader para evitar duplicación
from greaseweazle_reader import get_available_devices, is_greaseweazle_available


if __name__ == "__main__":
    # Ejemplo de uso
    print("=== Greaseweazle Writer Test ===")
    
    writer = GreaseweazleWriter()
    
    print(f"Greaseweazle disponible: {writer.is_available()}")
    
    if writer.is_available():
        print("Dispositivos disponibles:")
        devices = writer.get_devices()
        for device in devices:
            print(f"  - {device}")
        
        # Ejemplo de comando (sin ejecutar)
        example_cmd = writer.get_write_command("example.img", "example.def")
        if example_cmd:
            print(f"Comando de ejemplo: {example_cmd}")
    else:
        print("Greaseweazle no está disponible en el sistema")
