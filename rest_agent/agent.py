"""A simple REST API agent."""
import requests
from google.adk.agents import Agent

def make_request(url: str) -> dict:
    try:
        # Make the GET request
        response = requests.get(url)
        
        # Check if the request was successful
        if response.status_code == 200:
            # Try to parse JSON response
            try:
                data = response.json()
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "data": data
                }
            except ValueError:
                # If response is not JSON, return text
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "data": response.text
                }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": f"Request failed with status code {response.status_code}"
            }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Request failed: {str(e)}"
        }

root_agent = Agent(
    model='gemini-2.0-flash-001',
    name='rest_agent',
    description='A simple agent that makes HTTP requests and returns the response data',
    instruction="""I am a REST API agent that makes HTTP requests and returns the response.
When you give me a URL, I will:
1. Make a GET request to the URL
2. Return the response data if successful
3. Return an error message if the request fails
4. Handle both JSON and non-JSON responses

Example usage:
User: Get data from https://api.github.com/users/google
Agent: [Shows the response data or error message]""",
    tools=[make_request]
)
