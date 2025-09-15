# honeybee-designbuilder

![Honeybee](https://www.ladybug.tools/assets/img/honeybee.png) ![DesignBuilder](https://avatars.githubusercontent.com/u/17565908?s=200&v=4)

[![Build Status](https://github.com/ladybug-tools/honeybee-designbuilder/workflows/CI/badge.svg)](https://github.com/ladybug-tools/honeybee-designbuilder/actions)
[![Python 3.10](https://img.shields.io/badge/python-3.10-orange.svg)](https://www.python.org/downloads/release/python-3100/)

Honeybee extension for translation to/from DesignBuilder.

Translation is accomplished using XML files following the
[DesignBuilder DsbXML Schema](https://github.com/DesignBuilderSoftware/db-dsbxml-schema).
Files can be imported to DesignBuilder using the [DsbXML Importer](https://designbuilder.co.uk/helpv2025.1/#ImportDesignBuilderXML.htm?TocPath=Get%2520Started%257CMenu%257CFile%2520Menu%257C_____2)

## Installation

`pip install -U honeybe-designbuilder`

## QuickStart

```console
import honeybee_designbuilder
```

## [API Documentation](http://ladybug-tools.github.io/honeybee-designbuilder/docs)

## Local Development

1. Clone this repo locally
```console
git clone git@github.com:ladybug-tools/honeybee-designbuilder

# or

git clone https://github.com/ladybug-tools/honeybee-designbuilder
```
2. Install dependencies:
```
cd honeybee-designbuilder
pip install -r dev-requirements.txt
pip install -r requirements.txt
```

3. Run Tests:
```console
python -m pytest tests/
```

4. Generate Documentation:
```console
sphinx-apidoc -f -e -d 4 -o ./docs ./honeybee_designbuilder
sphinx-build -b html ./docs ./docs/_build/docs
```