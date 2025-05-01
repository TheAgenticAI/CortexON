# CortexON Multi-Language Environment

This directory contains the configuration for a consolidated multi-language execution environment for CortexON. Instead of running separate containers for each programming language, we use a single container with all language runtimes installed and provide mechanisms to switch between them.

## How it Works

The multi-language container includes:

1. All necessary language runtimes (Python, Java, C++, JavaScript, TypeScript, Ruby, Go, Rust, PHP)
2. Language-specific directories under `/app/<language>` for code execution
3. Environment switching scripts that set up the appropriate context for each language

## Benefits

- **Reduced resource usage**: A single container instead of multiple containers
- **Simplified management**: Only one container to monitor and maintain
- **Easy scaling**: Add new languages by extending a single container

## Implementation Details

- The container is built from the Dockerfile in this directory
- Language activation scripts in `/setup/` handle environment switching
- Each language has a dedicated workspace in `/app/<language>`
- The main `use_env` script allows changing language contexts

## Usage

The container is primarily managed through the `DockerEnvironment` class in `cortex_on/utils/docker_executor.py`, which has been updated to:

1. Connect to a single container instead of multiple containers
2. Switch language environments as needed
3. Execute code in the appropriate language context

## Adding a New Language

To add support for a new language:

1. Update the Dockerfile to install the required runtime and tools
2. Create an activation script in the `setup/` directory
3. Add the language configuration to `SUPPORTED_LANGUAGES` in `docker_executor.py`
4. Add an entry in the `use_env` script in the Dockerfile

## Building the Container

The container is built automatically as part of the main docker-compose setup:

```bash
docker-compose build multi_language_env
```

## Running the Container Standalone

If needed, you can run the container standalone:

```bash
docker-compose up multi_language_env
``` 