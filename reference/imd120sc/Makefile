# Compiler settings
CC      = gcc
CFLAGS  = -Wall -Wextra -O2 -std=c99
PREFIX  = /usr/local

# Files
TARGET  = td02imd_modern
SOURCES = td02imd_modern.c
OBJECTS = $(SOURCES:.c=.o)

# Default target
all: $(TARGET)

# Linking the program
$(TARGET): $(OBJECTS)
	$(CC) $(OBJECTS) -o $(TARGET)

# Compiling source files
%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

# Clean build files
clean:
	rm -f $(TARGET) $(OBJECTS)

# Install
install: $(TARGET)
	install -d $(PREFIX)/bin
	install -m 755 $(TARGET) $(PREFIX)/bin

# Uninstall
uninstall:
	rm -f $(PREFIX)/bin/$(TARGET)

.PHONY: all clean install uninstall
