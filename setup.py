# -*- coding: utf-8 -*-
# Copyright (c) 2014, Luke Campagnola.
# Distributed under the MIT License. See LICENSE.txt for more info.
import distutils.core
import os, sys

# Make sure this version is the firts to import
sys.path.insert(0, os.path.dirname(__file__))
import pycca


description = """\
PyCCA provides compilers for C and x86 assembly that allow optimized routines
to be compiled and executed at runtime with no external dependencies.
PyCCA supports 32- and 64-bit intel/amd architectures on Linux, OSX, and 
Windows with python 2.7 or 3.4. Current status: assembly compiler is beta, C
compiler is alpha.
"""


def package_tree(pkgroot):
    path = os.path.dirname(__file__)
    subdirs = [os.path.relpath(i[0], path).replace(os.path.sep, '.')
               for i in os.walk(os.path.join(path, pkgroot))
               if '__init__.py' in i[2]]
    return subdirs

distutils.core.setup(
    name='pycca',
    version=pycca.__version__,
    author='Luke Campagnola',
    author_email='luke.campagnola@gmail.com',
    license='MIT',
    url='http://github.com/lcampagn/pycca',
    download_url='https://pypi.python.org/pypi/pycca',
    keywords="assembly C compiler inline performance optimization",
    description="Pure-python C and assembly compilers",
    long_description=description,
    platforms='any',
    provides=['pycca'],
    install_requires=[],
    packages=package_tree('pycca'),
    package_dir={'pycca': 'pycca'},
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'Intended Audience :: Education',
        'Intended Audience :: Developers',
        'Topic :: Scientific/Engineering',
        'Topic :: Software Development :: Assemblers',
        'Topic :: Software Development :: Compilers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
    ],
)
