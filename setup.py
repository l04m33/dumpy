import os
import ast
from setuptools import setup


PACKAGE_NAME = 'dumpy'


def load_description(fname):
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, fname)) as f:
        return f.read().strip()


def get_version(fname):
    with open(fname) as f:
        source = f.read()
    module = ast.parse(source)
    for e in module.body:
        if isinstance(e, ast.Assign) and \
                len(e.targets) == 1 and \
                e.targets[0].id == '__version__' and \
                isinstance(e.value, ast.Str):
            return e.value.s
    raise RuntimeError('__version__ not found')


setup(
    name=PACKAGE_NAME,
    packages=[PACKAGE_NAME, '{}.tests'.format(PACKAGE_NAME)],
    version=get_version('{}/__init__.py'.format(PACKAGE_NAME)),
    description='Binary protocol parser',
    long_description=load_description('README.rst'),
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.4',
    ],
    author='Kay Zheng',
    author_email='l04m33@gmail.com',
    license='MIT',
    zip_safe=False,
    install_requires=[],
    extras_require={
        'dev': ['nose', 'coverage']
    },
)
