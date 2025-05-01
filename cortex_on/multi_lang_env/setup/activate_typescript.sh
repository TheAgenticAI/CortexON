#!/bin/bash

# Activate TypeScript environment
echo "Activating TypeScript environment"
export LANG_ENV="typescript"
cd /app/typescript
export PATH="/usr/bin:$PATH"
echo "TypeScript $(tsc --version) environment activated" 