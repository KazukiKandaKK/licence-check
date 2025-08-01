#!/usr/bin/env bash
set -e

SCAN_DIR=scans/scancode_output
mkdir -p "$SCAN_DIR"

echo "Pulling ScanCode Toolkit Docker image..."
docker pull --platform linux/amd64 beevelop/scancode:latest

echo "Starting license scanning..."

for dir in generated/*; do
  if [ -d "$dir" ]; then
    lang=$(basename "$dir")
    echo "Scanning $lang files..."
    
    docker run --rm --platform linux/amd64 \
      -v "$PWD/$dir":/project/src \
      -v "$PWD/$SCAN_DIR":/project/out \
      beevelop/scancode:latest \
      scancode -n 4 --json-pp /project/out/${lang}.json /project/src
    
    echo "Completed scanning $lang"
  fi
done

echo "License scanning complete! Results saved in $SCAN_DIR/"