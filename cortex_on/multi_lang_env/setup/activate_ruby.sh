#!/bin/bash

# Activate Ruby environment
echo "Activating Ruby environment"
export LANG_ENV="ruby"
cd /app/ruby
export PATH="/usr/bin:$PATH"
echo "Ruby $(ruby --version) environment activated" 