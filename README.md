# REST Agent

A simple REST API agent built using Google's ADK framework that can make HTTP requests and process responses.

## Features

- Make HTTP GET requests to any URL
- Handle both JSON and non-JSON responses
- Structured response format with success/error information
- Powered by Google's Gemini 2.0 Flash model

## Prerequisites

- Python 3.7 or higher
- pip (Python package installer)

## Installation

1. Clone the repository:
```bash
git clone <your-repository-url>
cd rest_agent
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate
```

3. Install the required dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
Create a `.env` file in the root directory and add your Google API key:
```
GOOGLE_API_KEY=your_api_key_here
```

## Usage

The REST agent can be used to make HTTP GET requests to any URL. Here's how to use it:

```python
from rest_agent.agent import root_agent

# Example: Get data from a public API
response = root_agent.run("Get data from https://api.github.com/users/google")
print(response)
```

The agent will return a structured response in the following format:
```python
{
    "success": True,
    "status_code": 200,
    "data": {...}  # Response data (JSON or text)
}
```

Or in case of an error:
```python
{
    "success": False,
    "status_code": 404,  # If applicable
    "error": "Error message"
}
```

## Dependencies

- google-adk[database]==0.3.0
- yfinance==0.2.56
- psutil==5.9.5
- litellm==1.66.3
- google-generativeai==0.8.5
- python-dotenv==1.1.0

