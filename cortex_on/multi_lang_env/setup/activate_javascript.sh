#!/bin/bash

# Activate JavaScript environment
echo "Activating JavaScript environment"
export LANG_ENV="javascript"
cd /app/javascript
export PATH="/usr/bin:$PATH"
echo "Node.js $(node --version) environment activated" 