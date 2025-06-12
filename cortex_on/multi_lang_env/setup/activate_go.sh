#!/bin/bash

# Activate Go environment
echo "Activating Go environment"
export LANG_ENV="go"
cd /app/go
export PATH="/usr/local/go/bin:$PATH"
echo "Go $(go version) environment activated"