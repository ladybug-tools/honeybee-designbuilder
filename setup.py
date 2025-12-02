import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

with open('standards-requirements.txt') as f:
    standards_requirements = f.read().splitlines()

setuptools.setup(
    name="honeybee-designbuilder",
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
    author="Ladybug Tools",
    author_email="info@ladybug.tools",
    description="Honeybee extension for translating HBJSON files to dsbXML files for DesignBuilder",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ladybug-tools/honeybee-designbuilder",
    packages=setuptools.find_packages(exclude=["tests*", "equest_docs*"]),
    install_requires=requirements,
    extras_require={
        'standards': standards_requirements
    },
    include_package_data=True,
    entry_points={
        "console_scripts": ["honeybee-designbuilder = honeybee_designbuilder.cli:designbuilder"]
    },
    classifiers=[
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: Implementation :: CPython",
        "Operating System :: OS Independent"
    ],
    license="AGPL-3.0"
)
