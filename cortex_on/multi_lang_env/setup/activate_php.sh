#!/bin/bash

# Activate PHP environment
echo "Activating PHP environment"
export LANG_ENV="php"
cd /app/php
export PATH="/usr/bin:$PATH"
echo "PHP $(php --version | head -n 1) environment activated" 