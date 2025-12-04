from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="resp_server",
    version="0.1.1",
    author="Vivek Dagar",
    author_email="vivek@example.com",
    description="A lightweight, embeddable, pure-Python Redis-compatible server for testing",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/vivekdagar/redis-python",
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Testing",
        "Topic :: Database",
    ],
    python_requires=">=3.9",
    keywords="redis server embedded testing mock",
    entry_points={
        "console_scripts": [
            "resp_server=resp_server.main:main",
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/vivekdagar/redis-python/issues",
        "Source": "https://github.com/vivekdagar/redis-python",
    },
)
