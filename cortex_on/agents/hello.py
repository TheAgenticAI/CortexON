
@dataclass
class orchestrator_deps:
    websocket: Optional[WebSocket] = None
    stream_output: Optional[StreamResponse] = None
    # Add a collection to track agent-specific streams
    agent_responses: Optional[List[StreamResponse]] = None
    model_preference: str = "Anthropic"

async def get_model_preference() -> str:
    """Fetch model preference from ta_browser API"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8000/api/v1/model/preference") as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("model_preference", "Anthropic")
                else:
                    logfire.error(f"Failed to get model preference: {response.status}")
                    return "Anthropic"
    except Exception as e:
        logfire.error(f"Error getting model preference: {str(e)}")
        return "Anthropic"

async def initialize_orchestrator_agent():
    """Initialize the orchestrator agent with model preference from ta_browser"""
    model_preference = await get_model_preference()
    model = AnthropicModel(
        model_name=os.environ.get("ANTHROPIC_MODEL_NAME"),
        anthropic_client=get_client()
    )
    
    print(f"Orchestrator agent model initialized with MODEL PREFERENCE: {model_preference}")
    
    return Agent(
        model=model,
        name="Orchestrator Agent",
        system_prompt=orchestrator_system_prompt,
        deps_type=orchestrator_deps
    )

# Initialize the agent
orchestrator_agent = None

def get_orchestrator_agent():
    """Get the orchestrator agent, initializing it if necessary"""
    global orchestrator_agent
    if orchestrator_agent is None:
        raise RuntimeError("Orchestrator agent not initialized. Call initialize_orchestrator_agent() first.")
    return orchestrator_agent

@get_orchestrator_agent().tool
async def plan_task(ctx: RunContext[orchestrator_deps], task: str) -> str:
    """Plans the task and assigns it to the appropriate agents"""
    try:
        logfire.info(f"Planning task: {task}")
        
        # Create a new StreamResponse for Planner Agent
        planner_stream_output = StreamResponse(
            agent_name="Planner Agent",
            instructions=task,
            steps=[],
            output="",
            status_code=0
        )