
from setuptools import setup, find_packages

with open('requirements.txt') as f:
    required_packages = []
    for line in f:
        if not line.startswith('-e'):
            required_packages.append(line.strip())

setup(
    name='imaegete',
    version='0.1.1',
    description='Cross-platform image image viewer',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Aaron Colichia',
    url='https://github.com/actx4gh/imaegete',
    packages=find_packages(),
    install_requires=required_packages,
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.10',
)
