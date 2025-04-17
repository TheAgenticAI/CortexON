# Standard library imports
import json
import os
import asyncio
from typing import Dict, List, Optional, Any, Union

# Third-party imports
import requests
import logfire
from dotenv import load_dotenv

# Import crawl4ai for web content extraction
try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
    from crawl4ai.content_filter_strategy import PruningContentFilter
    CRAWL4AI_AVAILABLE = True
except ImportError:
    logfire.warning("crawl4ai not installed. Will use fallback content extraction methods.")
    CRAWL4AI_AVAILABLE = False

# Import Beautiful Soup for fallback extraction
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    logfire.warning("BeautifulSoup not installed. Fallback extraction will be limited.")
    BS4_AVAILABLE = False

load_dotenv()

async def google_search(query: str, num_results: int = 10) -> str:
    """
    Performs a Google search using the Google Custom Search API and returns formatted results.
    
    Args:
        query: The search query string
        num_results: Number of results to return (max 10)
        
    Returns:
        Formatted string with search results including titles, URLs, and snippets
    """
    try:
        api_key = os.getenv('GOOGLE_API_KEY')
        cx = os.getenv('GOOGLE_CX')

        if not api_key or not cx:
            return "Error: GOOGLE_API_KEY or GOOGLE_CX environment variables are not set."
        
        base_url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": api_key,
            "cx": cx,
            "q": query,
            "num": min(num_results, 10)  # Ensure num doesn't exceed 10
        }
        
        logfire.info(f"Executing Google search for: {query}")
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        results = response.json()
        
        # Format the results in a readable form
        formatted_results = f"Search Results for '{query}':\n"
        formatted_results += f"Total Results: {results.get('searchInformation', {}).get('formattedTotalResults', 'N/A')}\n"
        formatted_results += f"Search Time: {results.get('searchInformation', {}).get('formattedSearchTime', 'N/A')} seconds\n\n"
        
        for item in results.get("items", []):
            formatted_results += f"Title: {item.get('title', 'N/A')}\n"
            formatted_results += f"URL: {item.get('link', 'N/A')}\n"
            formatted_results += f"Snippet: {item.get('snippet', 'N/A')}\n\n"
        
        return formatted_results
    
    except requests.RequestException as e:
        error_msg = f"Error performing Google search: {str(e)}"
        logfire.error(error_msg, exc_info=True)
        return error_msg
    except Exception as e:
        error_msg = f"An unexpected error occurred during search: {str(e)}"
        logfire.error(error_msg, exc_info=True)
        return error_msg

def _fallback_extract_content(url: str) -> str:
    """
    Fallback method to extract content from a web page using requests and BeautifulSoup.
    
    Args:
        url: The URL to extract content from
        
    Returns:
        Extracted content as plain text
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        if not BS4_AVAILABLE:
            # Very basic extraction if BeautifulSoup is not available
            return f"# Content from {url}\n\n" + response.text[:10000] + "...\n\n[Content truncated]"
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.extract()
        
        # Extract title
        title = soup.title.string if soup.title else "No title found"
        
        # Extract main content
        # Try common content containers
        main_content = soup.find('main') or soup.find('article') or soup.find(id='content') or soup.find(class_='content')
        
        if not main_content:
            # Fallback to body if no content container is found
            main_content = soup.body
        
        # Extract text and clean it up
        content = ""
        if main_content:
            paragraphs = main_content.find_all('p')
            content = "\n\n".join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
        
        if not content:
            # Last resort: just get all text from the body
            content = soup.body.get_text(separator='\n\n') if soup.body else "No content extracted"
        
        # Format as markdown
        markdown = f"# {title}\n\n"
        markdown += f"Source: {url}\n\n"
        markdown += "## Content\n\n"
        markdown += content
        
        return markdown
    
    except Exception as e:
        error_msg = f"Error in fallback extraction from {url}: {str(e)}"
        logfire.error(error_msg, exc_info=True)
        return f"Failed to extract content: {error_msg}"

async def extract_content_from_url(url: str, user_query: Optional[str] = None) -> str:
    """
    Extracts content from a web page using crawl4ai or fallback method.
    
    Args:
        url: The URL to extract content from
        user_query: Optional query to focus content extraction
        
    Returns:
        Extracted content in Markdown format
    """
    if not CRAWL4AI_AVAILABLE:
        logfire.info(f"Using fallback extraction for URL: {url}")
        return _fallback_extract_content(url)
    
    try:
        logfire.info(f"Extracting content from URL: {url}")
        
        # Configure browser settings
        browser_config = BrowserConfig(
            headless=True,
            verbose=False
        )
        
        # Configure content filtering based on whether a user query is provided
        if user_query:
            # BM25-based filtering using the user query for focus
            from crawl4ai.content_filter_strategy import BM25ContentFilter
            content_filter = BM25ContentFilter(user_query=user_query, bm25_threshold=1.0)
        else:
            # General pruning for clean output without a specific focus
            content_filter = PruningContentFilter(threshold=0.48, threshold_type="fixed", min_word_threshold=0)
        
        # Configure the crawler run
        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.ENABLED,
            markdown_generator=DefaultMarkdownGenerator(content_filter=content_filter)
        )
        
        # Execute the crawl
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(
                url=url,
                config=run_config
            )
            
            # Return the fit_markdown which is optimized for LLM processing
            # or fall back to raw_markdown if fit_markdown is not available
            if hasattr(result.markdown, 'fit_markdown') and result.markdown.fit_markdown:
                extracted_content = result.markdown.fit_markdown
            else:
                extracted_content = result.markdown.raw_markdown
                
            logfire.info(f"Successfully extracted {len(extracted_content)} characters from {url}")
            return extracted_content
    
    except Exception as e:
        error_msg = f"Error extracting content with crawl4ai from {url}: {str(e)}"
        logfire.error(error_msg, exc_info=True)
        
        # Try fallback extraction if crawl4ai fails
        logfire.info(f"Attempting fallback extraction for {url}")
        return _fallback_extract_content(url)

async def batch_extract_content(urls: List[str], user_query: Optional[str] = None) -> Dict[str, str]:
    """
    Extracts content from multiple URLs in parallel.
    
    Args:
        urls: List of URLs to extract content from
        user_query: Optional query to focus content extraction
        
    Returns:
        Dictionary mapping URLs to their extracted content
    """
    logfire.info(f"Starting batch extraction from {len(urls)} URLs")
    
    # Create tasks for each URL
    tasks = [extract_content_from_url(url, user_query) for url in urls]
    
    # Execute all tasks concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Map results to URLs
    content_map = {}
    for i, url in enumerate(urls):
        if isinstance(results[i], Exception):
            content_map[url] = f"Error extracting content: {str(results[i])}"
        else:
            content_map[url] = results[i]
    
    return content_map 