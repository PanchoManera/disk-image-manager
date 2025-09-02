#ifndef FILE_H
#define FILE_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Definiciones para compatibilidad
#define fget(buf, size, fp) fread(buf, 1, size, fp)

// Modo de apertura de archivo
#define FMODE_READ      "rb"
#define FMODE_WRITE     "wb"
#define FMODE_READWRITE "r+b"

// Función de apertura de archivo compatible
FILE *fopen_compat(const char *filename, const char *mode) {
    char new_mode[4] = {0};
    if (strchr(mode, 'r')) strcat(new_mode, "r");
    if (strchr(mode, 'w')) strcat(new_mode, "w");
    if (strchr(mode, 'b')) strcat(new_mode, "b");
    if (strchr(mode, '+')) strcat(new_mode, "+");
    return fopen(filename, new_mode);
}

#define fopen fopen_compat

#endif /* FILE_H */
