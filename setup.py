# Part of the jsonrpc2-zeromq-python project.
# (c) 2012 Dan Brown, All Rights Reserved.
# Please see the LICENSE file in the root of this project for license
# information.

from setuptools import setup

description = "Library for JSON-RPC 2.0 over ZeroMQ"

import os
try:
    long_description = open(os.path.join(os.path.dirname(__file__),
                                         'README.rst')).read()
except IOError:
    long_description = description

version = "1.1.2"

setup(
    name = "jsonrpc2-zeromq",
    version = version,
    description = description,
    long_description = long_description,
    url = "https://github.com/dwb/python-jsonrpc2-zeromq",
    download_url = ("https://github.com/dwb/"
                    "jsonrpc2-zeromq-python/archive/v{}.tar.gz".
                    format(version)),
    classifiers = [
        "Programming Language :: Python :: 2.7",
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        ],
    author = "Dan Brown",
    author_email = "dan@stompydan.net",
    license = "License :: OSI Approved :: BSD License",
    packages = ["jsonrpc2_zeromq"],
    install_requires=[
        "setuptools",
        "pyzmq>=2.1.11,<15",
        ],
    tests_require=[
        "nose==1.3.4",
        ],
    test_suite="nose.collector",
    )
