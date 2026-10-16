#!/bin/sh
set -eu
python3 -m compileall -q apk_revival scripts tests
python3 -m unittest discover -s tests -v

