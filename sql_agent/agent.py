"""A PostgreSQL agent that can execute queries and retrieve data."""
import psycopg2
import pandas as pd
from google.adk.agents import Agent
from typing import Dict, Any, List, Optional, Tuple, Set
import os
from dotenv import load_dotenv
import re
import json
from datetime import datetime
from pandas import Timestamp
import difflib
from decimal import Decimal

# Load environment variables
load_dotenv()

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (Timestamp, datetime)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

def get_table_constraints(conn: psycopg2.extensions.connection) -> Dict[str, Dict[str, Any]]:
    """
    Get primary key and foreign key constraints for all tables.
    
    Args:
        conn: PostgreSQL connection
        
    Returns:
        Dict containing table constraints
    """
    # Get primary keys
    pk_query = """
    SELECT
        tc.table_name,
        kc.column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kc
        ON kc.constraint_name = tc.constraint_name
    WHERE tc.constraint_type = 'PRIMARY KEY'
    ORDER BY tc.table_name, kc.ordinal_position;
    """
    
    # Get foreign keys
    fk_query = """
    SELECT
        tc.table_name AS table_name,
        kcu.column_name AS column_name,
        ccu.table_name AS foreign_table_name,
        ccu.column_name AS foreign_column_name
    FROM information_schema.table_constraints AS tc
    JOIN information_schema.key_column_usage AS kcu
        ON tc.constraint_name = kcu.constraint_name
    JOIN information_schema.constraint_column_usage AS ccu
        ON ccu.constraint_name = tc.constraint_name
    WHERE tc.constraint_type = 'FOREIGN KEY';
    """
    
    pk_df = pd.read_sql(pk_query, conn)
    fk_df = pd.read_sql(fk_query, conn)
    
    # Organize constraints by table
    constraints = {}
    
    # Process primary keys
    for _, row in pk_df.iterrows():
        table_name = row['table_name']
        if table_name not in constraints:
            constraints[table_name] = {'primary_keys': [], 'foreign_keys': []}
        constraints[table_name]['primary_keys'].append(row['column_name'])
    
    # Process foreign keys
    for _, row in fk_df.iterrows():
        table_name = row['table_name']
        if table_name not in constraints:
            constraints[table_name] = {'primary_keys': [], 'foreign_keys': []}
        constraints[table_name]['foreign_keys'].append({
            'column': row['column_name'],
            'references': {
                'table': row['foreign_table_name'],
                'column': row['foreign_column_name']
            }
        })
    
    return constraints

def get_related_tables(table: str, constraints: Dict[str, Dict[str, Any]]) -> Set[str]:
    """
    Get all tables related to the given table through foreign keys.
    
    Args:
        table: Table name
        constraints: Table constraints dictionary
        
    Returns:
        Set of related table names
    """
    related = set()
    
    # Get tables that reference this table
    for t, const in constraints.items():
        for fk in const['foreign_keys']:
            if fk['references']['table'] == table:
                related.add(t)
    
    # Get tables referenced by this table
    if table in constraints:
        for fk in constraints[table]['foreign_keys']:
            related.add(fk['references']['table'])
    
    return related

def get_fuzzy_matched_tables(query: str, tables: List[str], threshold: float = 0.7) -> List[str]:
    query_words = query.lower().split()
    matches = []
    for table in tables:
        for word in query_words:
            ratio = difflib.SequenceMatcher(None, table.lower(), word).ratio()
            if ratio > threshold:
                matches.append(table)
    return matches


def construct_join_conditions(tables: List[str], constraints: Dict[str, Dict[str, Any]]) -> List[str]:
    """
    Construct JOIN conditions based on foreign key relationships.
    
    Args:
        tables: List of tables to join
        constraints: Table constraints dictionary
        
    Returns:
        List of JOIN conditions
    """
    join_conditions = []
    used_joins = set()
    
    for i, table1 in enumerate(tables):
        for table2 in tables[i+1:]:
            # Check if tables are related
            if table1 in constraints and table2 in constraints:
                # Check foreign keys in table1
                for fk in constraints[table1]['foreign_keys']:
                    if fk['references']['table'] == table2:
                        join = f"{table1}.{fk['column']} = {table2}.{fk['references']['column']}"
                        if join not in used_joins:
                            join_conditions.append(join)
                            used_joins.add(join)
                
                # Check foreign keys in table2
                for fk in constraints[table2]['foreign_keys']:
                    if fk['references']['table'] == table1:
                        join = f"{table2}.{fk['column']} = {table1}.{fk['references']['column']}"
                        if join not in used_joins:
                            join_conditions.append(join)
                            used_joins.add(join)
    
    return join_conditions

def get_table_schema(conn: psycopg2.extensions.connection, table_name: str) -> Dict[str, List[str]]:
    """
    Get the schema information for a table.
    
    Args:
        conn: PostgreSQL connection
        table_name: Name of the table
        
    Returns:
        Dict containing column names and their data types
    """
    query = """
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = %s
    ORDER BY ordinal_position;
    """
    df = pd.read_sql(query, conn, params=(table_name,))
    return {
        'columns': df['column_name'].tolist(),
        'types': df['data_type'].tolist(),
        'nullable': df['is_nullable'].tolist()
    }

def get_all_tables(conn: psycopg2.extensions.connection) -> List[str]:
    """
    Get all table names in the database.
    
    Args:
        conn: PostgreSQL connection
        
    Returns:
        List of table names
    """
    query = """
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public';
    """
    df = pd.read_sql(query, conn)
    return df['table_name'].tolist()

def find_relevant_tables(query: str, tables: List[str], conn, constraints) -> List[str]:
    relevant_tables = []
    query_lower = query.lower()
    
    # 1. Exact table name match - if found, return just that table
    for table in tables:
        if table.lower() in query_lower:
            return [table]  # Return immediately if we find an exact match
    
    # 2. Column name match - only if no exact table match
    for table in tables:
        schema = get_table_schema(conn, table)
        if any(col.lower() in query_lower for col in schema['columns']):
            relevant_tables.append(table)
            relevant_tables.extend(get_related_tables(table, constraints))
    
    # 3. Fuzzy match - only if no other matches
    if not relevant_tables:
        fuzzy_matches = get_fuzzy_matched_tables(query, tables)
        relevant_tables.extend(fuzzy_matches)
    
    return list(set(relevant_tables))


def extract_conditions(query: str) -> Tuple[str, List[str]]:
    """
    Extract conditions from natural language query.
    
    Args:
        query: Natural language query
        
    Returns:
        Tuple of (base query, list of conditions)
    """
    conditions = []
    query_lower = query.lower()
    
    # Common condition patterns
    patterns = {
        'greater than': '>',
        'less than': '<',
        'equal to': '=',
        'not equal to': '!=',
        'contains': 'LIKE',
        'starts with': 'LIKE',
        'ends with': 'LIKE',
        'between': 'BETWEEN',
        'in': 'IN',
        'like': 'LIKE',
        'is null': 'IS NULL',
        'is not null': 'IS NOT NULL'
    }
    
    # Extract conditions
    for pattern, operator in patterns.items():
        if pattern in query_lower:
            # Extract the condition part
            condition_part = query_lower.split(pattern)[1].strip()
            conditions.append(f"{operator} {condition_part}")
    
    return query, conditions

def construct_query(query: str, tables: List[str], conn: psycopg2.extensions.connection, constraints: Dict[str, Dict[str, Any]]) -> str:
    """
    Construct SQL query from natural language.
    
    Args:
        query: Natural language query
        tables: List of relevant tables
        conn: PostgreSQL connection
        constraints: Table constraints dictionary
        
    Returns:
        Constructed SQL query
    """
    query_lower = query.lower()
    
    # Determine query type
    if any(word in query_lower for word in ['insert', 'add', 'create']):
        return construct_insert_query(query, tables, conn)
    elif any(word in query_lower for word in ['update', 'modify', 'change']):
        return construct_update_query(query, tables, conn)
    elif any(word in query_lower for word in ['delete', 'remove']):
        return construct_delete_query(query, tables, conn)
    else:
        return construct_select_query(query, tables, conn, constraints)

def construct_select_query(query: str, tables: List[str], conn: psycopg2.extensions.connection, constraints: Dict[str, Dict[str, Any]]) -> str:
    """Construct SELECT query."""
    base_query, conditions = extract_conditions(query)
    query_lower = query.lower()
    
    # Get all columns from relevant tables
    all_columns = []
    for table in tables:
        schema = get_table_schema(conn, table)
        all_columns.extend([f"{table}.{col}" for col in schema['columns']])
    
    # Build the query
    sql = f"SELECT {', '.join(all_columns)} FROM {tables[0]}"
    
    # Add JOINs for related tables only if we need data from them
    if len(tables) > 1:
        join_conditions = construct_join_conditions(tables, constraints)
        for i, table in enumerate(tables[1:], 1):
            sql += f" JOIN {table}"
            if join_conditions:
                # Only use join conditions that involve the current table
                current_joins = [j for j in join_conditions if table in j]
                if current_joins:
                    sql += f" ON {' AND '.join(current_joins)}"
    
    # Add conditions
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    
    # Add ordering if specified
    if 'order by' in query_lower:
        order_part = query_lower.split('order by')[1].strip()
        sql += f" ORDER BY {order_part}"
    
    # Add limit if specified
    if 'limit' in query_lower:
        limit_part = query_lower.split('limit')[1].strip()
        sql += f" LIMIT {limit_part}"
    else:
        # Check for numeric values in the query that might be limits
        import re
        numbers = re.findall(r'\b\d+\b', query)
        if numbers:
            sql += f" LIMIT {numbers[0]}"
    
    return sql

def construct_insert_query(query: str, tables: List[str], conn: psycopg2.extensions.connection) -> str:
    """Construct INSERT query."""
    # Extract values from the query
    values_match = re.search(r'values?\s+(.+?)(?:\s+where|\s+$)', query.lower())
    if values_match:
        values = values_match.group(1)
        return f"INSERT INTO {tables[0]} VALUES ({values})"
    return ""

def construct_update_query(query: str, tables: List[str], conn: psycopg2.extensions.connection) -> str:
    """Construct UPDATE query."""
    # Extract set values and conditions
    set_match = re.search(r'set\s+(.+?)(?:\s+where|\s+$)', query.lower())
    where_match = re.search(r'where\s+(.+?)$', query.lower())
    
    if set_match:
        set_values = set_match.group(1)
        where_clause = f" WHERE {where_match.group(1)}" if where_match else ""
        return f"UPDATE {tables[0]} SET {set_values}{where_clause}"
    return ""

def construct_delete_query(query: str, tables: List[str], conn: psycopg2.extensions.connection) -> str:
    """Construct DELETE query."""
    # Extract conditions
    where_match = re.search(r'where\s+(.+?)$', query.lower())
    where_clause = f" WHERE {where_match.group(1)}" if where_match else ""
    return f"DELETE FROM {tables[0]}{where_clause}"

def get_table_relationships(conn: psycopg2.extensions.connection) -> Dict[str, List[Dict[str, str]]]:
    """
    Get relationships between tables using foreign keys.
    
    Args:
        conn: PostgreSQL connection
        
    Returns:
        Dict mapping table names to their relationships
    """
    query = """
    SELECT
        tc.table_name,
        kcu.column_name,
        ccu.table_name AS foreign_table_name,
        ccu.column_name AS foreign_column_name
    FROM information_schema.table_constraints AS tc
    JOIN information_schema.key_column_usage AS kcu
        ON tc.constraint_name = kcu.constraint_name
    JOIN information_schema.constraint_column_usage AS ccu
        ON ccu.constraint_name = tc.constraint_name
    WHERE tc.constraint_type = 'FOREIGN KEY';
    """
    df = pd.read_sql(query, conn)
    
    relationships = {}
    for _, row in df.iterrows():
        table = row['table_name']
        if table not in relationships:
            relationships[table] = []
        relationships[table].append({
            'column': row['column_name'],
            'references': {
                'table': row['foreign_table_name'],
                'column': row['foreign_column_name']
            }
        })
    return relationships

def construct_join_query(tables: List[str], relationships: Dict[str, List[Dict[str, str]]]) -> str:
    """
    Construct a JOIN query based on table relationships.
    
    Args:
        tables: List of tables to join
        relationships: Table relationships dictionary
        
    Returns:
        SQL query with proper JOINs
    """
    if not tables:
        return ""
    
    # Start with the first table
    query = f"SELECT * FROM {tables[0]}"
    
    # Add JOINs for remaining tables
    for table in tables[1:]:
        # Find relationship between current table and previous tables
        for prev_table in tables[:tables.index(table)]:
            if prev_table in relationships:
                for rel in relationships[prev_table]:
                    if rel['references']['table'] == table:
                        query += f" JOIN {table} ON {prev_table}.{rel['column']} = {table}.{rel['references']['column']}"
                        break
            if table in relationships:
                for rel in relationships[table]:
                    if rel['references']['table'] == prev_table:
                        query += f" JOIN {table} ON {table}.{rel['column']} = {prev_table}.{rel['references']['column']}"
                        break
    
    return query

def extract_query_intent(query: str) -> Dict[str, Any]:
    """
    Extract intent and details from natural language query.
    
    Args:
        query: Natural language query
        
    Returns:
        Dict containing query intent and details
    """
    query_lower = query.lower()
    intent = {
        'type': 'SELECT',  # Default to SELECT
        'tables': [],
        'conditions': [],
        'limit': None,
        'order_by': None,
        'search_terms': []
    }
    
    # Extract tables
    tables = get_all_tables(None)  # We'll get actual tables later
    for table in tables:
        if table.lower() in query_lower:
            intent['tables'].append(table)
    
    # Extract search terms
    words = query_lower.split()
    for i, word in enumerate(words):
        if word in ['for', 'with', 'having'] and i + 1 < len(words):
            intent['search_terms'].append(words[i + 1])
    
    # Extract limit
    import re
    numbers = re.findall(r'\b\d+\b', query)
    if numbers:
        intent['limit'] = int(numbers[0])
    
    # Extract order by
    if 'order by' in query_lower:
        order_part = query_lower.split('order by')[1].strip()
        intent['order_by'] = order_part
    
    return intent

def construct_smart_query(intent: Dict[str, Any], relationships: Dict[str, List[Dict[str, str]]]) -> str:
    """
    Construct a smart SQL query based on intent and relationships.
    
    Args:
        intent: Query intent dictionary
        relationships: Table relationships
        
    Returns:
        SQL query
    """
    if not intent['tables']:
        return ""
    
    # Start with base query
    query = f"SELECT * FROM {intent['tables'][0]}"
    
    # Add JOINs if multiple tables
    if len(intent['tables']) > 1:
        for table in intent['tables'][1:]:
            # Find relationship between current table and previous tables
            for prev_table in intent['tables'][:intent['tables'].index(table)]:
                if prev_table in relationships:
                    for rel in relationships[prev_table]:
                        if rel['references']['table'] == table:
                            query += f" JOIN {table} ON {prev_table}.{rel['column']} = {table}.{rel['references']['column']}"
                            break
                if table in relationships:
                    for rel in relationships[table]:
                        if rel['references']['table'] == prev_table:
                            query += f" JOIN {table} ON {table}.{rel['column']} = {prev_table}.{rel['references']['column']}"
                            break
    
    # Add WHERE conditions for search terms
    if intent['search_terms']:
        conditions = []
        for term in intent['search_terms']:
            # Try to match term with product names
            conditions.append(f"products.name ILIKE '%{term}%'")
        if conditions:
            query += " WHERE " + " OR ".join(conditions)
    
    # Add ORDER BY
    if intent['order_by']:
        query += f" ORDER BY {intent['order_by']}"
    
    # Add LIMIT
    if intent['limit']:
        query += f" LIMIT {intent['limit']}"
    
    return query

def execute_sql_query(query: str) -> Dict[str, Any]:
    """
    Execute a SQL query and return the results.
    
    Args:
        query (str): SQL query to execute
        
    Returns:
        Dict[str, Any]: Query results or error message
    """
    try:
        conn = get_db_connection()
        
        # If query is a natural language query, process it
        if not query.strip().upper().startswith(('SELECT', 'INSERT', 'UPDATE', 'DELETE')):
            # Extract query intent
            intent = extract_query_intent(query)
            
            # Get table relationships
            relationships = get_table_relationships(conn)
            
            # Construct smart query
            query = construct_smart_query(intent, relationships)
        
        cursor = conn.cursor()
        cursor.execute(query)
        
        if cursor.description:
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            
            def serialize_value(val):
                if isinstance(val, (datetime, pd.Timestamp)):
                    return val.isoformat()
                if isinstance(val, Decimal):
                    return float(val)
                return val
            
            result = [
                {col: serialize_value(val) for col, val in zip(columns, row)}
                for row in rows
            ]
            
            return {"success": True, "data": result}
        else:
            return {"success": True, "data": []}
            
    except Exception as e:
        return {"success": False, "error": f"PostgreSQL query failed: {str(e)}"}
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def get_db_connection() -> psycopg2.extensions.connection:
    """
    Get a PostgreSQL database connection using environment variables.
    
    Returns:
        PostgreSQL connection object
    """
    # Get connection parameters from environment variables
    db_params = {
        'dbname': os.getenv('POSTGRES_DB'),
        'user': os.getenv('POSTGRES_USER'),
        'password': os.getenv('POSTGRES_PASSWORD'),
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': os.getenv('POSTGRES_PORT', '5432')
    }

    # Check if required parameters are present
    if not all([db_params['dbname'], db_params['user'], db_params['password']]):
        raise ValueError("Missing required PostgreSQL connection parameters in environment variables")

    # Connect to PostgreSQL
    return psycopg2.connect(**db_params)

root_agent = Agent(
    model='gemini-2.0-flash-001',
    name='sql_agent',
    description='An intelligent PostgreSQL agent that can understand natural language queries and execute SQL commands',
    instruction="""I am an intelligent PostgreSQL agent that can:
1. Execute SQL queries and return the results
2. Understand natural language queries and convert them to SQL
3. Automatically identify relevant tables and columns
4. Process query results in a structured format
5. Handle various types of SQL queries (SELECT, INSERT, UPDATE, DELETE)
6. Provide helpful error messages if queries fail
7. Automatically handle table relationships and foreign keys

I can understand queries in both natural language and SQL:
- Natural language: "Show me all users" (I'll identify the users table and its columns)
- Natural language: "What are the top 5 products by sales?" (I'll identify relevant tables and construct the query with proper joins)
- Natural language: "Add a new user with name John and email john@example.com"
- Natural language: "Update the price of product with ID 123 to $99.99"
- Natural language: "Remove all inactive users"
- SQL: "SELECT * FROM users WHERE age > 25"

I automatically:
- Identify the most relevant tables if not specified
- Include all relevant columns in the results
- Handle table relationships and foreign keys
- Construct proper JOIN conditions based on foreign key relationships
- Format the results in a clear, structured way
- Construct appropriate queries based on the intent

Example usage:
User: Show me all users with their orders
Agent: [Identifies users and orders tables, uses foreign key relationship to join them]

User: What are the top 5 products by sales?
Agent: [Identifies products and sales tables, constructs the query with proper joins and ordering]

User: Add a new customer with name Alice and email alice@example.com
Agent: [Identifies the customers table and constructs an INSERT query]

User: Update the status of order #123 to 'shipped'
Agent: [Identifies the orders table and constructs an UPDATE query]

User: Delete all expired sessions
Agent: [Identifies the sessions table and constructs a DELETE query with proper conditions]""",
    tools=[execute_sql_query]
)
