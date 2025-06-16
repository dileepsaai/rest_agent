# REST Agent

A REST API and SQL Server agent built using Google's ADK framework that can make HTTP requests and execute SQL queries.

## Features

- Make HTTP GET requests to any URL
- Execute SQL queries and retrieve data from SQL Server
- Handle both JSON and non-JSON responses
- Structured response format with success/error information
- Powered by Google's Gemini 2.0 Flash model

## Prerequisites

- Python 3.7 or higher
- pip (Python package installer)
- SQL Server instance
- ODBC Driver for SQL Server

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

4. Configure Postgres Server
```
docker run --name postgres-db \
  -e POSTGRES_PASSWORD=mysecretpassword \
  -e POSTGRES_DB=testdb \
  -p 5432:5432 \
  -d postgres
```

5. Set up environment variables:
Create a `.env` file in the root directory and add your credentials:
```
GOOGLE_API_KEY=your_api_key_here
SQL_CONNECTION_STRING=DRIVER={ODBC Driver 17 for SQL Server};SERVER=your_server;DATABASE=your_database;UID=your_username;PWD=your_password
```

Note: Make sure to replace the SQL connection string with your actual SQL Server details.

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
     - "Show me all users from the users table"
     - "What are the top 5 products by sales?"

The agent will respond with structured data in the chat interface, showing:
- Success/failure status
- HTTP status code (for REST requests)
- Response data or error message
- Row count (for SQL queries)

## Dependencies

- google-adk[database]==0.3.0
- yfinance==0.2.56
- psutil==5.9.5
- litellm==1.66.3
- google-generativeai==0.8.5
- python-dotenv==1.1.0
- pyodbc==5.0.1
- pandas==2.2.0

## Steps to setup the Postgres DB and population
### Setup the Postgres DB using Docker
```
docker run --name postgres-db \                                
  -e POSTGRES_PASSWORD=mysecretpassword \
  -e POSTGRES_DB=testdb \
  -p 5432:5432 \
  -d postgres
  ```

### Copy the sql file to docker container
```
 docker cp init.sql postgres-db:/init.sql
```

### Run the sql file for schema creating and data population
```
docker exec -u postgres postgres-db psql -d testdb -f /init.sql
```