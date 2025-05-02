import asyncio
import json
from utils.docker_executor import run_docker_container

async def test_python():
    code = """
print("Hello from Python!")
for i in range(5):
    print(f"Number: {i}")
"""
    result = await run_docker_container("python", code)
    print("Python Test Results:")
    print(json.dumps(result, indent=2))
    
async def test_javascript():
    code = """
console.log("Hello from JavaScript!");
for (let i = 0; i < 5; i++) {
    console.log(`Number: ${i}`);
}
"""
    result = await run_docker_container("javascript", code)
    print("\nJavaScript Test Results:")
    print(json.dumps(result, indent=2))
    
async def test_cpp():
    code = """
#include <iostream>
using namespace std;

int main() {
    cout << "Hello from C++!" << endl;
    for (int i = 0; i < 5; i++) {
        cout << "Number: " << i << endl;
    }
    return 0;
}
"""
    result = await run_docker_container("cpp", code)
    print("\nC++ Test Results:")
    print(json.dumps(result, indent=2))
    
async def test_infinite_loop():
    code = """
# This should be killed after the timeout
while True:
    pass
"""
    result = await run_docker_container("python", code)
    print("\nInfinite Loop Test Results:")
    print(json.dumps(result, indent=2))

async def main():
    print("Testing Docker Executor...")
    await test_python()
    await test_javascript()
    await test_cpp()
    await test_infinite_loop()
    
if __name__ == "__main__":
    asyncio.run(main()) 