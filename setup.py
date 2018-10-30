import sys
from setuptools import setup, find_packages

with open('README.rst', 'rb') as f:
    long_description = f.read().decode('utf-8')


setup(
    name = "django-complex-fields",
    version = "0.1.0",
    license = "LGPL",
    description = "An extenstion for Django that provides translation, version and source by field. Can be adapted to personalize fields",
    long_description = "long_description",
    author = "Guillaume Auger",
    author_email = "gauger@caravan.coop",
    url = "https://github.com/caravancoop/complex-fields",
    packages = find_packages(),
    package_data = {
        "complex_fields": ["templates/*.html"]
    },
    zip_safe=False,
    install_requires=[
        "Django>=1.8.3<2.0",
        "django-reversion==2.0.4",
        "django-languages-plus==0.1.5",
    ],
    classifiers = [
        "Development Status :: 2 - Pre-Alpha",
        "Framework :: Django",
        "Intended Audience :: Developers",
        "Licence :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.4",
        "Topic :: Database",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Text Processing :: Linguistic",
    ]
)
