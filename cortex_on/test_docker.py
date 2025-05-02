import asyncio
import logging
from utils.docker_executor import get_or_create_environment, cleanup_environments

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_docker_environment():
    try:
        # Create test environment
        env_id = "test123"
        env = get_or_create_environment(env_id, 'python')
        
        # Start the environment
        logger.info("Starting Docker environment...")
        start_result = await env.start()
        logger.info(f"Start result: {start_result}")
        
        # Write a test file
        test_content = 'print("Hello from Docker!")'
        logger.info("Writing test file...")
        write_result = await env.write_file('test.py', test_content)
        logger.info(f"Write result: {write_result}")
        
        # List files
        logger.info("Listing files...")
        list_result = await env.list_files()
        logger.info(f"List result: {list_result}")
        
        # Read the file back
        logger.info("Reading file...")
        read_result = await env.read_file('test.py')
        logger.info(f"Read result: {read_result}")
        
        # Execute the file
        logger.info("Executing file...")
        exec_result = await env.execute_code('python', 'test.py')
        logger.info(f"Execution result: {exec_result}")
        
        # Clean up
        logger.info("Stopping environment...")
        stop_result = await env.stop()
        logger.info(f"Stop result: {stop_result}")
        
        return True
    except Exception as e:
        logger.error(f"Error in test: {str(e)}", exc_info=True)
        return False
    finally:
        # Ensure cleanup
        await cleanup_environments()
        
if __name__ == "__main__":
    logger.info("Starting Docker environment test...")
    asyncio.run(test_docker_environment())
    logger.info("Test completed.") 