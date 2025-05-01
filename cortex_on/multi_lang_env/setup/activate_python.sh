#!/bin/bash

# Activate Python environment
echo "Activating Python environment"
export LANG_ENV="python"
cd /app/python
export PATH="/usr/bin:$PATH"
echo "Python $(python --version) environment activated" 