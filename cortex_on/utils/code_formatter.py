import re
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Language syntax highlighting mappings
LANGUAGE_HIGHLIGHTS = {
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "java": "java",
    "cpp": "cpp",
    "c++": "cpp",
    "c": "c",
    # Additional languages
    "ruby": "ruby",
    "go": "go",
    "rust": "rust",
    "php": "php",
    "csharp": "csharp",
    "kotlin": "kotlin",
    "swift": "swift",
    "r": "r",
    "scala": "scala",
    "perl": "perl",
    "dart": "dart",
    "julia": "julia"
}

def format_code_for_frontend(code: str, language: str) -> str:
    """
    Format code for frontend display with proper syntax highlighting.

    Args:
        code: The source code to format
        language: The programming language

    Returns:
        Markdown-formatted code ready for frontend display
    """
    # Normalize language name
    normalized_language = normalize_language(language)

    # Get proper language identifier for syntax highlighting
    highlight_lang = LANGUAGE_HIGHLIGHTS.get(normalized_language, normalized_language)

    # Clean up code (remove excessive newlines, normalize spacing)
    cleaned_code = clean_code(code)

    # Format as markdown code block with language syntax highlighting
    return f"```{highlight_lang}\n{cleaned_code}\n```"

def format_output_for_frontend(output: str) -> str:
    """
    Format execution output for frontend display.

    Args:
        output: The execution output text

    Returns:
        Formatted output text ready for frontend display
    """
    # Log the raw output for debugging
    logger.info(f"Raw output before formatting: [{output}]")

    # Check if output is None or empty
    if output is None:
        logger.info("Output is None")
        return "*No output produced*"

    # Clean up output
    cleaned_output = output.strip()

    if not cleaned_output:
        logger.info("Output is empty after stripping")
        return "*No output produced*"

    # Strip excessive blank lines
    cleaned_output = re.sub(r'\n{3,}', '\n\n', cleaned_output)

    # Log the final formatted output
    logger.info(f"Formatted output: [{cleaned_output}]")

    # Format terminal output section - using plain backticks for cleaner display
    return f"```\n{cleaned_output}\n```"

def format_execution_result(code: str, language: str, result: Dict) -> str:
    """
    Create a complete formatted output with both code and execution results.

    Args:
        code: The source code
        language: The programming language
        result: The execution result dictionary

    Returns:
        A formatted string containing both code and execution results
    """
    # Format the code section
    formatted_code = format_code_for_frontend(code, language)

    # Check if there was an error in execution setup (not in the code itself)
    if "error" in result:
        error_message = result["error"]
        logger.debug(f"Formatting error output: {error_message}")
        return f"{formatted_code}\n\n## Errors\n\n{format_output_for_frontend(error_message)}\n\n## Status\n\n**Γ¥î Execution failed**"

    # Process stdout and stderr
    stdout = result.get("stdout", "").strip()
    stderr = result.get("stderr", "").strip()

    # Log output for debugging
    logger.info(f"Formatting stdout: {stdout[:200]}{'...' if len(stdout) > 200 else ''}")
    logger.info(f"Formatting stderr: {stderr[:200]}{'...' if len(stderr) > 200 else ''}")

    # Format sections for the frontend
    sections = []

    # Always add the code section first
    sections.append(formatted_code)

    # Add output section if stdout exists or explicitly note if no output
    if stdout:
        sections.append(f"## Output\n\n{format_output_for_frontend(stdout)}")
    else:
        sections.append("## Output\n\n*No output produced*")

    # Add errors section if stderr exists
    if stderr:
        sections.append(f"## Errors\n\n{format_output_for_frontend(stderr)}")

    # Add execution status with emoji for better visibility
    if result.get("success", False):
        status = "**Γ£à Execution completed successfully**"
    else:
        exit_code = result.get("exit_code", "unknown")
        status = f"**Γ¥î Execution failed** (Exit code: {exit_code})"

    sections.append(f"## Status\n\n{status}")

    # Join all sections with double newlines for proper separation
    return "\n\n".join(sections)

def normalize_language(language: str) -> str:
    """
    Normalize language name.

    Args:
        language: The programming language name to normalize

    Returns:
        Normalized language name
    """
    # Convert to lowercase and strip whitespace
    normalized = language.lower().strip()

    # Handle common aliases
    language_aliases = {
        "python3": "python",
        "py": "python",
        "js": "javascript",
        "ts": "typescript",
        "node": "javascript",
        "nodejs": "javascript",
        "java": "java",
        "c++": "cpp",
        "c": "c",
        # Additional languages
        "rb": "ruby",
        "golang": "go",
        "rs": "rust",
        "kt": "kotlin",
        "dotnet": "csharp",
        "c#": "csharp",
        "dot-net": "csharp",
        "pl": "perl",
        "php7": "php",
        "php8": "php",
        "jl": "julia",
        "dart2": "dart",
        "scala3": "scala",
        "r-lang": "r"
    }

    return language_aliases.get(normalized, normalized)

def clean_code(code: str) -> str:
    """
    Clean up code by normalizing whitespace, indentation, etc.

    Args:
        code: The source code to clean

    Returns:
        Cleaned code
    """
    # Remove leading/trailing whitespace
    cleaned = code.strip()

    # Remove multiple consecutive blank lines (more than 2)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

    return cleaned