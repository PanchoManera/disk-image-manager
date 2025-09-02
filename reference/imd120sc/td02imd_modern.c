#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <ctype.h>

#define VERSION "1.20"
#define CYEAR "2025"

// LZSS parameters
#define SBSIZE    4096        // Size of Ring buffer
#define LASIZE    60          // Size of Look-ahead buffer
#define THRESHOLD 2           // Minimum match for compress

// Huffman coding parameters
#define N_CHAR   (256-THRESHOLD+LASIZE) // Character code (= 0..N_CHAR-1)
#define TSIZE    (N_CHAR*2-1)           // Size of table
#define ROOT     (TSIZE-1)              // Root position
#define MAX_FREQ 0x8000                 // Update when cumulative frequency reaches this value

// Teledisk sector flag meanings
#define SEC_DUP     0x01        // Sector was duplicated
#define SEC_CRC     0x02        // Sector has CRC error
#define SEC_DAM     0x04        // Sector has Deleted Address Mark
#define SEC_DOS     0x10        // Sector not allocated
#define SEC_NODAT   0x20        // Sector has no data field
#define SEC_NOID    0x40        // Sector has no ID field

// Huffman decoder tables
static const unsigned char d_code[256] = {
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01,
    0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02,
    0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03,
    0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x05, 0x05, 0x05, 0x05, 0x05, 0x05, 0x05, 0x05,
    0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07,
    0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x09, 0x09, 0x09, 0x09, 0x09, 0x09, 0x09, 0x09,
    0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0B, 0x0B, 0x0B, 0x0B, 0x0B, 0x0B, 0x0B, 0x0B,
    0x0C, 0x0C, 0x0C, 0x0C, 0x0D, 0x0D, 0x0D, 0x0D, 0x0E, 0x0E, 0x0E, 0x0E, 0x0F, 0x0F, 0x0F, 0x0F,
    0x10, 0x10, 0x10, 0x10, 0x11, 0x11, 0x11, 0x11, 0x12, 0x12, 0x12, 0x12, 0x13, 0x13, 0x13, 0x13,
    0x14, 0x14, 0x14, 0x14, 0x15, 0x15, 0x15, 0x15, 0x16, 0x16, 0x16, 0x16, 0x17, 0x17, 0x17, 0x17,
    0x18, 0x18, 0x19, 0x19, 0x1A, 0x1A, 0x1B, 0x1B, 0x1C, 0x1C, 0x1D, 0x1D, 0x1E, 0x1E, 0x1F, 0x1F,
    0x20, 0x20, 0x21, 0x21, 0x22, 0x22, 0x23, 0x23, 0x24, 0x24, 0x25, 0x25, 0x26, 0x26, 0x27, 0x27,
    0x28, 0x28, 0x29, 0x29, 0x2A, 0x2A, 0x2B, 0x2B, 0x2C, 0x2C, 0x2D, 0x2D, 0x2E, 0x2E, 0x2F, 0x2F,
    0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x3B, 0x3C, 0x3D, 0x3E, 0x3F
};

static const unsigned char d_len[] = { 2, 2, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 6, 6, 6, 7 };

// Text lookup tables
static const char *dt_text[] = { "5.25-96/48", "5.25", "5.25-96", "3.5", "3.5", "8\"", "3.5" };
static const char *dr_txt[] = { "LD", "LD", "HD" };
static const char *dr_step[] = { "S", "D", "E" };

// Global variables
unsigned parent[TSIZE+N_CHAR];  // parent nodes (0..T-1) and leaf positions (rest)
unsigned son[TSIZE];            // pointers to child nodes (son[], son[]+1)
unsigned freq[TSIZE+1];         // frequency table
unsigned Bits, Bitbuff;         // buffered bit count and left-aligned bit buffer
unsigned GBcheck;               // Getbyte check down-counter
unsigned GBr;                   // Ring buffer position
unsigned GBi;                   // Decoder index
unsigned GBj;                   // Decoder index
unsigned GBk;                   // Decoder index
unsigned char Debug;            // Debug mode
unsigned char Warn;             // Warning level
unsigned char Wmask;            // Warning mask
unsigned char GBstate;          // Decoder state
unsigned char Eof;             // End-of-file indicator
unsigned char Advcomp;         // Advanced compression enabled
unsigned char ring_buff[SBSIZE+LASIZE-1]; // text buffer for match strings

// File pointers
FILE *fpi;                     // Input file pointer
FILE *fpo;                     // Output file pointer

// Main disk structures
#pragma pack(push, 1)  // Asegurar alineación de 1 byte
struct td0_header {
    unsigned short Sig;      // TD Signature
    unsigned char Sequence;  // Volume sequence number
    unsigned char Checksig;  // Check signature for multi-volume sets
    unsigned char TDversion; // Teledisk version
    unsigned char Datarate;  // Data rate
    unsigned char Drivetype; // Source drive type
    unsigned char Stepping;  // Stepping type
    unsigned char DOSmode;   // Read according to DOS allocation
    unsigned char Sides;     // # of sides read
    unsigned short Hcrc;     // Header crc
} Header;
#pragma pack(pop)

// Track header
#pragma pack(push, 1)  // Asegurar alineación de 1 byte para todas las estructuras
struct track_header {
    unsigned char Tsectors;    // number sectors/track
    unsigned char Tcylinder;   // Physical cylinder
    unsigned char Tside;       // Physical side
    unsigned char Tcrc;        // Crc of header
} Thead;

// Sector header
struct sector_header {
    unsigned char Scylinder;   // Cylinder number in ID field
    unsigned char Sside;       // Side number in ID field
    unsigned char Ssector;     // Sector number in ID field
    unsigned char Ssize;       // Size of sector
    unsigned char Sflags;      // Sector control flags
    unsigned char Scrc;        // Sector header CRC
} Shead;

// Data block header
struct data_header {
    unsigned short Doffset;    // Offset to next data block
    unsigned char Dmethod;     // Method of compression
} Dhead;
#pragma pack(pop)

// Function prototypes
void init_decompress(void);
void update(int c);
unsigned GetChar(void);
unsigned GetBit(void);
unsigned GetByte(void);
unsigned DecodeChar(void);
unsigned DecodePosition(void);
void error(const char *format, ...);
void warn(const char *format, ...);
int getbyte(void);
unsigned getword(void);
int getblock(unsigned char *p, unsigned size, const char *e);
void process_sector(void);
int issame(unsigned char *d, unsigned char v, unsigned s);
void write_data(unsigned index);
void remove_sectors(void);
unsigned getnum(unsigned b);
void filename(const char *file, const char *ext, int dropext);
void show_comment(void);

// Implementation of functions
void init_decompress(void) {
    unsigned i, j;

    for(i = j = 0; i < N_CHAR; ++i) {
        freq[i] = 1;
        son[i] = i + TSIZE;
        parent[i+TSIZE] = i;
    }

    while(i <= ROOT) {
        freq[i] = freq[j] + freq[j+1];
        son[i] = j;
        parent[j] = parent[j+1] = i++;
        j += 2;
    }

    memset(ring_buff, ' ', sizeof(ring_buff));
    Advcomp = freq[TSIZE] = 0xFFFF;
    parent[ROOT] = Bitbuff = Bits = 0;
    GBr = SBSIZE - LASIZE;
}

void update(int c) {
    unsigned i, j, k, f, l;

    if(freq[ROOT] == MAX_FREQ) {
        for(i = j = 0; i < TSIZE; ++i) {
            if(son[i] >= TSIZE) {
                freq[j] = (freq[i] + 1) / 2;
                son[j] = son[i];
                ++j;
            }
        }

        for(i = 0, j = N_CHAR; j < TSIZE; i += 2, ++j) {
            k = i + 1;
            f = freq[j] = freq[i] + freq[k];
            for(k = j - 1; f < freq[k]; --k);
            ++k;
            l = (j - k) * sizeof(freq[0]);

            memmove(&freq[k+1], &freq[k], l);
            freq[k] = f;
            memmove(&son[k+1], &son[k], l);
            son[k] = i;
        }

        for(i = 0; i < TSIZE; ++i)
            if((k = son[i]) >= TSIZE)
                parent[k] = i;
            else
                parent[k] = parent[k+1] = i;
    }

    c = parent[c+TSIZE];
    do {
        k = ++freq[c];
        if(k > freq[l = c+1]) {
            while(k > freq[++l]);
            freq[c] = freq[--l];
            freq[l] = k;
            parent[i = son[c]] = l;
            if(i < TSIZE)
                parent[i+1] = l;
            parent[j = son[l]] = c;
            son[l] = i;
            if(j < TSIZE)
                parent[j+1] = c;
            son[c] = j;
            c = l;
        }
    } while(c = parent[c]);
}

unsigned GetChar(void) {
    int c = fgetc(fpi);
    if(c == EOF) {
        c = 0;
        Eof = 255;
    }
    return (unsigned)c;
}

unsigned GetBit(void) {
    unsigned t;
    if(!Bits--) {
        Bitbuff |= GetChar() << 8;
        Bits = 7;
    }
    t = Bitbuff >> 15;
    Bitbuff <<= 1;
    return t;
}

unsigned GetByte(void) {
    unsigned t;
    if(Bits < 8)
        Bitbuff |= GetChar() << (8-Bits);
    else
        Bits -= 8;
    t = Bitbuff >> 8;
    Bitbuff <<= 8;
    return t;
}

unsigned DecodeChar(void) {
    unsigned c = ROOT;
    while((c = son[c]) < TSIZE)
        c += GetBit();
    update(c -= TSIZE);
    return c;
}

unsigned DecodePosition(void) {
    unsigned i, j, c;
    i = GetByte();
    c = d_code[i] << 6;
    j = d_len[i >> 4];
    while(--j)
        i = (i << 1) | GetBit();
    return (i & 0x3F) | c;
}

void error(const char *format, ...) {
    va_list args;
    va_start(args, format);
    vfprintf(stderr, format, args);
    va_end(args);
    fprintf(stderr, "\n");
    if(fpo) fclose(fpo);
    if(fpi) fclose(fpi);
    exit(1);
}

int getbyte(void) {
    unsigned c;

    --GBcheck;
    if(!Advcomp)    // No compression
        return getc(fpi);

    for(;;) {       // Decompressor state machine
        if(Eof)     // End of file has been flagged
            return -1;
        if(!GBstate) {       // Not in the middle of a string
            c = DecodeChar();
            if(c < 256) {    // Direct data extraction
                ring_buff[GBr++] = c;
                GBr &= (SBSIZE-1);
                return c;
            }
            GBstate = 255;   // Begin extracting a compressed string
            GBi = (GBr - DecodePosition() - 1) & (SBSIZE-1);
            GBj = c - 255 + THRESHOLD;
            GBk = 0;
        }
        if(GBk < GBj) {     // Extract a compressed string
            ring_buff[GBr++] = c = ring_buff[(GBk++ + GBi) & (SBSIZE-1)];
            GBr &= (SBSIZE-1);
            return c;
        }
        GBstate = 0;        // Reset to non-string state
    }
}

unsigned getword(void) {
    unsigned w;
    w = getbyte();
    return (getbyte() << 8) | w;
}

int getblock(unsigned char *p, unsigned size, const char *e) {
    int c;
    int eof = 0;
    while(size) {
        --size;
        if((c = getbyte()) == -1) {
            eof = 1;
            if(e)
                error("EOF reading %s", e);
            break;
        }
        *p++ = c;
    }
    return eof;
}

void warn(const char *format, ...) {
    va_list args;
    va_start(args, format);
    vfprintf(stderr, format, args);
    va_end(args);
    fprintf(stderr, "\n");
}

// Main program implementation
int main(int argc, char *argv[]) {
    if (argc < 2) {
        printf("Usage: %s inputfile.td0 [options]\n", argv[0]);
        return 1;
    }

    // Initialize variables
    const char *infile = argv[1];
    char outfile[256];
    strncpy(outfile, infile, sizeof(outfile)-5);
    char *ext = strrchr(outfile, '.');
    if (ext) *ext = '\0';
    strncat(outfile, ".IMD", sizeof(outfile)-strlen(outfile)-1);

    // Open input file
    if (!(fpi = fopen(infile, "rb"))) {
        error("Cannot open input file: %s", infile);
    }

    // Read TD0 header
    if (fread(&Header, sizeof(Header), 1, fpi) != 1) {
        error("Error reading TD0 header");
    }

    // Validate header
    printf("Debug: Header signature = 0x%04X\n", Header.Sig);
    if (Header.Sig != 0x4454 && Header.Sig != 0x4464) { // 'TD' or 'td' (little-endian)
        error("Invalid TD0 header signature");
    }

    // Initialize decompression if needed
    if (Header.Sig == 0x4464) { // 'td' = compressed (little-endian)
        init_decompress();
    }

    // Open output file
    if (!(fpo = fopen(outfile, "wb"))) {
        error("Cannot create output file: %s", outfile);
    }

    // Write IMD header
    fprintf(fpo, "IMD 1.20 %s\r\n", VERSION);

    // Process each track
    while (!feof(fpi)) {
        unsigned char track_data[256];
        if (fread(&Thead, sizeof(Thead), 1, fpi) != 1) {
            if (feof(fpi)) break;
            error("Error reading track header");
        }

        // Check for end of disk marker
        if (Thead.Tsectors == 0xFF) break;

        // Process sectors in track
        for (int i = 0; i < Thead.Tsectors; i++) {
            if (fread(&Shead, sizeof(Shead), 1, fpi) != 1) {
                error("Error reading sector header");
            }

            // Process sector data
            if (Shead.Ssize > 6) { // Validar tamaño del sector
                error("Invalid sector size: %u", Shead.Ssize);
            }
            unsigned sector_size = 128 << Shead.Ssize;
            
            printf("Track %u, Head %u, Sectors %u\n", Thead.Tcylinder, Thead.Tside, Thead.Tsectors);
            printf("Processing Sector: Cyl=%u, Side=%u, Sector=%u, Size=%u(%u bytes), Flags=0x%02X\n",
                   Shead.Scylinder, Shead.Sside, Shead.Ssector, Shead.Ssize, sector_size, Shead.Sflags);

            if (!(Shead.Sflags & SEC_NODAT)) {
                // Leer encabezado de datos si hay datos
                if (fread(&Dhead, sizeof(Dhead), 1, fpi) != 1) {
                    error("Error reading data header");
                }

                printf("Data header: offset=%u, method=%u\n", Dhead.Doffset, Dhead.Dmethod);

                // Alocar buffer para datos del sector
                unsigned char *sector_data = malloc(sector_size);
                if (!sector_data) {
                    error("Memory allocation failed");
                }

                // Leer datos según el método de compresión
                switch (Dhead.Dmethod) {
                    case 0: // Raw sector data
                        if (fread(sector_data, sector_size, 1, fpi) != 1) {
                            free(sector_data);
                            error("Error reading raw sector data");
                        }
                        break;
                    case 1: // 2-byte RLE
                        {
                            unsigned short count;
                            unsigned char b1, b2;
                            if (fread(&count, 2, 1, fpi) != 1 ||
                                fread(&b1, 1, 1, fpi) != 1 ||
                                fread(&b2, 1, 1, fpi) != 1) {
                                free(sector_data);
                                error("Error reading RLE data");
                            }
                            for (unsigned i = 0; i < count * 2 && i < sector_size; i += 2) {
                                sector_data[i] = b1;
                                sector_data[i+1] = b2;
                            }
                        }
                        break;
                    case 2: // RLE block
                        {
                            unsigned char *p = sector_data;
                            unsigned remain = sector_size;
                            while (remain > 0) {
                                unsigned char blocktype;
                                if (fread(&blocktype, 1, 1, fpi) != 1) {
                                    free(sector_data);
                                    error("Error reading RLE block type");
                                }
                                if (blocktype == 0) { // Literal data
                                    unsigned char count;
                                    if (fread(&count, 1, 1, fpi) != 1) {
                                        free(sector_data);
                                        error("Error reading RLE block count");
                                    }
                                    if (count > remain) count = remain;
                                    if (fread(p, count, 1, fpi) != 1) {
                                        free(sector_data);
                                        error("Error reading RLE block data");
                                    }
                                    p += count;
                                    remain -= count;
                                } else { // Repeated fragment
                                    unsigned frag_size = 1 << blocktype;
                                    unsigned char count;
                                    unsigned char fragment[256];
                                    if (fread(&count, 1, 1, fpi) != 1 ||
                                        fread(fragment, frag_size, 1, fpi) != 1) {
                                        free(sector_data);
                                        error("Error reading RLE fragment");
                                    }
                                    for (unsigned i = 0; i < count && remain >= frag_size; i++) {
                                        memcpy(p, fragment, frag_size);
                                        p += frag_size;
                                        remain -= frag_size;
                                    }
                                }
                            }
                        }
                        break;
                    default:
                        free(sector_data);
                        error("Unknown compression method: %u", Dhead.Dmethod);
                }

                // Escribir datos al archivo IMD
                fwrite(sector_data, sector_size, 1, fpo);
                free(sector_data);
            }
        }
    }

    // Close files
    fclose(fpi);
    fclose(fpo);

    printf("Conversion completed successfully\n");
    return 0;
}
