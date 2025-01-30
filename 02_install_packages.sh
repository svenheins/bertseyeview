#!/bin/bash
python -m pip install -r package_requirements.txt
python -m pip install --upgrade build
python -m build
python -m pip install dist/neo4jmanager-0.0.2-py3-none-any.whl
