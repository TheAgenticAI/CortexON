#!/bin/bash

# Activate C++ environment
echo "Activating C++ environment"
export LANG_ENV="cpp"
cd /app/cpp
export PATH="/usr/bin:$PATH"
echo "C++ $(g++ --version | head -n 1) environment activated"