import struct

# Function to analyze the disk image structure
def analyze_disk_image(filename):
    with open(filename, 'rb') as f:
        data = f.read()

    sector_size = 512  # Assume 512 bytes per sector initially
    num_sectors = len(data) // sector_size
    remaining_bytes = len(data) % sector_size

    print(f"Total size: {len(data)} bytes")
    print(f"Sector size: {sector_size} bytes")
    print(f"Total sectors: {num_sectors}")
    if remaining_bytes != 0:
        print(f"Warning: {remaining_bytes} bytes not fitting into assumed sector size")

    # Iterate through sectors to see if we can detect varying sizes
    offset = 0
    for sector in range(num_sectors):
        current_slice = data[offset:offset + sector_size]

        # Attempt to read header or any identifiable structure
        # This is just an example assuming a known header structure
        if len(current_slice) >= 5:
            header = struct.unpack('<5s', current_slice[:5])
            print(f"Sector {sector}: {header}")
        else:
            print(f"Sector {sector}: Incomplete header")

        offset += sector_size

    # Check additional bytes in case of non-uniform sector size
    if remaining_bytes:
        print(f"Additional unaligned data: {data[offset:]}")

# Main
analyze_disk_image('word_respect_sizes_realfloppy_2.img')

