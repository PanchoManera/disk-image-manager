#!/bin/zsh

# Directory containing original TD0 files
ORIGINAL_DIR="/Users/pancho/git/HP1250/hp150_toolkit/HP150_ALL_ORIGINAL"
# Directory where organized files will be stored
TARGET_DIR="./HP150_ALL_ORIGINAL"

# Create main directory if it doesn't exist
mkdir -p "$TARGET_DIR"

# Loop through each TD0 file in the original directory
for TD0_FILE in "$ORIGINAL_DIR"/*.TD0; do
    # Extract the base name without extension
    BASE_NAME=$(basename "$TD0_FILE" .TD0)

    # Create a directory for this file
    mkdir -p "$TARGET_DIR/$BASE_NAME/td0"
    mkdir -p "$TARGET_DIR/$BASE_NAME/img"

    # Copy the TD0 file into its directory
    cp "$TD0_FILE" "$TARGET_DIR/$BASE_NAME/td0/"

    # Run the conversion script (assuming it's in the current directory)
    python ./td0_to_hp150.py "$TD0_FILE"

    # Move any resulting IMG files into the img directory
    mv *.img "$TARGET_DIR/$BASE_NAME/img/" 2>/dev/null

    # Create a geometry description file
    echo "Geometry info for $BASE_NAME" > "$TARGET_DIR/$BASE_NAME/geometry.txt"
    # Example geometry content; needs to be replaced with actual values
    echo "Tracks: 80" >> "$TARGET_DIR/$BASE_NAME/geometry.txt"
    echo "Sectors: 9" >> "$TARGET_DIR/$BASE_NAME/geometry.txt"
    echo "Bytes per sector: 512" >> "$TARGET_DIR/$BASE_NAME/geometry.txt"
done
