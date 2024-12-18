# png-parser
Utility to parse, decode, and view png files. The information about a png file can be either printed to the screen, or put into an sqlite database. One can list information about the images stored in the database, and can restrict the list to images matching some criteria, for example images of color type 3 which are less than 100 pixels wide and contain a tEXt chunk.

Using a built-in png decoder, one can view images in a matplotlib plot window, or in the console if the image is less than 80 pixels wide. The decoder supports all valid color types and bit depths, but does not support interlacing and does not make use of ancillary chunks. I wrote it only to understand how png decoding works, so it is slow for larger images.

The decoder has been tested and gives correct output with this suite of test png files: http://www.schaik.com/pngsuite/pngsuite_bas_png.html

Complete details about the png format can be found here: http://www.libpng.org/pub/png/spec/1.2/PNG-Contents.html



## Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/CoolGuy75562/png-parser.git
   ```
2. Install dependencies:
   ```bash
   pip3 install numpy matplotlib
   ```

## Usage
There are three different "modes":
```bash
usage: png_parser.py [-h] {store,info,view} ...

positional arguments:
  {store,info,view}
    store            store png files in database
    info             view information about given png files
    view             view a random image stored in the database, or a png file if specified

options:
  -h, --help         show this help message and exit
```

The store option puts the information about a group of png files into a database. This information includes the absolute path to the file, information about the png file such as color type and bit depth, and information about each chunk in the png file, such as the chunk name and chunk length. Chunk data, including IDAT data, are also stored in another table.
```bash
usage: png_parser.py store [-h] [png_files ...]

positional arguments:
  png_files   png files to be stored in database

options:
  -h, --help  show this help message and exit
```

The info option prints information about a list of png files, such as color type and bit depth. If instead the --database option is specified, one can get the information about files which have been stored in the database using the store argument. For the database option, one has several conditions by which one can filter the images that are listed.
```bash
usage: png_parser.py info [-h] [-c] [-d [DATABASE]] [--color-type {0,2,3,4,6}] [--bit-depth {1,2,4,8,16}] [--interlace-method {0,1}] [--width WIDTH] [--height HEIGHT]
                          [--chunk-name CHUNK_NAME]
                          [png_files ...]

positional arguments:
  png_files             list of png files

options:
  -h, --help            show this help message and exit
  -c, --chunks          for each png file print a list of its chunks in order of occurrence
  -d [DATABASE], --database [DATABASE]
                        display info for first n images in database. (default 10)
  --color-type {0,2,3,4,6}
                        if --database given, restrict to images of specified color type
  --bit-depth {1,2,4,8,16}
                        if --database given, restrict to images of specified bit depth
  --interlace-method {0,1}
                        if --database given, restrict to images of specified interlace method
  --width WIDTH         if --database given, restrict to images less than specified width
  --height HEIGHT       if --database given, restrict to images less than specified height
  --chunk-name CHUNK_NAME
                        if --database given, restrict to images containing specified chunk
```

The view argument displays the specified png image in a matplotlib figure, or the console. If no file is specified, a random image from the database is selected and displayed instead. It can take a while to display the image if it is large.
```bash
usage: png_parser.py view [-h] [-c] [png_file]

positional arguments:
  png_file       png file to view

options:
  -h, --help     show this help message and exit
  -c, --console  print image to console. image width must be less than 80 pixels, and bit depth must not be 16. only 5 levels of transparency supported. will not work if terminal does not
                 support truecolor

```

## Example

Consider this parrot png:

![color_index_test](https://github.com/user-attachments/assets/27583125-16ba-4f29-bfa1-5b2d892e1e8c)

The info argument, along with the -c option, gives us the following output: 

```bash
python3 png_parser.py info -c color_index_test.png 
================================================================================
IHDR information for color_index_test.png:

width: 150
height: 200
bit depth: 8
color type: 3 (indexed color)
compression method: 0 (DEFLATE)
filter method: 0
interlace method: 0 (no interlace)

--------------------------------------------------------------------------------
Chunks contained in color_index_test.png:

    0: IHDR    1: PLTE    2: IDAT    3: IEND

```

We can view the image using the view argument:

```bash
python3 png_parser.py view color_index_test.png
```

![view_option](https://github.com/user-attachments/assets/5345f877-7865-4f72-9d35-42cc49b4ae84)

This screenshot is a png image, so we can look at its information too:

```bash
python3 png_parser.py info -c screenshot.png
================================================================================
IHDR information for screenshot.png:

width: 680
height: 595
bit depth: 8
color type: 6 (rgb alpha)
compression method: 0 (DEFLATE)
filter method: 0
interlace method: 0 (no interlace)

--------------------------------------------------------------------------------
Chunks contained in screenshot.png:

    0: IHDR    1: pHYs    2: IDAT    3: IDAT    4: IDAT    5: IDAT    6: IDAT
    7: IDAT    8: IDAT    9: IDAT   10: IDAT   11: IDAT   12: IEND

```

And we can view the image using the view argument:

```bash
python3 png_parser.py view screenshot.png
```

![screenshot_screenshot](https://github.com/user-attachments/assets/2e5a7a3a-4ace-44d6-9417-45ecee6e5a56)
