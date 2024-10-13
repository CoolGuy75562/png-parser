import sys
import argparse
import zlib
import matplotlib.pyplot as plt
import numpy as np

PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
FILTER_METHOD = 0
COMPRESSION_METHOD = 0
INTERLACE_METHODS = [0, 1]
COLOR_TYPES = [0, 2, 3, 4, 6]
BIT_DEPTHS = {0: [1, 2, 4, 8, 16],
              2: [8, 16],
              3: [1, 2, 4, 8],
              4: [8, 16],
              6: [8, 16]
              }

def read_chunk(png_file):
    chunk_length_bytes = png_file.read(4)
    chunk_length = int.from_bytes(chunk_length_bytes)
    
    chunk_type_bytes = png_file.read(4)
    chunk_type = chunk_type_bytes.decode('ascii')
    # the fifth bit of each byte in the chunk type is a flag
    is_ancillary = (int.from_bytes(chunk_type_bytes[0:1]) & 32) >> 5
    is_private = (int.from_bytes(chunk_type_bytes[1:2]) & 32) >> 5
    is_reserved = (int.from_bytes(chunk_type_bytes[2:3]) & 32) >> 5
    is_safe_to_copy = (int.from_bytes(chunk_type_bytes[3:4]) & 32) >> 5
    
    chunk_data = png_file.read(chunk_length)
    
    chunk_crc = int.from_bytes(png_file.read(4))
    actual_crc = zlib.crc32(chunk_type_bytes + chunk_data)
    assert actual_crc == chunk_crc, "failed chunk checksum"
    return {"chunk length" : chunk_length,
            "chunk type" : chunk_type,
            "is ancillary" : is_ancillary,
            "is private" : is_private,
            "is reserved" : is_reserved,
            "is safe to copy" : is_safe_to_copy,
            "chunk data" : chunk_data,
            "chunk crc" : chunk_crc
            }
    
def parse_IHDR_info(IHDR_data):
    width = int.from_bytes(IHDR_data[0:4])
    height = int.from_bytes(IHDR_data[4:8])
    bit_depth = int.from_bytes(IHDR_data[8:9])
    color_type = int.from_bytes(IHDR_data[9:10])
    compression_method = int.from_bytes(IHDR_data[10:11])
    filter_method = int.from_bytes(IHDR_data[11:12])
    interlace_method = int.from_bytes(IHDR_data[12:13])
    return (width,
            height,
            bit_depth,
            color_type,
            compression_method,
            filter_method,
            interlace_method
            )

def find_palette_chunk(png_file):
    """ Returns palette chunk if exists, as well
    as list of any ancillary chunks read.
    """
    ancillary_chunks = []
    while True:
        curr_chunk = read_chunk(png_file)
        if curr_chunk["is ancillary"] == 0:
            break
        print(f"Ancillary chunk: {curr_chunk}")
        ancillary_chunks.append(curr_chunk)
    assert curr_chunk["chunk type"] == "PLTE", "PLTE chunk must be the first critical chunk after IHDR for color type 3."
    return curr_chunk, ancillary_chunks
        
def get_palette(PLTE_chunk):
    PLTE_data = PLTE_chunk["chunk data"]
    PLTE_data_length = PLTE_chunk["chunk length"]
    palette = []
    assert PLTE_data_length % 3 == 0, "PLTE data length must be divisible by 3"
    n_entries = PLTE_data_length//3
    for i in range (n_entries):
        red = int.from_bytes(PLTE_data[3*i:3*i+1])
        green = int.from_bytes(PLTE_data[3*i+1:3*i+2])
        blue = int.from_bytes(PLTE_data[3*i+2:3*i+3])
        palette.append([red, green, blue])
    return palette
    
def read_png_file(filename):
    with open(filename, 'rb') as png_file: # rb: read bytes
        png_signature = png_file.read(8)
        assert png_signature == PNG_SIGNATURE, "first 8 bytes must be the png signature"

        IHDR_chunk = read_chunk(png_file)
        assert IHDR_chunk["chunk type"] == 'IHDR', "IHDR chunk must appear first"
        
        width, height, bit_depth, color_type, compression_method, filter_method, interlace_method = parse_IHDR_info(IHDR_chunk["chunk data"])
                
        assert filter_method == FILTER_METHOD, "filter method must be 0"
        assert compression_method == COMPRESSION_METHOD, "compression method must be 0"
        assert interlace_method in INTERLACE_METHODS, "interlace method must be 0 or 1"
        assert interlace_method == 0, "interlaced images not supported"
        
        assert color_type in COLOR_TYPES, f"color type must be one of {COLOR_TYPES}"
        assert bit_depth in BIT_DEPTHS[color_type], f"bit depth for color type {color_type} must be one of {BIT_DEPTHS[color_type]}"

        ancillary_chunks = []
        palette = None
        if color_type == 3: # indexed color
            PLTE_chunk, ancillary_chunks = find_palette_chunk(png_file)
            palette = get_palette(PLTE_chunk)
        IDAT_data = []
        while True:
            curr_chunk = read_chunk(png_file)
            if curr_chunk["chunk type"] == "IEND":
                break
            elif curr_chunk["chunk type"] == "IDAT":
                IDAT_data.append(curr_chunk["chunk data"])
            else:
                print(f"Ancillary chunk: {curr_chunk}")
                ancillary_chunks.append(curr_chunk)
        IDAT_data = b"".join(IDAT_data)
        png_file.close()

        return (width, height, bit_depth, color_type), IDAT_data, palette

    # -- Decompress IDAT data
def decompress_IDAT_data(IDAT_data, method='zlib'):
    print(f"compressed IDAT bytes: {str(len(IDAT_data))}")
    decomped_IDAT_data = zlib.decompress(IDAT_data)
    print(f"decompressed IDAT bytes: {str(len(decomped_IDAT_data))}\n")
    return decomped_IDAT_data

    # Now we define some functions for decoding the IDAT data, and converting rows of bytes to rows of pixels according to the color type and bit depth.
def decode_image_data(image_info, decomped_IDAT_data, palette=None):
    width, height, bit_depth, color_type = image_info
    # -- Filter functions --
    def none_filter(x, a, b, c):
        return x
        
    def prior_filter(x, a, b, c):
        return (x + a) % 256

    def up_filter(x, a, b, c):
        return (x + b) % 256

    def average_filter(x, a, b, c):
        return (x + (a + b)//2) % 256
        
    def paeth_filter(x, a, b, c):
        p = a + b - c
        pa = abs(p-a)
        pb = abs(p-b)
        pc = abs(p-c)
        if pa <= pb and pa <= pc:
            Pr = a
        elif pb <= pc:
            Pr = b
        else:
            Pr = c
        return (x + Pr) % 256

    undo_filter = (none_filter,
                   prior_filter,
                   up_filter,
                   average_filter,
                   paeth_filter
                   )

    
    def ceil_div(a, b):
        return -(a // -b)

    # bpp: bytes per pixel, rounded up
    bpp = {0: ceil_div(bit_depth, 8),
           2: 3*bit_depth//8,
           3: 1,
           4: 2*bit_depth//8,
           6: 4*bit_depth//8
           }
    bpp = bpp[color_type]

    bytes_per_sample = bit_depth//8
    
    # -- Color type functions --
    def gs(image_row):
        gs_image_row = []
        for i in range((scanline_length-1)//2):
            two_bytes = int.from_bytes(image_row[2*i:2*(i+1)])
            for j in range(1, 16//bit_depth + 1):
                bits_to_shift = 16 - j*bit_depth
                pixel = (two_bytes >> bits_to_shift) & (2**(bit_depth)-1)
                gs_image_row.append(pixel)
        # if scanline length odd:
        for i in range((scanline_length-1)%2):
            last_byte = int.from_bytes(image_row[scanline_length-2:scanline_length-1])
            for j in range(1, 8//bit_depth + 1):
                bits_to_shift = 8-j*bit_depth
                pixel = (last_byte >> bits_to_shift) & (2**(bit_depth)-1)
                gs_image_row.append(pixel)
        return gs_image_row

    def rgb(image_row):
        rgb_image_row = []
        for i in range((scanline_length-1)//bpp):
            pixel_bytes = image_row[bpp*i:bpp*(i+1)]
            red = int.from_bytes(pixel_bytes[0:bytes_per_sample])/(2**bit_depth)
            green = int.from_bytes(pixel_bytes[bytes_per_sample:2*bytes_per_sample])/(2**bit_depth)
            blue = int.from_bytes(pixel_bytes[2*bytes_per_sample:3*bytes_per_sample])/(2**bit_depth)
            rgb_image_row.append([red, green, blue])
        return rgb_image_row

    def ci(image_row):
        ci_image_row = []
        for i in range(scanline_length-1):
            ci_byte = int.from_bytes(image_row[i:i+1])
            for j in range(1, 8//bit_depth + 1):
                bits_to_shift = 8-j*bit_depth
                idx = (ci_byte >> bits_to_shift) & (2**(bit_depth)-1)
                ci_image_row.append(palette[idx])
        return ci_image_row

    def gsa(image_row):
        gsa_image_row = []
        for i in range((scanline_length-1)//bpp):
            pixel_bytes = image_row[bpp*i:bpp*(i+1)]
            gs_sample = int.from_bytes(pixel_bytes[0:bytes_per_sample])/(2**bit_depth)
            alpha = int.from_bytes(pixel_bytes[bytes_per_sample:2*bytes_per_sample])/(2**bit_depth)
            gsa_image_row.append([gs_sample, alpha])
        return gsa_image_row

    def rgba(image_row):
        rgba_image_row = []
        for i in range((scanline_length-1)//bpp):
            pixel_bytes = image_row[bpp*i:bpp*(i+1)]
            red = int.from_bytes(pixel_bytes[0:bytes_per_sample])/(2**bit_depth)
            green = int.from_bytes(pixel_bytes[bytes_per_sample:2*bytes_per_sample])/(2**bit_depth)
            blue = int.from_bytes(pixel_bytes[2*bytes_per_sample:3*bytes_per_sample])/(2**bit_depth)
            alpha = int.from_bytes(pixel_bytes[3*bytes_per_sample:4*bytes_per_sample])/(2**bit_depth)
            rgba_image_row.append([red, green, blue, alpha])
        return rgba_image_row
    
    row_to_pixels = {0 : gs,
                     2 : rgb,
                     3 : ci,
                     4 : gsa,
                     6 : rgba
                     }
    row_to_pixels = row_to_pixels[color_type]
    
    scanline_length = {0: (bit_depth*width)//8 + 1,
                       2: (bit_depth*width*3)//8 + 1,
                       3: (bit_depth*width)//8 + 1,
                       4: (bit_depth*width*2)//8 + 1,
                       6: (bit_depth*width*4)//8 + 1
                       }
    scanline_length = scanline_length[color_type] # length of scanline including filter byte

    # Now we are ready to undo the filter from each scanline and format the pixels according to the color type. 
    image = []
    b_row = [0]*(scanline_length-1) # row above first row is zero
    for i in range(height):
        scanline = decomped_IDAT_data[i*scanline_length:(i+1)*scanline_length]
        filter_type = int.from_bytes(scanline[0:1])
        image_row = []
        a = 0 # left of first entry is zero
        for j in range(0, scanline_length-1):
            b = b_row[j]
            c = b_row[j-bpp] if j-bpp >= 0 else 0
            x = int.from_bytes(scanline[j+1:j+2]) # because of filter byte this index is off by one
            x = undo_filter[filter_type](x, a, b, c)
            image_row.append(x)
            a = image_row[j-bpp+1] if j-bpp+1 >= 0 else 0
        b_row = image_row
        image.append(row_to_pixels(image_row))
    fig = plt.figure()
    ax = fig.add_subplot(111)
    
    if color_type == 0: # grayscale
        ax.imshow(image, aspect='equal', interpolation='none', cmap='gray', vmin=0, vmax = 2**bit_depth)
    elif color_type == 4: # grayscale with alpha, have to turn into rgba to get to work with matplotlib.imshow()
        image = np.array(image)
        gs = image[:,:,0]
        alpha = image[:,:,1]
        image = np.dstack((gs, gs, gs, alpha))
        ax.imshow(image, aspect='equal', interpolation='none', cmap='gray', vmin=0, vmax= 2**bit_depth)
    else:
        ax.imshow(image, aspect='equal', interpolation='none', vmin=0, vmax=2**bit_depth)
    plt.show()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--png-files', nargs='*', required=True, type=argparse.FileType('rb'))
    parser.add_argument('-d', '--decode', action='store_false')
    args = parser.parse_args()
    for png_file in args.png_files:
        print(f"\nReading {png_file.name}...\n")
        image_info, IDAT_data, palette = read_png_file(png_file.name)
        if args.decode:
            decode_image_data(image_info, decompress_IDAT_data(IDAT_data), palette=palette)
        else:
            print(IDAT_data)
            
if __name__ == '__main__':
    main()
