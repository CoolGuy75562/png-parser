# png-parser
Utility to parse, decode, and view png files. The information about a png file can be either printed to the screen, or put into a database. 

The decoder supports all valid color types and bit depths, but does not support interlacing and does not make use of ancillary chunks.
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
Navigate to the appropriate directory and run python3 with one of the following:
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

```bash
usage: png_parser.py store [-h] [png_files ...]

positional arguments:
  png_files   png files to be stored in database

options:
  -h, --help  show this help message and exit
```

```bash
usage: png_parser.py info [-h] [-c] [png_files ...]

positional arguments:
  png_files     list of png files

options:
  -h, --help    show this help message and exit
  -c, --chunks  for each png file print a list of its chunks in order of occurrence
```

```bash
usage: png_parser.py view [-h] [png_file]

positional arguments:
  png_file    png file to view

options:
  -h, --help  show this help message and exit
```

