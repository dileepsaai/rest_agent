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

## Running with ADK Web Interface

1. Make sure you're in the project directory and your virtual environment is activated:
```bash
cd rest_agent
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Start the ADK web interface:
```bash
adk web
```

3. Open your web browser and navigate to:
```
http://localhost:8000
```

4. In the ADK web interface:
   - Select the "rest_agent" from the list of available agents
   - You can now interact with the agent through the chat interface
   - Try commands like:
     - "Get data from https://api.github.com/users/google"
     - "Make a request to https://jsonplaceholder.typicode.com/posts/1"

The agent will respond with structured data in the chat interface, showing:
- Success/failure status
- HTTP status code
- Response data or error message

## Dependencies

- google-adk[database]==0.3.0
- yfinance==0.2.56
- psutil==5.9.5
- litellm==1.66.3
- google-generativeai==0.8.5
- python-dotenv==1.1.0

