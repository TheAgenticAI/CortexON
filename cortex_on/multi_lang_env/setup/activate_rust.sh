#!/bin/bash

# Activate Rust environment
echo "Activating Rust environment"
export LANG_ENV="rust"
cd /app/rust
export PATH="$HOME/.cargo/bin:$PATH"
echo "Rust $(rustc --version) environment activated" 