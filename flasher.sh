#!/bin/bash

set -e

FQBN=arduino:avr:uno
PORT=/dev/ttyUSB0
SKETCH_PATH=/app/path/to/sketch

arduino-cli compile --fqbn $FQBN $SKETCH_PATH
arduino-cli upload -p $PORT --fqbn $FQBN $SKETCH_PATH
