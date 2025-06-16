# SQL Agent

A PostgreSQL agent built using Google's ADK framework that can execute queries and retrieve data from your PostgreSQL database.

## Features

- Execute SQL queries and retrieve data from PostgreSQL
- Handle various types of SQL queries (SELECT, INSERT, UPDATE, DELETE)
- Structured response format with success/error information
- Powered by Google's Gemini 2.0 Flash model

## Prerequisites

- Python 3.7 or higher
- pip (Python package installer)
- PostgreSQL database server

## Installation

1. Make sure you have the required dependencies installed:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
Create a `.env` file in the root directory and add your PostgreSQL connection details:
```
GOOGLE_API_KEY=your_api_key_here
POSTGRES_DB=your_database_name
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password
POSTGRES_HOST=localhost  # or your database host
POSTGRES_PORT=5432      # default PostgreSQL port
```

Note: Make sure to replace the PostgreSQL connection parameters with your actual database details.

## Running with ADK Web Interface

1. Make sure your virtual environment is activated:
```bash
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
   - Select the "sql_agent" from the list of available agents
   - You can now interact with the agent through the chat interface
   - Try commands like:
     - "Show me all users from the users table"
     - "What are the top 5 products by sales?"
     - "Insert a new user into the users table"
     - "Update the price of product with ID 123"

The agent will respond with structured data in the chat interface, showing:
- Success/failure status
- Query results or error message
- Row count (for SELECT queries)

## Example Queries

Here are some example queries you can try:

1. Basic SELECT queries:
   - "Show me all users from the users table"
   - "List all products with price greater than $100"
   - "Get the latest 10 orders"

2. Aggregation queries:
   - "What are the top 5 products by sales?"
   - "Show me total sales by month"
   - "Calculate average order value by customer"

3. JOIN queries:
   - "Show me all orders with customer details"
   - "List products with their category names"
   - "Get employee details with their department information"

4. Data modification:
   - "Insert a new user into the users table"
   - "Update the price of product with ID 123"
   - "Delete all inactive users"

## Dependencies

- google-adk[database]==0.3.0
- psycopg2-binary==2.9.9
- pandas==2.2.0
- python-dotenv==1.1.0 