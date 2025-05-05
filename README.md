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

This project uses HashiCorp Cloud Platform (HCP) Vault for secure secrets management. While you can either self-host Vault or use HCP Vault, we recommend using HCP Vault for the best managed experience. For HCP Vault Dedicated cluster setup, follow the [official HashiCorp documentation](https://developer.hashicorp.com/vault/tutorials/get-started-hcp-vault-dedicated/create-cluster).

#### WebSocket
- `VITE_WEBSOCKET_URL=ws://localhost:8081/ws`

#### Configuring External MCP Servers (OPTIONAL)

CortexON supports integration with external MCP (Model Context Protocol) servers for extended capabilities. Configure these in the `cortex_on/config/external_mcp_servers.json` file.

#### 1. GitHub Personal Access Token

1. **Create a GitHub Account** if you don't already have one at [github.com](https://github.com)

2. **Generate a Personal Access Token (PAT)**:
   - Follow the steps as listed here: [Personal Access Token Setup](https://github.com/modelcontextprotocol/servers/tree/main/src/github#setup)

3. **Add the Token to Your Configuration**:
   - Open `cortex_on/config/external_mcp_servers.json`
   - Find the GitHub section and replace the empty token:
   ```json
   "env": {
     "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_YourTokenHere"
   }
   ```
4. **Sample Queries**
  - Update the README.md file in the <repo_name> repository by <github_username> on branch main. Insert the line "Changed by CortexOn" in the end. Provide the updated file content as the content parameter and set branch as main.
  - List the latest commit and in which repo the commit was made by <github_username>

#### 2. Google Maps API Key

1. **Create a Google Cloud Account**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create an account or sign in with your Google account

2. **Create a New Project**:
   - In the cloud console, click on the project dropdown at the top
   - Click "New Project"
   - Name it (e.g., "CortexON Maps")
   - Click "Create"

3. **Enable the Required APIs**:
   - In your project, go to "APIs & Services" → "Library"
   - Search for and enable these APIs:
     * Maps JavaScript API
     * Geocoding API
     * Directions API
     * Places API
     * Distance Matrix API
   - You can enable more APIs as per your requirements

4. **Create an API Key**:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "API Key"
   - Your new API key will be displayed

5. **Add the API Key to Your Configuration**:
   - Open `cortex_on/config/external_mcp_servers.json`
   - Find the Google Maps section and replace the empty key:
   ```json
   "env": {
     "GOOGLE_MAPS_API_KEY": "<your-api-key-here>"
   }
   ```
6. **Sample Queries**
  - Find the closest pizza shops to \[address] within a 5-mile radius
  - Find the shortest driving route that includes the following stops: \[address 1], \[address 2], and \[address 3]

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
