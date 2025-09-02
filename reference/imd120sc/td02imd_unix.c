#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <stdarg.h>

#define VERSION "1.20"
#define CYEAR "2025"

// Remove register keyword as it's deprecated
#define register

// Memory access functions
static unsigned char *memory_buffer = NULL;

unsigned char peek(unsigned seg, unsigned offset) {
    unsigned char *ptr = (unsigned char *)seg;
    return ptr[offset];
}

void poke(unsigned seg, unsigned offset, unsigned char value) {
    unsigned char *ptr = (unsigned char *)seg;
    ptr[offset] = value;
}

// Simplified format function
void _format_(unsigned args, unsigned char *buffer, const char *format, ...) {
    va_list ap;
    va_start(ap, format);
    vsprintf((char *)buffer, format, ap);
    va_end(ap);
}

// Simple abort function
void abort_program(const char *msg) {
    fprintf(stderr, "%s\n", msg);
    exit(1);
}

// Memory allocation
unsigned alloc_seg(unsigned size) {
    memory_buffer = (unsigned char *)malloc(size);
    if (!memory_buffer) {
        abort_program("Memory allocation failed");
    }
    return (unsigned)memory_buffer;
}

// File operations for binary mode
FILE *fopen_binary(const char *filename, const char *mode) {
    char binary_mode[4];
    snprintf(binary_mode, sizeof(binary_mode), "%sb", mode);
    return fopen(filename, binary_mode);
}

// Global variables
unsigned IOB_size = 4096;

// TD0 file structures
#include "TD02IMD.C"

// Main program modifications
int main(int argc, char *argv[]) {
    if (argc < 2) {
        printf("Usage: td02imd_unix inputfile.td0 [options]\n");
        return 1;
    }

    // Original main code here, with binary file handling
    File = argv[1];
    return main_td02imd(argc, argv);
}
