Debian packages dependencies:

- python-opencv
- libpapack-dev (for scipy)
- libblas3gf libc6 libgcc1 libgfortran3 liblapack3gf  libstdc++6 build-essential gfortran python-all-dev libatlas-base-dev (for scipy)
- python-scipy (if installation with pip doesn't work)
- libfreetype6-dev libpng-dev (for matplotlib); also
    `ln -s /usr/include/freetype2/ft2build.h /usr/include/`
- tesseract-ocr

Python dependencies can be found in requirements.txt
