<p align="center">
  <img src="frontend/src/assets/CortexON_logo_dark.svg" alt="CortexOn Logo" width="500"/>
</p>

# CortexON

**An Open Source Generalized AI Agent for Advanced Research and Business Process Automation**

CortexON is an open-source, multi-agent AI system inspired by advanced agent platforms such as Manus and OpenAI DeepResearch. Designed to seamlessly automate and simplify everyday tasks, CortexON excels at executing complex workflows including comprehensive research tasks, technical operations, and sophisticated business process automations.

<img src="assets/cortexon_flow.png" alt="CortexOn Logo" width="1000"/>

---

## Table of Contents

- [What is CortexON?](#what-is-cortexon)
- [How It Works](#how-it-works)
- [Key Capabilities](#key-capabilities)
- [Technical Stack](#technical-stack)
- [Quick Start Installation](#quick-start-installation)
  - [Environment Variables](#environment-variables)
  - [Docker Setup](#docker-setup)
  - [Access Services](#access-services)
- [Contributing](#contributing)
- [Code of Conduct](#code-of-conduct)
- [License](#license)

---

## What is CortexON?

Under the hood, CortexON integrates multiple specialized agents that dynamically collaborate to accomplish user-defined objectives. These specialized agents include:

- **Web Agent:** Handles real-time internet searches, data retrieval, and web interactions.
- **File Agent:** Manages file operations, organization, data extraction, and storage tasks.
- **Coder Agent:** Generates, debugs, and optimizes code snippets across various programming languages.
- **Executor Agent:** Executes tasks, manages workflows, and orchestrates inter-agent communications.
- **API Agent:** Integrates seamlessly with external services, APIs, and third-party software to extend automation capabilities.

Together, these agents dynamically coordinate, combining their unique capabilities to effectively automate complex tasks.

---

## How It Works

<img src="assets/cortexon_arch.png" alt="CortexOn Logo" width="1000"/>

---

## Key Capabilities
- Advanced, context-aware research automation
- Dynamic multi-agent orchestration
- Seamless integration with third-party APIs and services
- Code generation, debugging, and execution
- Efficient file and data management
- Personalized and interactive task execution, such as travel planning, market analysis, educational content creation, and business intelligence

---

## Technical Stack

CortexON is built using:
- **Framework:** PydanticAI multi-agent framework
- **Headless Browser:** Browserbase (Web Agent)
- **Search Engine:** Google SERP
- **Logging & Observability:** Pydantic Logfire
- **Backend:** FastAPI
- **Frontend:** React/TypeScript, TailwindCSS, Shadcn

---

## Quick Start Installation

### Environment Variables

Create a `.env` file with the following required variables:

#### Anthropic API
- `ANTHROPIC_MODEL_NAME=claude-3-7-sonnet-20250219`
- `ANTHROPIC_API_KEY=your_anthropic_api_key`

Obtain your API key from [Anthropic Console](https://console.anthropic.com).

#### Browserbase Configuration
- `BROWSERBASE_API_KEY=your_browserbase_api_key`
- `BROWSERBASE_PROJECT_ID=your_browserbase_project_id`

Set up your account and project at [Browserbase](https://browserbase.com).

#### Google Custom Search
- `GOOGLE_API_KEY=your_google_api_key`
- `GOOGLE_CX=your_google_cx_id`

Follow the steps at [Google Custom Search API](https://developers.google.com/custom-search/v1/overview).

#### Logging
- `LOGFIRE_TOKEN=your_logfire_token`

Create your token at [LogFire](https://pydantic.dev/logfire).

#### Vault Integration(OPTIONAL)
- `VITE_APP_API_BASE_URL=http://localhost:8000`
- `VITE_APP_VA_NAMESPACE=your_unique_namespace_id` (format unrestricted, UUID recommended)
- `VA_TOKEN=your_vault_authentication_token`
- `VA_URL=your_vault_service_endpoint`
- `VA_TTL=24h`
- `VA_TOKEN_REFRESH_SECONDS=43200`

#### WebSocket
- `VITE_WEBSOCKET_URL=ws://localhost:8081/ws`

### Docker Setup

1. Clone the CortexON repository:
```sh
git clone https://github.com/TheAgenticAI/CortexOn.git
cd CortexOn
```

2. Setup environment variables

3. **Docker Desktop Users (Optional)**: Enable host networking in Docker Desktop settings ([Guide](https://docs.docker.com/engine/network/drivers/host/)).

4. Build and run the Docker containers:
```sh
docker-compose build
docker-compose up
```

### Access Services
- **Frontend:** [http://localhost:3000](http://localhost:3000)
- **CortexON Backend:** [http://localhost:8081](http://localhost:8081) | API Docs: [http://localhost:8081/docs](http://localhost:8081/docs)
- **Agentic Browser:** [http://localhost:8000](http://localhost:8000) | API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Contributing

We welcome contributions from developers of all skill levels. Please see our [Contributing Guidelines](CONTRIBUTING.md) for detailed instructions.

---

## Code of Conduct

We are committed to providing a welcoming and inclusive environment for all contributors. Please adhere to our [Code of Conduct](CODE_OF_CONDUCT.md).

---

## License

CortexON is licensed under the [CortexON Open Source License Agreement](LICENSE).
