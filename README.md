# png-parser
Reads png file, decompresses image data with zlib, decodes image data, then displays decoded image in a matplotlib plot. 

Supports all valid color types and bit depths, but support for interlacing and ancillary chunks is not implemented yet. 

My goal for this project is to understand the png format before moving on to writing a programme to decode jpeg, which has a much less trivial compression algorithm.

Complete details about the png format can be found here: http://www.libpng.org/pub/png/spec/1.2/PNG-Contents.html

The programme has been tested and gives correct output with this suite of test png files: http://www.schaik.com/pngsuite/pngsuite_bas_png.html

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
Navigate to the png-parser directory and run
```bash
python3 ./png_parser.py --png-file [PNG_FILE ...]
```
where each argument PNG_FILE to --png-file is the path to a png file.

If you have given a valid path to a png file, the programme will open the file. Information about any ancillary chunks in the file, as well as the size of the image data before and after zlib decompression in bytes, will be printed to the screen. Once the image data has been decoded, the image will appear in a matplotlib plot window. If you have given more than one file to read, the next file will be read and plotted after you close the plot window of the current image.
