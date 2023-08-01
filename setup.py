#!/usr/bin/env python

# usage:
# python setup.py sdist
# twine upload dist/*

import pathlib
from setuptools import setup, find_packages

HERE = pathlib.Path(__file__).parent

setup(

    ### Metadata

    name='zarrview',

    version='0.1.1',

    description='PySide or PyQt tree model/view for a Zarr hierarchy.',

    long_description=(HERE / "README.md").read_text(),
    long_description_content_type = "text/markdown",

    url='https://github.com/marcel-goldschen-ohm/zarr-view',

    download_url='',

    license='MIT',

    author='Marcel Goldschen-Ohm',
    author_email='goldschen-ohm@utexas.edu',

    maintainer='Marcel Goldschen-Ohm',
    maintainer_email='goldschen-ohm@utexas.edu',

    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Topic :: Scientific/Engineering'
    ],

    ### Dependencies

    install_requires=[
        'zarr',
        'qtawesome'
    ],
    extras_require={
        'PySide6': ['PySide6>=6.5.2'],
        'PyQt6': ['PyQt6>=6.5.2'],
        'PyQt5': ['PyQt5']
    },

    ### Contents

    packages=find_packages()
    )
