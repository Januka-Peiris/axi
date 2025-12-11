#!/bin/bash
set -e

echo "Installing Backend..."
pip install -e backend

echo "Installing CLI..."
pip install -e axi-cli

echo "Setting up Frontend..."
cd frontend
npm install

echo "Ready! Run 'axi ui' to start."
