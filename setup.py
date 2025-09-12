#!/usr/bin/env python3
"""Setup script for Telegram Account Manager Bot"""

from pathlib import Path

from setuptools import find_packages, setup

# Read README
readme_path = Path("docs") / "README.md"
long_description = (
    readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""
)

# Read requirements
requirements_path = Path("config") / "requirements.txt"
requirements = []
if requirements_path.exists():
    requirements = requirements_path.read_text().strip().split("\n")
    requirements = [
        req.strip() for req in requirements if req.strip() and not req.startswith("#")
    ]

setup(
    name="telegram-account-manager",
    version="1.0.0",
    description="Professional Telegram bot for managing multiple user accounts with OTP destroyer protection",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Meher Mankar & Gutkesh",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "telegram-bot=main:main",
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
