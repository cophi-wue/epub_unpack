from setuptools import find_packages, setup

#from extractor import __version__
__version__ = "0.1.0"
setup(
    name='EpubExtractor',
    author='Lennart Keller',
    author_email='lennartkeller@gmail.com',
    version=__version__,
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "Click",
        "lxml",
        "beautifulsoup4",
        "saxonche",
        "css_inline",
        "ebooklib @ git+https://github.com/LennartKeller/ebooklib.git",
        "tqdm",
        "Jinja2",
        "joblib",
        "chardet",
        "scikit-learn"
    ],
    entry_points={
        "console_scripts": [
            "epx = extractor.cli:cli",
        ],
    },
)