""" This module contains functions to parse, decode, and display png files."""
# Copyright (C) 2024  CoolGuy75562
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.

import argparse
import zlib
import sys
from typing import BinaryIO
import matplotlib.pyplot as plt
import numpy as np
import database  # database.py

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

COLOR_TYPE_STR = {0: "(grayscale)",
                  2: "(rgb)",
                  3: "(indexed color)",
                  4: "(grayscale alpha)",
                  6: "(rgb alpha)"
                  }
COMPRESSION_METHOD_STR = {0: "(DEFLATE)"}
INTERLACE_METHOD_STR = {0: "(no interlace)",
                        1: "(Adam7 interlace)"
                        }


# these are used in decoding scanlines of uncompressed IDAT data
def none_filter(x: int, a: int, b: int, c: int) -> int:
    return x


def prior_filter(x: int, a: int, b: int, c: int) -> int:
    return (x + a) % 256


def up_filter(x: int, a: int, b: int, c: int) -> int:
    return (x + b) % 256


def average_filter(x: int, a: int, b: int, c: int) -> int:
    return (x + (a + b)//2) % 256


def paeth_filter(x: int, a: int, b: int, c: int) -> int:
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


def ceil_div(a: int, b: int) -> int:
    return -(a // -b)


def read_chunk(png_file: BinaryIO) -> dict:
    """ Read next chunk from file object pointing to the start of a chunk. """
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

    return {"chunk_length": chunk_length,
            "chunk_type": chunk_type,
            "is_ancillary": is_ancillary,
            "is_private": is_private,
            "is_reserved": is_reserved,
            "is_safe_to_copy": is_safe_to_copy,
            "chunk_data": chunk_data,
            "chunk_crc": chunk_crc
            }


def parse_IHDR_data(IHDR_data: bytes) -> dict:
    """ Parse information from the data field of an IHDR chunk. """
    width = int.from_bytes(IHDR_data[0:4])
    height = int.from_bytes(IHDR_data[4:8])
    bit_depth = int.from_bytes(IHDR_data[8:9])
    color_type = int.from_bytes(IHDR_data[9:10])
    compression_method = int.from_bytes(IHDR_data[10:11])
    filter_method = int.from_bytes(IHDR_data[11:12])
    interlace_method = int.from_bytes(IHDR_data[12:13])
    assert filter_method == FILTER_METHOD, "filter method must be 0"
    assert compression_method == COMPRESSION_METHOD, \
        "compression method must be 0"
    assert interlace_method in INTERLACE_METHODS, \
        "interlace method must be 0 or 1"
    assert color_type in COLOR_TYPES, \
        f"color type must be one of {COLOR_TYPES}"
    assert bit_depth in BIT_DEPTHS[color_type], \
        "wrong bit depth for color type"
    return {"width": width,
            "height": height,
            "bit_depth": bit_depth,
            "color_type": color_type,
            "compression_method": compression_method,
            "filter_method": filter_method,
            "interlace_method": interlace_method
            }


def get_palette(PLTE_chunk: dict) -> list[list]:
    """ Get the pallete data from a PLTE chunk. """
    PLTE_data = PLTE_chunk["chunk_data"]
    PLTE_data_length = PLTE_chunk["chunk_length"]
    palette = []
    assert PLTE_data_length % 3 == 0, "PLTE data length must be divisible by 3"
    n_entries = PLTE_data_length//3
    for i in range(n_entries):
        red = int.from_bytes(PLTE_data[3*i:3*i+1])
        green = int.from_bytes(PLTE_data[3*i+1:3*i+2])
        blue = int.from_bytes(PLTE_data[3*i+2:3*i+3])
        palette.append([red, green, blue])
    return palette


def read_png_file(filename: str) -> tuple[dict,
                                          dict | None,
                                          bytes,
                                          list[dict],
                                          list[dict]
                                          ]:
    """ Opens file filename, checks that it is a valid png file, then returns
        information needed to decode the image, and lists of the chunks read.

    Args:
        filename: The name of the png file to be read.

    Returns:
        IHDR_info: A dictionary containing the information from the IHDR chunk.
        PLTE_chunk: The PLTE chunk if exists, else None
        IDAT_data: The concatenation of the data fields of the IDAT chunks
            in order they are read.
        ancillary_chunks: A list containing the ancillary chunks
        chunks: A list containing every chunk.
    """
    with open(filename, 'rb') as png_file:  # rb: read bytes
        png_signature = png_file.read(8)
        assert png_signature == PNG_SIGNATURE, \
            "first 8 bytes must be the png signature"

        chunks = []
        IHDR_chunk = read_chunk(png_file)
        assert IHDR_chunk["chunk_type"] == 'IHDR', \
            "IHDR chunk must appear first"
        chunks.append(IHDR_chunk)
        ancillary_chunks = []
        IDAT_chunks = []
        PLTE_chunk = None
        while True:
            curr_chunk = read_chunk(png_file)
            if curr_chunk["chunk_type"] == "IEND":
                chunks.append(curr_chunk)
                break
            elif curr_chunk["chunk_type"] == "IDAT":
                IDAT_chunks.append(curr_chunk)
                chunks.append(curr_chunk)
            elif curr_chunk["chunk_type"] == "PLTE":
                PLTE_chunk = curr_chunk
                chunks.append(curr_chunk)
            else:
                ancillary_chunks.append(curr_chunk)
                chunks.append(curr_chunk)
        png_file.close()

        IHDR_info = parse_IHDR_data(IHDR_chunk["chunk_data"])
        IDAT_data = b''.join([chunk["chunk_data"] for chunk in IDAT_chunks])
        return IHDR_info, PLTE_chunk, IDAT_data, ancillary_chunks, chunks


def extract_IDAT_data(IDAT_chunks: list[dict]) -> bytes:
    return b"".join([chunk["chunk_data"] for chunk in IDAT_chunks])


def decode_image_data(IHDR_info: dict,
                      decomped_IDAT_data: bytes,
                      PLTE_chunk: dict
                      ) -> list[list]:
    """ Decodes decompressed IDAT data according to color_type, bit_depth etc.,
    and returns the resulting image.
    """
    width = IHDR_info["width"]
    height = IHDR_info["height"]
    bit_depth = IHDR_info["bit_depth"]
    color_type = IHDR_info["color_type"]

    if PLTE_chunk:
        assert color_type in [2, 3, 6]
        palette = get_palette(PLTE_chunk)

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
    # matplotlib.imshow() doesn't do integer samples larger than 255
    # so for higher bit depth we have to convert to float in range [0, 1]
    def gs(image_row: bytes) -> list[int]:
        gs_image_row = []
        for i in range((scanline_length-1)//2):
            two_bytes = int.from_bytes(image_row[2*i:2*(i+1)])
            for j in range(1, 16//bit_depth + 1):
                bits_to_shift = 16 - j*bit_depth
                pixel = (two_bytes >> bits_to_shift) & (2**(bit_depth)-1)
                gs_image_row.append(pixel)
        # if scanline length odd:
        for i in range((scanline_length-1) % 2):
            last_byte = int.from_bytes(
                image_row[scanline_length-2:scanline_length-1]
            )
            for j in range(1, 8//bit_depth + 1):
                bits_to_shift = 8-j*bit_depth
                pixel = (last_byte >> bits_to_shift) & (2**(bit_depth)-1)
                gs_image_row.append(pixel)
        return gs_image_row

    def rgb(image_row: bytes) -> list[list[int]]:
        rgb_image_row = []
        for i in range((scanline_length-1)//bpp):
            pixel_bytes = image_row[bpp*i:bpp*(i+1)]
            red = int.from_bytes(pixel_bytes[0:bytes_per_sample])
            green = int.from_bytes(
                pixel_bytes[bytes_per_sample:2*bytes_per_sample]
            )
            blue = int.from_bytes(
                pixel_bytes[2*bytes_per_sample:3*bytes_per_sample]
            )
            rgb_image_row.append([red, green, blue])
        return rgb_image_row

    def ci(image_row: bytes) -> list[list[int]]:
        ci_image_row = []
        for i in range(scanline_length-1):
            ci_byte = int.from_bytes(image_row[i:i+1])
            for j in range(1, 8//bit_depth + 1):
                bits_to_shift = 8-j*bit_depth
                idx = (ci_byte >> bits_to_shift) & (2**(bit_depth)-1)
                ci_image_row.append(palette[idx])
        return ci_image_row

    def gsa(image_row: bytes) -> list[list[int]]:
        gsa_image_row = []
        for i in range((scanline_length-1)//bpp):
            pixel_bytes = image_row[bpp*i:bpp*(i+1)]
            gs_sample = int.from_bytes(pixel_bytes[0:bytes_per_sample])
            alpha = int.from_bytes(
                pixel_bytes[bytes_per_sample:2*bytes_per_sample]
            )
            gsa_image_row.append([gs_sample, alpha])
        return gsa_image_row

    def rgba(image_row: bytes) -> list[list[int]]:
        rgba_image_row = []
        for i in range((scanline_length-1)//bpp):
            pixel_bytes = image_row[bpp*i:bpp*(i+1)]
            red = int.from_bytes(pixel_bytes[0:bytes_per_sample])
            green = int.from_bytes(
                pixel_bytes[bytes_per_sample:2*bytes_per_sample]
            )
            blue = int.from_bytes(
                pixel_bytes[2*bytes_per_sample:3*bytes_per_sample]
            )
            alpha = int.from_bytes(
                pixel_bytes[3*bytes_per_sample:4*bytes_per_sample]
            )
            rgba_image_row.append([red, green, blue, alpha])
        return rgba_image_row

    row_to_pixels = {0: gs, 2: rgb, 3: ci, 4: gsa, 6: rgba}
    row_to_pixels = row_to_pixels[color_type]

    scanline_length = {0: (bit_depth*width)//8 + 1,
                       2: (bit_depth*width*3)//8 + 1,
                       3: (bit_depth*width)//8 + 1,
                       4: (bit_depth*width*2)//8 + 1,
                       6: (bit_depth*width*4)//8 + 1
                       }

    # length of scanline including filter byte
    scanline_length = scanline_length[color_type]

    image = []
    b_row = [0]*(scanline_length-1)  # row above first row is zero
    for i in range(height):
        scanline = decomped_IDAT_data[i*scanline_length:(i+1)*scanline_length]
        filter_type = int.from_bytes(scanline[0:1])
        image_row = []
        a = 0  # left of first entry is zero
        for j in range(0, scanline_length-1):
            b = b_row[j]
            c = b_row[j-bpp] if j-bpp >= 0 else 0
            x = int.from_bytes(scanline[j+1:j+2])  # +1 because filter byte
            x = undo_filter[filter_type](x, a, b, c)
            image_row.append(x)
            a = image_row[j-bpp+1] if j-bpp+1 >= 0 else 0
        b_row = image_row
        image.append(row_to_pixels(image_row))
    return image


def show_image(image: list[list[float]] | list[list[list[float]]],
               color_type: int,
               bit_depth: int
               ) -> None:
    """ Displays image in matplotlib plot. """
    image = np.array(image)
    if color_type in [2, 4, 6]:
        image = np.divide(image, 2**bit_depth)
    fig = plt.figure()
    ax = fig.add_subplot(111)

    if color_type == 0:  # grayscale
        ax.imshow(image,
                  aspect='equal',
                  interpolation='none',
                  cmap='gray',
                  vmin=0, vmax=2**bit_depth)
    # we have to turn grayscale with alpha into rgb to get imshow() to work
    elif color_type == 4:
        gs = image[:, :, 0]
        alpha = image[:, :, 1]
        image = np.dstack((gs, gs, gs, alpha))
        ax.imshow(image,
                  aspect='equal',
                  interpolation='none',
                  cmap='gray',
                  vmin=0, vmax=2**bit_depth)
    else:
        ax.imshow(image,
                  aspect='equal',
                  interpolation='none',
                  vmin=0, vmax=2**bit_depth)
    plt.show()


def print_symbol_console(r, g, b, symbol):
    print(f"\033[38;2;{r};{g};{b}m{symbol}\033[0m", end="")


def show_image_console_rgb(image, width, color_type, bit_depth):

    if color_type == 0:
        if bit_depth < 8:
            image = np.multiply(image, 2**(8-bit_depth))
        image = np.dstack((image, image, image))

    for row in image[:]:
        for pixel in row:
            r, g, b = pixel
            print_symbol_console(r, g, b, '\u2588')
        print()


def show_image_console_rgba(image, width, color_type, bit_depth):

    if color_type == 4:
        image = np.array(image)
        gs = image[:, :, 0]
        alpha = image[:, :, 1]
        image = np.dstack((gs, gs, gs, alpha))

    alpha_map = {0: '\u2800',
                 1: '\u2591',
                 2: '\u2592',
                 3: '\u2593',
                 4: '\u2588'
                 }

    for row in image[:]:
        for pixel in row:
            r, g, b, a = pixel
            a = (10*a)//512
            print_symbol_console(r, g, b, alpha_map[a])
        print()


def print_info(file_name: str, IHDR_info: dict) -> None:
    print(f"IHDR information for {file_name}:\n")
    print(f"width: {IHDR_info['width']}")
    print(f"height: {IHDR_info['height']}")
    print(f"bit depth: {IHDR_info['bit_depth']}")
    print((
        f"color type: {IHDR_info['color_type']} "
        f"{COLOR_TYPE_STR[IHDR_info['color_type']]}"
    ))
    print((
        f"compression method: {IHDR_info['compression_method']} "
        f"{COMPRESSION_METHOD_STR[IHDR_info['compression_method']]}"
    ))
    print(f"filter method: {IHDR_info['filter_method']}")
    print((
        f"interlace method: {IHDR_info['interlace_method']} "
        f"{INTERLACE_METHOD_STR[IHDR_info['interlace_method']]}\n"
    ))


def print_chunks(file_name: str, chunks: list[dict]) -> None:
    print(f"Chunks contained in {file_name}:\n")
    for i, chunk in enumerate(chunks):
        chunk_str = "{num: >{width}}: {chunk_type}".format(
            num=i,
            width=5,
            chunk_type=chunk
        )
        print(chunk_str, end="")
        if (i+1) % 7 == 0:
            print()
    print("\n")


def start_database() -> database.Database | type(None):
    db = database.Database()
    if not db.connect():
        return None
    else:
        return db


# Command line options:
def store(args: argparse.Namespace) -> None:
    """ Store information about each png file in list in a database. """
    db = start_database()
    if not db:
        sys.exit(1)

    for png_file in args.png_files:
        IHDR_info, _, _, _, all_chunks = read_png_file(png_file.name)
        print(f"Inserting {png_file.name} data into db.db...")
        png_info_insert_success = db.insert_png_info(png_file.name,
                                                     IHDR_info)
        if png_info_insert_success:
            for chunk in all_chunks:
                chunk_insert_success = db.insert_chunk(chunk)
                if not chunk_insert_success:
                    break
            if chunk_insert_success:
                print("Saving changes...")
                db.save_changes()
                print("Done!\n")
        if not (png_info_insert_success and chunk_insert_success):
            print("Changes not saved.\n")
    db.close()

def info(args: argparse.Namespace) -> None:
    """ Display information about png files
        and chunks if option specified."""

    if args.database:
        db = start_database()
        if not db:
            sys.exit(1)
        png_files, IHDR_infos, all_chunkss = db.get_first_n_infos(args.database)
        db.close()
        if not any((png_files, IHDR_infos, all_chunkss)):
            print("Perhaps the database is empty")
            sys.exit(1)
    else:
        IHDR_infos, all_chunkss = [], []
        png_files = [png_file.name for png_file in args.png_files]
        for png_file in png_files:
            IHDR_info, _, _, _, all_chunks = read_png_file(png_file)
            all_chunks = [chunk["chunk_type"] for chunk in all_chunks]
            IHDR_infos.append(IHDR_info)
            all_chunkss.append(all_chunks)
            
    if args.chunks:
        for png_file, IHDR_info, all_chunks in zip(
                png_files,
                IHDR_infos,
                all_chunkss
        ):
            print(80*"=")
            print_info(png_file, IHDR_info)
            print(80*"-")
            print_chunks(png_file, all_chunks)
    else:
        for png_file, IHDR_info in zip(png_files, IHDR_infos):
            print(80*"=")
            print_info(png_file, IHDR_info)


def view(args: argparse.Namespace) -> None:
    """ View image with user specified path if given,
        else a random image from db.db.
    """
    if args.png_file == 'random':
        db = start_database()
        if not db:
            sys.exit(1)
        print("Opening random image from db.db...")
        if args.console:
            IHDR_info, PLTE_chunk, IDAT_data = db.get_random_png_file(
                width_lim=80
            )
        else:
            IHDR_info, PLTE_chunk, IDAT_data = db.get_random_png_file()
        db.close()
        if not any((IHDR_info, PLTE_chunk, IDAT_data)):
            print("Could not find valid non-interlaced image in db.db")
            sys.exit(1)
    else:
        IHDR_info, PLTE_chunk, IDAT_data, _, _ = read_png_file(args.png_file)
    if IHDR_info["interlace_method"]:
        print("viewing interlaced images is not currently supported")
        sys.exit(1)
    decomped_IDAT_data = zlib.decompress(IDAT_data)
    image = decode_image_data(IHDR_info, decomped_IDAT_data, PLTE_chunk)
    if args.console:
        if IHDR_info["width"] > 80:
            print("option --console not supported"
                  "for images wider than 80 pixels")
            sys.exit(1)
        if IHDR_info["bit_depth"] == 16:
            print("option --console not supported for 16 bit color")
            sys.exit(1)
        show_image_console = {
            0: show_image_console_rgb,
            2: show_image_console_rgb,
            3: show_image_console_rgb,
            4: show_image_console_rgba,
            6: show_image_console_rgba
        }
        show_image_console[IHDR_info["color_type"]](image,
                                                    IHDR_info["width"],
                                                    IHDR_info["color_type"],
                                                    IHDR_info["bit_depth"])
    else:
        show_image(image, IHDR_info["color_type"], IHDR_info["bit_depth"])


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    store_parser = subparsers.add_parser('store',
                                         help='store png files in database'
                                         )
    store_parser.set_defaults(func=store)
    store_parser.add_argument('png_files',
                              nargs='*',
                              type=argparse.FileType('rb'),
                              help='png files to be stored in database'
                              )

    info_parser = subparsers.add_parser('info',
                                        help=('view information '
                                              'about given png files')
                                        )
    info_parser.set_defaults(func=info)
    info_parser.add_argument('-c', '--chunks',
                             action='store_true',
                             help=('for each png file print a '
                                   'list of its chunks in order of occurrence')
                             )
    info_parser.add_argument('png_files',
                             nargs='*',
                             type=argparse.FileType('rb'),
                             help='list of png files',
                             default=None
                             )
    info_parser.add_argument('-d', '--database',
                             nargs='?',
                             const=10,
                             type=int,
                             help=('display info for top n images in database. '
                                   '(default 10) '
                                   )
                             )
    view_parser = subparsers.add_parser('view',
                                        help=('view a random image stored '
                                              'in the database, or a png file '
                                              'if specified. '
                                              'viewing interlaced '
                                              'images is not supported')
                                        )
    view_parser.set_defaults(func=view)
    view_parser.add_argument('png_file',
                             nargs='?',
                             help='png file to view',
                             default='random'
                             )
    view_parser.add_argument('-c', '--console',
                             action='store_true',
                             help=('print image to console. '
                                   'image width must be less than 80 pixels, '
                                   'and bit depth must not be 16. '
                                   'only 5 levels of transparency supported. '
                                   'will not work if terminal does not '
                                   'support truecolor')
                             )

    args = parser.parse_args()

    # sanity checks
    arguments_given = vars(args).keys()
    
    if 'database' in arguments_given and args.png_files:
        print("--database option requires no png_files")
        info_parser.print_usage()
        sys.exit(1)

    if 'database' in arguments_given and args.database < 1:
        print("--database option takes a positive nonzero integer. ")
        info_parser.print_usage()
        sys.exit(1)
        
    try:
        args.func(args)
    except AttributeError:
        parser.print_usage()
        sys.exit(1)


if __name__ == '__main__':
    main()
