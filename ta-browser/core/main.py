from core.orchestrator import Orchestrator
import asyncio

# Global orchestrator instance
orchestrator = None

async def initialize_orchestrator():
    """Initialize the global orchestrator instance"""
    global orchestrator
    orchestrator = Orchestrator()
    await orchestrator.start()

async def main():
    """Main function to start the orchestrator"""
    # Initialize the orchestrator
    await initialize_orchestrator()
    
    # Keep the application running
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
