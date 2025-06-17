"""A MS SQL Server agent that can execute queries and retrieve data."""
import pyodbc
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
from google.generativeai import GenerativeModel
import google.generativeai as genai


# Load environment variables
load_dotenv()

# Initialize Gemini
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = GenerativeModel('gemini-pro')

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (Timestamp, datetime)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

def get_table_constraints(conn: pyodbc.Connection) -> Dict[str, Dict[str, Any]]:
    """
    Get primary key and foreign key constraints for all tables.
    
    Args:
        conn: MS SQL Server connection
        
    Returns:
        Dict containing table constraints
    """
    # Get primary keys
    pk_query = """
    SELECT 
        OBJECT_NAME(t.object_id) AS table_name,
        c.name AS column_name
    FROM sys.tables t
    INNER JOIN sys.indexes i ON t.object_id = i.object_id
    INNER JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
    INNER JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
    WHERE i.is_primary_key = 1
    ORDER BY OBJECT_NAME(t.object_id), ic.key_ordinal;
    """
    
    # Get foreign keys
    fk_query = """
    SELECT 
        OBJECT_NAME(fk.parent_object_id) AS table_name,
        COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS column_name,
        OBJECT_NAME(fk.referenced_object_id) AS foreign_table_name,
        COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS foreign_column_name
    FROM sys.foreign_keys fk
    INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    ORDER BY OBJECT_NAME(fk.parent_object_id);
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

def get_table_schema(conn: pyodbc.Connection, table_name: str) -> Dict[str, List[str]]:
    """
    Get the schema information for a table.
    
    Args:
        conn: MS SQL Server connection
        table_name: Name of the table
        
    Returns:
        Dict containing column names and their data types
    """
    query = """
    SELECT 
        c.name AS column_name,
        t.name AS data_type,
        c.is_nullable,
        CASE 
            WHEN t.name IN ('varchar', 'nvarchar', 'char', 'nchar') 
            THEN CAST(c.max_length AS VARCHAR) 
            ELSE NULL 
        END AS max_length,
        CASE 
            WHEN t.name IN ('decimal', 'numeric') 
            THEN CAST(c.precision AS VARCHAR) + ',' + CAST(c.scale AS VARCHAR)
            ELSE NULL 
        END AS precision_scale
    FROM sys.columns c
    INNER JOIN sys.types t ON c.user_type_id = t.user_type_id
    WHERE c.object_id = OBJECT_ID(?)
    ORDER BY c.column_id;
    """
    df = pd.read_sql(query, conn, params=(table_name,))
    return {
        'columns': df['column_name'].tolist(),
        'types': df['data_type'].tolist(),
        'nullable': df['is_nullable'].tolist(),
        'max_length': df['max_length'].tolist(),
        'precision_scale': df['precision_scale'].tolist()
    }

def get_all_tables(conn: pyodbc.Connection) -> List[str]:
    """
    Get all table names in the database.
    
    Args:
        conn: MS SQL Server connection
        
    Returns:
        List of table names
    """
    query = """
    SELECT TABLE_NAME 
    FROM INFORMATION_SCHEMA.TABLES 
    WHERE TABLE_TYPE = 'BASE TABLE'
    ORDER BY TABLE_NAME;
    """
    df = pd.read_sql(query, conn)
    return df['TABLE_NAME'].tolist()

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

def construct_query(query: str, tables: List[str], conn: pyodbc.Connection, constraints: Dict[str, Dict[str, Any]]) -> str:
    """
    Construct SQL query from natural language.
    
    Args:
        query: Natural language query
        tables: List of relevant tables
        conn: MS SQL Server connection
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

def construct_select_query(query: str, tables: List[str], conn: pyodbc.Connection, constraints: Dict[str, Dict[str, Any]]) -> str:
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

def construct_insert_query(query: str, tables: List[str], conn: pyodbc.Connection) -> str:
    """Construct INSERT query."""
    # Extract values from the query
    values_match = re.search(r'values?\s+(.+?)(?:\s+where|\s+$)', query.lower())
    if values_match:
        values = values_match.group(1)
        return f"INSERT INTO {tables[0]} VALUES ({values})"
    return ""

def construct_update_query(query: str, tables: List[str], conn: pyodbc.Connection) -> str:
    """Construct UPDATE query."""
    # Extract set values and conditions
    set_match = re.search(r'set\s+(.+?)(?:\s+where|\s+$)', query.lower())
    where_match = re.search(r'where\s+(.+?)$', query.lower())
    
    if set_match:
        set_values = set_match.group(1)
        where_clause = f" WHERE {where_match.group(1)}" if where_match else ""
        return f"UPDATE {tables[0]} SET {set_values}{where_clause}"
    return ""

def construct_delete_query(query: str, tables: List[str], conn: pyodbc.Connection) -> str:
    """Construct DELETE query."""
    # Extract conditions
    where_match = re.search(r'where\s+(.+?)$', query.lower())
    where_clause = f" WHERE {where_match.group(1)}" if where_match else ""
    return f"DELETE FROM {tables[0]}{where_clause}"

def get_table_relationships(conn: pyodbc.Connection) -> Dict[str, List[Dict[str, str]]]:
    """
    Get relationships between tables using foreign keys.
    
    Args:
        conn: MS SQL Server connection
        
    Returns:
        Dict containing table relationships
    """
    query = """
    SELECT 
        OBJECT_NAME(fk.parent_object_id) AS table_name,
        COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS column_name,
        OBJECT_NAME(fk.referenced_object_id) AS referenced_table,
        COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS referenced_column
    FROM sys.foreign_keys fk
    INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    ORDER BY OBJECT_NAME(fk.parent_object_id);
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
                'table': row['referenced_table'],
                'column': row['referenced_column']
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

def get_schema_info(conn: pyodbc.Connection) -> str:
    """
    Get database schema information in a format suitable for LLM.
    """
    tables = get_all_tables(conn)
    schema_info = []
    
    # First, get all relationships
    relationships = get_table_relationships(conn)
    
    # Then build schema info with relationships
    for table in tables:
        schema = get_table_schema(conn, table)
        table_info = f"Table: {table}\n"
        table_info += "Columns:\n"
        for col, type_ in zip(schema['columns'], schema['types']):
            table_info += f"- {col} ({type_})\n"
        
        # Add relationship information
        if table in relationships:
            table_info += "Relationships:\n"
            for rel in relationships[table]:
                table_info += f"- {rel['column']} -> {rel['references']['table']}.{rel['references']['column']}\n"
        
        # Add sample data for better understanding
        try:
            sample_query = f"SELECT * FROM {table} LIMIT 1"
            sample_df = pd.read_sql(sample_query, conn)
            if not sample_df.empty:
                table_info += "Sample Data:\n"
                for col in sample_df.columns:
                    table_info += f"- {col}: {sample_df[col].iloc[0]}\n"
        except:
            pass
        
        schema_info.append(table_info)
    
    return "\n".join(schema_info)

def construct_query_with_llm(natural_query: str, schema_info: str) -> str:
    """
    Use LLM to construct SQL query from natural language.
    """
    prompt = f"""You are a SQL expert. Given the following database schema and relationships:

{schema_info}

Convert this natural language query to SQL:
"{natural_query}"

Important rules:
1. Analyze the query to determine the main table(s) to query
2. Use proper JOINs based on the relationships shown in the schema
3. For any query:
   - Start with the most relevant table(s)
   - Join with related tables using the relationships shown
   - Use appropriate WHERE conditions based on the query intent
   - Use ILIKE for case-insensitive text matching
   - Include any specified limits or ordering
4. Be valid SQL syntax

Example queries:
1. "show me 2 products":
   SELECT * FROM products LIMIT 2

2. "coupons for Macbook":
   SELECT c.* 
   FROM coupons c
   JOIN product_coupons pc ON c.coupon_id = pc.coupon_id
   JOIN products p ON pc.product_id = p.product_id
   WHERE p.name ILIKE '%Macbook%'

3. "orders with Macbook products":
   SELECT o.* 
   FROM orders o
   JOIN products p ON o.product_id = p.product_id
   WHERE p.name ILIKE '%Macbook%'

Return ONLY the SQL query without any explanation.

SQL Query:"""

    response = model.generate_content(prompt)
    return response.text.strip()

def execute_sql_query(query: str) -> Dict[str, Any]:
    """
    Execute SQL query and return results.
    """
    try:
        # Get database connection
        conn = get_db_connection()
        
        # Check if this is a natural language query or a non-SELECT SQL query
        if not query.strip().upper().startswith('SELECT'):
            # If it's a natural language query, try to convert it to SELECT
            if not query.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER')):
                # Get schema information for LLM
                schema_info = get_schema_info(conn)
                # Use LLM to construct SQL query
                query = construct_query_with_llm(query, schema_info)
                print(f"Generated SQL query: {query}")  # Debug print
            else:
                return {
                    "status": "error",
                    "message": "I am only able to fetch data (SELECT queries) and cannot perform operations that modify, delete, or create data (such as INSERT, UPDATE, DELETE, CREATE, DROP, or ALTER queries). Please rephrase your query to ask for information only."
                }

        # If after conversion it's still not a SELECT query, prevent execution
        if not query.strip().upper().startswith('SELECT'):
            return {
                "status": "error",
                "message": "I am only able to fetch data (SELECT queries) and cannot perform operations that modify, delete, or create data. Please rephrase your query to ask for information only."
            }

        # Execute query
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
            
            return {
                "status": "success",
                "data": result,
                "row_count": len(result)
            }
        else:
            return {
                "status": "success",
                "data": [],
                "row_count": 0
            }
    except Exception as e:
        # Log the error for debugging but return a user-friendly message
        print(f"Error executing query: {str(e)}")  # Debug print
        return {
            "status": "error",
            "message": "I couldn't process that query. Could you please rephrase it?"
        }
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def get_db_connection() -> pyodbc.Connection:
    """Get a connection to the MS SQL Server database using environment variables."""

    server = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "1433")
    database = os.getenv("DB_NAME", "master")
    username = os.getenv("DB_USER", "sa")
    password = os.getenv("DB_PASSWORD", "YourStrong@Passw0rd")

    conn_str = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={server},{port};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        "TrustServerCertificate=yes;"
    )

    return pyodbc.connect(conn_str)

root_agent = Agent(
    model='gemini-2.0-flash-001',
    name='sql_agent',
    description='An intelligent MS SQL Server agent that can understand natural language queries and execute SQL commands on a database with various tables including retailers, stores, and product information.',
    instruction="""I am an intelligent MS SQL Server agent that can:
1. Execute SQL queries and return the results as structured data.
2. Understand natural language queries and accurately convert them into SQL `SELECT` statements.
3. Automatically identify relevant tables and columns from the provided database schema.
4. Process query results in a clear, structured format (JSON or similar).
5. Provide helpful error messages if queries fail or if a non-`SELECT` query is attempted.
6. Automatically handle table relationships and foreign keys to perform necessary `JOIN` operations.
7. **I will strictly perform `SELECT` operations to fetch data only. I will NEVER execute any operations related to `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP`, or `ALTER` data or tables.**
8. My final response to the user will always be the fetched data, not the SQL query.
9. **I will present the data in a human-understandable format, not as raw JSON.**
10. **I will hide sensitive information such as IDs, passwords, and personal data in the responses.**
11. **I can perform semantic or similarity searches to find relevant data, such as food-related coupons, by analyzing the context and keywords in the query.**

Available Tables and their key columns:
- `retailers`: `retailer_id`, `retailer_name`, `status`, `login_url`, `share_store_data`, `retailer_group_id`, `admin_login_id`, `client_retailer_id`, `retailer_key`, `mode`, `app_group_id`, `is_promotion_pod`, `icn_primary_ip`, `icn_primary_port`, `icn_secondary_ip`, `icn_secondary_port`, `logo`, `is_ICN_mode`, `twilio_from_number`, `twilio_sub_account_sid`, `share_qrcode_url`, `is_TCB_mode`, `tcb_retailer_email_domain`, `sms_credits`, `twilio_verify_service_id`, `data_source`, `tcb_internal_id`, `tcb_store_locator_url`
- `stores`: `store_id`, `retailer_id`, `store_name`, `status`, `store_number`, `time_zone`, `tlog_identifier`, `city_id`, `zip_code`, `latitude`, `longitude`, `weather_zip_code`, `address`, `store_key`, `icn_store_number`, `prefix_barcode`, `data_source`, `point_amount`, `is_cachelao_mode`, `points_redemption_criteria`
- `store_upc_master`: `retailer_id`, `store_id`, `upc`, `item_name`, `size`, `mfg_id`, `dept_id`, `category_id`, `upc_store`, `with_checkdigit`, `item_name_store`, `size_store`, `category_store`, `manufacturer_store`, `brand_store`
- `upc_master`: `id`, `retailer_id`, `upc_code`, `item_name`, `dept_id`, `size`, `major_category_id`, `sub_category_id`, `min_category_id`, `upc_length`, `upc_map_id`, `category_id`
- `coupons`: `coupon_id`, `coupon_title`, `provider_type`, `provider_id`, `provider_name`, `start_date`, `image_path`, `terms`, `coupon_status`, `creation_timestamp`, `max_redeem_quantity`, `redeem_block_days`, `coupon_group_id`, `icn_coupon`, `store_id`, `display_status`, `tcb_gs1` (coupon code/usable coupon), `mfg_id`, `brand_id`
- Other tables include: `app_group`, `brand_master`, `brands`, `category_master`, `circular`, `circular_images`, `city_master`, `country_master`, `coupon_app_group_map`, `coupon_brand_master`, `coupon_categories`, `coupon_discount`, `coupon_discount_type`, `coupon_expiration`, `coupon_expiration_type`, `coupon_group`, `coupon_manufacturer_master`, `coupon_products`, `custom_category`, `custom_category_items`, `custom_salesarea`, `customer_app_group_map`, `customer_app_support`, `customer_clipped_coupon`, `customer_papercoupon_coupon_redeem_history`, `customer_redeem_history`, `customers`, `dashboard_users`, `distributor_brand_map`, `distributors`, `dma_child`, `dma_master`, `emilio_customer_support`, `emilio_fetch_code_coupon_map`, `emilio_fetch_codes`, `export`, `filter_upc`, `items`, `log`, `logger`, `login`, `login_datasource_map`, `login_domain_map`, `loyalty_retailer_rules`, `loyalty_settings`, `loyalty_settings_bk`, `loyalty_templates`, `manufacturer_master`, `map_details`, `menu_login_map`, `menu_master`, `missing_coupon_discount`, `missing_coupon_expiration`, `missing_coupon_products`, `missing_coupons`, `ml_upc`, `notification`, `notification_config`, `pos_basket`, `pos_coupons`, `pos_process_coupon`, `pos_session`, `pos_version`, `push_notification_campaigns`, `push_notification_topics`, `region_master`, `retailer_group`, `retailer_rules`, `retailers_test`, `retailers_test1`, `sms_campaigns`, `sms_response`, `state_master`, `store_departments_master`, `store_info`, `sub_brands`, `tcb_webhook`, `temp_icn_customer_coupon`, `temp_retailer_upc`, `temp_store_departments_master`, `temp_upc_details`, `templates`, `test_coupon_app_group_map`, `test_coupon_discount`, `test_coupon_expiration`, `test_coupon_products`, `test_coupons`, `transactions`, `transactions_csv`, `transactions_csv_child`, `upc_brand_map`, `upc_details`, `users_test`, `weather_data`

I can understand queries in both natural language and SQL:
- Natural language: "Show me all retailers" (e.g., provide a list of retailer names and IDs)
- Natural language: "What are the names of stores for retailer with id 123?" (I will use the `retailer_id` to join `retailers` and `stores` tables, and return store names and their IDs for retailer 123).
- Natural language: "Find items in store_upc_master with item name 'Macbook'" (e.g., return item details like UPC, size, and item name).
- Natural language: "Show me all active coupons" (e.g., return coupon titles, descriptions, provider names, and coupon codes for active coupons).
- Natural language: "Find coupons with a start date after 2023-01-01" (e.g., return coupon titles, descriptions, provider names, and coupon codes for coupons starting after the specified date).
- SQL: "SELECT * FROM retailers WHERE status = 'active'" (returns all data from the `retailers` table where the status is 'active').

I automatically:
- **Always utilize the `execute_sql_query` tool to retrieve data from the database.**
- Identify the most relevant tables if not specified.
- Include all relevant columns in the results or specific columns if requested.
- **I will always display human-friendly names for columns, instead of exposing raw column names from the database. For `tcb_gs1`, I will display it as 'Coupon Code'.**
- Handle table relationships and foreign keys (e.g., `retailer_id`, `store_id`).
- Construct proper JOIN conditions based on foreign key relationships.
- Format the results as structured data (e.g., JSON list of dictionaries).
- Construct appropriate `SELECT` queries based on the intent.

Example usage:
User: Show me all stores for the 'Best Buy' retailer.
Agent: Here are the stores for Best Buy:
- Store Name: Best Buy NYC
- Store Name: Best Buy LA

User: List all products and their UPC codes from the `upc_master` table.
Agent: Here are the products and their UPC codes:
- Product Name: Laptop, UPC: 12345
- Product Name: Monitor, UPC: 67890

User: Get the `item_name` and `store_id` for all items in `store_upc_master` where `retailer_id` is 1.
Agent: Here are the items for Retailer ID 1:
- Item Name: Item A, Store ID: 101
- Item Name: Item B, Store ID: 102

User: What is the `login_url` for the retailer with `retailer_id` 1?
Agent: The Login URL for Retailer ID 1 is: https://login.example.com

User: Show me the `store_name` and `address` for all stores in `city_id` 'NYC'
Agent: Here are the stores in NYC:
- Store Name: Store A, Address: 123 Main St

User: Show me all coupons that are active.
Agent: Here are the active coupons:
- Title: Summer Sale, Description: Enjoy 20% off on all summer items., Provider: Example Provider A, Coupon Code: XXXX-YYYY-ZZZZ
- Title: Holiday Discount, Description: Get 15% off on holiday specials., Provider: Example Provider B, Coupon Code: AAAA-BBBB-CCCC

User: Find coupons by `coupon_title` that contain 'Discount'
Agent: Here are the coupons with 'Discount' in the title:
- Title: Holiday Discount, Description: Get 15% off on holiday specials., Provider: Example Provider B, Coupon Code: AAAA-BBBB-CCCC

User: Get food-related coupons.
Agent: Here are the food-related coupons:
- Title: Food Festival, Description: Enjoy 25% off on all food items., Provider: Example Provider C, Coupon Code: DDDD-EEEE-FFFF
- Title: Grocery Sale, Description: Get 10% off on grocery items., Provider: Example Provider D, Coupon Code: GGGG-HHHH-IIII""",
    tools=[execute_sql_query]
)
