from setuptools import find_packages, setup

setup(
    name="ado-template-tracker",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pydantic",
        "pyyaml",
        "requests",
        "azure-identity",
        "aiohttp",
    ],
    entry_points={
        "console_scripts": [
            "adott=ado_template_tracker.main:main",  # Shorter CLI command
            "ado-template-tracker=ado_template_tracker.main:main",  # Full name
        ],
    },
    description="Track Azure DevOps pipeline template adoption across projects",
    author="Christos Galanopoulos",
    author_email="christosgalano@outlook.com",
    url="https://github.com/christosgalano/ado-template-tracker",
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
)
