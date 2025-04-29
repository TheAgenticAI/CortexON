import json
from utils.code_formatter import (
    format_code_for_frontend,
    format_output_for_frontend,
    format_execution_result
)

def test_code_formatting():
    # Test Python code formatting
    python_code = """
def hello_world():
    print("Hello, World!")

for i in range(5):
    print(f"Number: {i}")
    
hello_world()



# Too many blank lines above
"""

    formatted_python = format_code_for_frontend(python_code, "python")
    print("Python code formatting:")
    print(formatted_python)
    print("\n" + "-"*50 + "\n")

    # Test JavaScript code formatting
    js_code = """
function helloWorld() {
    console.log("Hello, World!");
}

for (let i = 0; i < 5; i++) {
    console.log(`Number: ${i}`);
}

helloWorld();
"""

    formatted_js = format_code_for_frontend(js_code, "js")
    print("JavaScript code formatting:")
    print(formatted_js)
    print("\n" + "-"*50 + "\n")

    # Test output formatting
    output = "Hello, World!\nNumber: 0\nNumber: 1\nNumber: 2\nNumber: 3\nNumber: 4"
    formatted_output = format_output_for_frontend(output)
    print("Output formatting:")
    print(formatted_output)
    print("\n" + "-"*50 + "\n")

    # Test error formatting
    error_result = {"error": "Container timeout after 30 seconds"}
    formatted_error = format_execution_result(python_code, "python", error_result)
    print("Error formatting:")
    print(formatted_error)
    print("\n" + "-"*50 + "\n")

    # Test successful execution result formatting
    success_result = {
        "execution_id": "12345",
        "language": "python",
        "stdout": "Hello, World!\nNumber: 0\nNumber: 1\nNumber: 2\nNumber: 3\nNumber: 4",
        "stderr": "",
        "exit_code": 0,
        "success": True
    }
    formatted_success = format_execution_result(python_code, "python", success_result)
    print("Success result formatting:")
    print(formatted_success)
    print("\n" + "-"*50 + "\n")

    # Test failed execution result formatting
    failed_result = {
        "execution_id": "12345",
        "language": "python",
        "stdout": "",
        "stderr": "NameError: name 'undefined_variable' is not defined",
        "exit_code": 1,
        "success": False
    }
    formatted_failure = format_execution_result(python_code, "python", failed_result)
    print("Failed result formatting:")
    print(formatted_failure)

if __name__ == "__main__":
    test_code_formatting() 