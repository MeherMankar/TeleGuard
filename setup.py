from setuptools import setup, find_packages

setup(
    name="teleguard",
    version="2.0.0",
    packages=find_packages(),
    install_requires=[
        "telethon==1.28.5",
        "aiohttp>=3.9.0",
        "cryptography>=43.0.1",
        "pymongo>=4.6.3",
        "motor>=3.3.0",
        "python-dotenv==1.0.0",
        "APScheduler==3.10.4",
        "requests>=2.31.0",
    ],
    python_requires=">=3.12",
)