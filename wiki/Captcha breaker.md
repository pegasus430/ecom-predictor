This page contains info on how to use the captcha breaker utilities for breaking Amazon captchas if getting blocked.

The captcha breaker is implemented in the `search/captcha_solver.py` file. The class to use for breaking captchas is `CaptchaBreakerWrapper`.

**Usage example**:

    import captcha_solver

    CB = captcha_solver.CaptchaBreakerWrapper()
    captcha_text = CB.solve_captcha("http://ecx.images-amazon.com/captcha/bfhuzdtn/Captcha_distpnvhaw.jpg")

**Necessary files**:

To be able to solve captchas, the class must have access to 2 data files named:

- `train_captchas_data_images.npy`
- `train_captchas_data_labels.npy`

They are found in `search/train_captchas_data`.

The `TRAIN_DATA_PATH` field in the `CaptchaBreakerWrapper` class contains the path to the directory containing these 2 files. Change this field's value in your instance of the class to point to a directory containing these 2 files.

The captcha breaker will also create 2 directories containing the captcha files in the directory from which it's run. To change the paths for these directories, change the value of the `CAPTCHAS_DIR` and `SOLVED_CAPTCHAS_DIR` fields in the `CaptchaBreakerWrapper` class.

**Dependencies**:

- numpy
- opencv
- urllib

# How to build and install OpenCV2 in python virtual environment

This is tutorial how to build and install OpenCV2 for Amazon Captcha Solver in Python virtual environment.

**Works properly with**:

* Ubuntu 16.04 based distro
* Python 2.7
* virtualenvwrapper

## Pre-build steps
Refresh and upgrade installed libraries
```
$ sudo apt-get update
$ sudo apt-get upgrade
```

Install all requirements for build
```
$ sudo apt-get install build-essential cmake pkg-config libjpeg8-dev libtiff5-dev libjasper-dev libpng12-dev libavcodec-dev libavformat-dev libswscale-dev libv4l-dev libxvidcore-dev libx264-dev libgtk-3-dev libatlas-base-dev gfortran python2.7-dev python3.5-dev
```

Install virtualenv, virtualenvwrapper and create new virtualenv
```
$ sudo pip install virtualenv virtualenvwrapper
$ echo "export WORKON_HOME=$HOME/.virtualenvs" >> ~/.bashrc
$ echo "source /usr/local/bin/virtualenvwrapper.sh" >> ~/.bashrc
$ source ~/.bashrc
$ mkvirtualenv cv -p python2
```
or use existing one
```
$ workon cv
```

Install numpy from pip
```
$ pip install numpy
```

Download [opencv-2.4.13.zip](https://bitbucket.org/dfeinleib/tmtext/downloads/opencv-2.4.13.zip) from attachment and unzip it
```
wget -O opencv-2.4.13.zip https://bitbucket.org/dfeinleib/tmtext/downloads/opencv-2.4.13.zip
unzip opencv-2.4.13.zip
```

## Build
Ensure you use your target virtualenv before build.
Your command promt must looks like below. In braces is name of the virtualenv.
```
(cv2) druzhko@hipe-laptop:~$ 
```

Setup and configure build
```
$ cd opencv-2.4.13
$ mkdir build
$ cd build
$ cmake -D CMAKE_INSTALL_PREFIX=$VIRTUAL_ENV/local/ -D PYTHON_EXECUTABLE=$VIRTUAL_ENV/bin/python -D PYTHON_LIBRARY=/usr/lib/x86_64-linux-gnu/libpython2.7.so -D PYTHON_PACKAGES_PATH=$VIRTUAL_ENV/lib/python2.7/site-packages -D BUILD_EXAMPLES=ON -D INSTALL_PYTHON_EXAMPLES=ON -D INSTALL_C_EXAMPLES=ON -D WITH_V4L=ON -D CUDA_GENERATION=Auto -D WITH_CUBLAS=1 -D ENABLE_FAST_MATH=1 -D CUDA_FAST_MATH=1 -D WITH_OPENGL=ON -D WITH_TBB=ON ..
```

Now build. Parameter ```-j``` controls number of processes used when building. Set as number of CPU cores.
```
make -j2
```

Install
```
$ sudo make install
$ sudo ldconfig
```

## Testing
```
$ workon cv
$ python
Python 2.7.12 (default, Nov 19 2016, 06:48:10) 
[GCC 5.4.0 20160609] on linux2
Type "help", "copyright", "credits" or "license" for more information.
>>> import cv2
>>> cv2.__version__
'2.4.13'
```