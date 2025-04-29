import asyncio
import logging
from utils.docker_executor import run_docker_container

# Set up logging
logging.basicConfig(level=logging.INFO)

# Test prime function code
prime_test_code = """
def is_prime(n):
    \"\"\"Check if a number is prime.\"\"\"
    if n <= 1:
        return False
    if n <= 3:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True

# Test cases
test_cases = [2, 3, 4, 5, 15, 17, 20, 97]
print("Testing prime numbers:")
for num in test_cases:
    result = is_prime(num)
    print(f"{num} is {'prime' if result else 'not prime'}")
"""

async def test_prime_function():
    print("Running Docker test for prime function...")
    result = await run_docker_container("python", prime_test_code)
    
    print("\n--- Execution Result ---")
    print(f"Execution ID: {result.get('execution_id')}")
    print(f"Success: {result.get('success')}")
    print(f"Exit Code: {result.get('exit_code')}")
    print("\n--- Output ---")
    print(result.get('stdout'))
    
    if result.get('stderr'):
        print("\n--- Errors ---")
        print(result.get('stderr'))

if __name__ == "__main__":
    asyncio.run(test_prime_function()) 