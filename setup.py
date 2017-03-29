#!/usr/bin/python3

from setuptools import setup
import image_builder


setup(
    name=image_builder.__productname__,
    description=image_builder.__description__,
    version=image_builder.__version__,
    author=image_builder.__author__,
    author_email=image_builder.__author_email__,
    url=image_builder.__url__,
    install_requires=["keystoneauth1",
                      "python-novaclient",
                      "python-glanceclient"],
    packages=['image_builder'],
    entry_points={
        'console_scripts': [
            'imagebuilder = image_builder.imagebuilder:main'
            ]
        }
    )
