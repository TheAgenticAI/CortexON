#!/bin/bash

# Activate Java environment
echo "Activating Java environment"
export LANG_ENV="java"
cd /app/java
export JAVA_HOME=$(dirname $(dirname $(readlink -f $(which javac))))
export PATH="$JAVA_HOME/bin:$PATH"
echo "Java $(java -version 2>&1 | head -n 1) environment activated"