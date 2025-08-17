#!/usr/bin/env python3
"""
Database MCP Server with Text-to-SQL Conversion
Handles database queries, searches, and data operations
"""

import json
import sys
import argparse
import sqlite3
import anthropic
from typing import Optional, Dict, List, Any
from datetime import datetime
import uuid
import smtplib
from email.mime.text import MIMEText


# FastAPI imports
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, HTMLResponse

# MCP imports
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport

def debug_print(message):
    """Debug print to stderr"""
    print(f"[DB-SERVER] {message}", file=sys.stderr, flush=True)

debug_print("Starting Database MCP Server with Text-to-SQL...")

# ================================
# Database Schema & Setup
# ================================

# Database schema for text-to-SQL conversion
DATABASE_SCHEMA = {
    "claims": {
        "table_description": "Brazil claims data for warranty and service claims",
        "columns": {
            "claim_id": "VARCHAR(50) PRIMARY KEY - Unique claim identifier (e.g., '1-ABCD')",
            "claim_number": "VARCHAR(50) - Human readable claim number",
            "customer_name": "VARCHAR(100) - Customer name",
            "product_serial": "VARCHAR(50) - Product serial number", 
            "claim_date": "DATE - Date claim was filed",
            "claim_type": "VARCHAR(50) - Type of claim (warranty, service, etc.)",
            "status": "VARCHAR(20) - Claim status (open, closed, pending)",
            "region": "VARCHAR(50) - Geographic region (Brazil, US, etc.)",
            "amount": "DECIMAL(10,2) - Claim amount in USD",
            "description": "TEXT - Detailed claim description"
        },
        "sample_queries": [
            "Find claim number 1-ABCD",
            "Show all Brazil claims from last month",
            "Get pending warranty claims"
        ]
    },
    "engines": {
        "table_description": "Engine master data with specifications and attributes",
        "columns": {
            "engine_id": "VARCHAR(50) PRIMARY KEY - Unique engine identifier",
            "serial_number": "VARCHAR(50) UNIQUE - Engine serial number (e.g., '12345678')",
            "model_name": "VARCHAR(50) - Engine model (e.g., 'X10', 'X15')",
            "engine_family": "VARCHAR(50) - Engine family grouping",
            "displacement": "DECIMAL(5,2) - Engine displacement in liters",
            "power_rating": "INTEGER - Power rating in HP",
            "manufacture_date": "DATE - Date engine was manufactured", 
            "status": "VARCHAR(20) - Engine status (active, retired, etc.)",
            "location": "VARCHAR(100) - Current engine location",
            "last_updated": "TIMESTAMP - Last modification timestamp"
        },
        "sample_queries": [
            "Find engine with serial number 12345678",
            "Update engine model from X10 to X15",
            "Show all X10 model engines"
        ]
    },
    "warranty": {
        "table_description": "Warranty records and coverage information",
        "columns": {
            "warranty_id": "VARCHAR(50) PRIMARY KEY - Unique warranty identifier",
            "product_serial": "VARCHAR(50) - Product serial number",
            "warranty_type": "VARCHAR(50) - Type of warranty coverage",
            "start_date": "DATE - Warranty start date",
            "end_date": "DATE - Warranty expiration date",
            "coverage_amount": "DECIMAL(10,2) - Maximum coverage amount",
            "status": "VARCHAR(20) - Warranty status (active, expired, claimed)",
            "terms": "TEXT - Warranty terms and conditions"
        },
        "sample_queries": [
            "Check warranty for serial number ABC123",
            "Find expired warranties",
            "Get active warranty coverage"
        ]
    }
}

# Pending approval requests storage
PENDING_APPROVALS = {}

# Initialize SQLite database
def init_database():
    """Initialize SQLite database with sample data"""
    
    conn = sqlite3.connect('enterprise.db')
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS claims (
            claim_id VARCHAR(50) PRIMARY KEY,
            claim_number VARCHAR(50),
            customer_name VARCHAR(100),
            product_serial VARCHAR(50),
            claim_date DATE,
            claim_type VARCHAR(50),
            status VARCHAR(20),
            region VARCHAR(50),
            amount DECIMAL(10,2),
            description TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS engines (
            engine_id VARCHAR(50) PRIMARY KEY,
            serial_number VARCHAR(50) UNIQUE,
            model_name VARCHAR(50),
            engine_family VARCHAR(50),
            displacement DECIMAL(5,2),
            power_rating INTEGER,
            manufacture_date DATE,
            status VARCHAR(20),
            location VARCHAR(100),
            last_updated TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS warranty (
            warranty_id VARCHAR(50) PRIMARY KEY,
            product_serial VARCHAR(50),
            warranty_type VARCHAR(50),
            start_date DATE,
            end_date DATE,
            coverage_amount DECIMAL(10,2),
            status VARCHAR(20),
            terms TEXT
        )
    ''')
    
    # Insert sample data
    sample_claims = [
        ("1-AAAA", "1-AAAA", "John Silva", "ENG001", "2024-01-15", "warranty", "closed", "Brazil", 1500.00, "Engine overheating issue"),
        ("1-BBBB", "1-BBBB", "Maria Santos", "ENG002", "2024-02-20", "service", "open", "Brazil", 800.00, "Fuel system malfunction"),
        ("1-CCCC", "1-CCCC", "Carlos Lima", "ENG003", "2024-03-10", "warranty", "pending", "Brazil", 2200.00, "Transmission failure")
    ]
    
    sample_engines = [
        ("ENG001", "12345678", "X10", "ISX", 15.0, 600, "2023-06-15", "active", "Brazil Plant", "2024-01-01 00:00:00"),
        ("ENG002", "12345679", "X15", "ISX", 15.0, 650, "2023-07-20", "active", "US Plant", "2024-01-01 00:00:00"),
        ("ENG003", "12345680", "X10", "ISX", 12.0, 500, "2023-08-25", "active", "Brazil Plant", "2024-01-01 00:00:00")
    ]
    
    sample_warranty = [
        ("W001", "ENG001", "Extended", "2023-06-15", "2025-06-15", 5000.00, "active", "2 year extended warranty"),
        ("W002", "ENG002", "Standard", "2023-07-20", "2024-07-20", 3000.00, "expired", "1 year standard warranty"),
        ("W003", "ENG003", "Extended", "2023-08-25", "2025-08-25", 5000.00, "active", "2 year extended warranty")
    ]
    
    # Insert if not exists
    cursor.execute("SELECT COUNT(*) FROM claims")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO claims VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", sample_claims)
    
    cursor.execute("SELECT COUNT(*) FROM engines")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO engines VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", sample_engines)
    
    cursor.execute("SELECT COUNT(*) FROM warranty")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO warranty VALUES (?, ?, ?, ?, ?, ?, ?, ?)", sample_warranty)
    
    conn.commit()
    conn.close()
    
    debug_print("Database initialized with sample data")

# Initialize database on startup
init_database()

# ================================
# MCP Server Setup
# ================================

mcp_server = FastMCP("Database Query MCP Server")

# Claude API client for text-to-SQL
CLAUDE_API_KEY ="******"  # Replace with your key
claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY) if CLAUDE_API_KEY != "your-claude-api-key" else None

#!/usr/bin/env python3
"""
Claude-Only Text-to-SQL Conversion with Enhanced Prompting
Focuses on using Claude exclusively for better natural language understanding
"""

import json
from typing import Dict, Any

def text_to_sql(user_query: str, table_hint: str = None, claude_client=None) -> Dict[str, Any]:
    """
    Claude-based text-to-SQL conversion with enhanced prompting
    """
    
    if not claude_client:
        return {
            "sql": "SELECT 'Claude API key not configured' as error_message",
            "explanation": "Claude API client not available",
            "confidence": 0.0,
            "error": "Claude API key required for text-to-SQL conversion"
        }
    
    # Enhanced database schema context
    schema_context = """DATABASE SCHEMA:

Table: claims (Brazil claims data for warranty and service claims)
Columns:
- claim_id: VARCHAR(50) PRIMARY KEY - Unique claim identifier
- claim_number: VARCHAR(50) - Human readable claim number (format: '1-ABCD', '2-EFGH')
- customer_name: VARCHAR(100) - Customer full name (e.g., 'Carlos Lima', 'Maria Santos')
- product_serial: VARCHAR(50) - Product serial number
- claim_date: DATE - Date claim was filed
- claim_type: VARCHAR(50) - warranty, service, etc.
- status: VARCHAR(20) - open, closed, pending
- region: VARCHAR(50) - Brazil, US, etc.
- amount: DECIMAL(10,2) - Claim amount in USD
- description: TEXT - Detailed claim description

Table: engines (Engine master data with specifications)
Columns:
- engine_id: VARCHAR(50) PRIMARY KEY - Unique engine identifier
- serial_number: VARCHAR(50) UNIQUE - Engine serial (8+ digits like '12345678')
- model_name: VARCHAR(50) - Engine model (X10, X15, etc.)
- engine_family: VARCHAR(50) - Engine family grouping
- displacement: DECIMAL(5,2) - Engine displacement in liters
- power_rating: INTEGER - Power rating in HP
- manufacture_date: DATE - Manufacturing date
- status: VARCHAR(20) - active, retired, etc.
- location: VARCHAR(100) - Current location
- last_updated: TIMESTAMP - Last modification time

Table: warranty (Warranty records and coverage)
Columns:
- warranty_id: VARCHAR(50) PRIMARY KEY
- product_serial: VARCHAR(50) - Product serial number
- warranty_type: VARCHAR(50) - Standard, Extended, etc.
- start_date: DATE - Warranty start
- end_date: DATE - Warranty expiration
- coverage_amount: DECIMAL(10,2) - Max coverage
- status: VARCHAR(20) - active, expired, claimed
- terms: TEXT - Warranty terms"""

    # Enhanced prompt with better examples and instructions
    enhanced_prompt = f"""You are an expert SQL query generator for an enterprise database system. Convert natural language queries to precise SQL statements.

{schema_context}

USER QUERY: "{user_query}"
Table hint: {table_hint or "Auto-detect based on query content"}

CRITICAL PARSING INSTRUCTIONS:
1. **Person Names**: Extract full names (e.g., "Carlos Lima" → search customer_name)
2. **Claim Numbers**: Pattern like "1-ABCD", "2-EFGH" → search claim_number  
3. **Serial Numbers**: 8+ digit numbers → search serial_number
4. **Model Names**: X10, X15, etc. → search model_name
5. **Remove Conversational Words**: Ignore "Can you", "Please", "Get me", etc.

QUERY UNDERSTANDING EXAMPLES:
❌ BAD: "Can u get Carlos Lima Claim Number" → searching for literal string "Can u get Carlos Lima Claim Number"
✅ GOOD: Extract "Carlos Lima" → SELECT * FROM claims WHERE LOWER(customer_name) LIKE LOWER('%Carlos Lima%')

❌ BAD: "Find claim for John" → vague, needs clarification
✅ GOOD: Extract "John" → SELECT * FROM claims WHERE LOWER(customer_name) LIKE LOWER('%John%')

❌ BAD: Generic SELECT * FROM claims without WHERE clause
✅ GOOD: Always include specific WHERE conditions based on extracted entities

SQL GENERATION RULES:
1. **SQLite Syntax**: Use proper SQLite functions and syntax
2. **Always Limit**: Include LIMIT 10 to prevent large result sets
3. **Case Insensitive**: Use LOWER() for text comparisons
4. **Partial Matching**: Use LIKE with % wildcards for name/text searches
5. **Exact Matching**: Use = for IDs and serial numbers when exact match intended
6. **Multiple Conditions**: Use OR for broader searches, AND for specific filters
7. **Order Results**: Add appropriate ORDER BY (recent first for dates)

SPECIFIC EXAMPLES:
Query: "Can u get Carlos Lima Claim Number"
Analysis: Extract customer name "Carlos Lima"
SQL: SELECT * FROM claims WHERE LOWER(customer_name) LIKE LOWER('%Carlos Lima%') ORDER BY claim_date DESC LIMIT 10

Query: "Find claim 1-ABCD"  
Analysis: Extract claim number "1-ABCD"
SQL: SELECT * FROM claims WHERE claim_number = '1-ABCD' OR claim_id = '1-ABCD' LIMIT 10

Query: "Show engine with serial 12345678"
Analysis: Extract serial number "12345678"
SQL: SELECT * FROM engines WHERE serial_number = '12345678' LIMIT 10

Query: "Get all X10 engines"
Analysis: Extract model name "X10"
SQL: SELECT * FROM engines WHERE LOWER(model_name) = LOWER('X10') ORDER BY last_updated DESC LIMIT 10

RETURN FORMAT - Valid JSON only:
{{
    "sql": "Complete SELECT statement with WHERE clause",
    "explanation": "Clear explanation of what the query searches for",
    "tables_used": ["primary_table"],
    "confidence": 0.85,
    "extracted_entities": {{
        "customer_name": "Carlos Lima",
        "claim_number": null,
        "serial_number": null,
        "model_name": null
    }},
    "query_type": "customer_search"
}}

Generate the SQL query now:"""

    try:
        response = claude_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1000,
            temperature=0.1,
            messages=[{"role": "user", "content": enhanced_prompt}]
        )
        
        # Extract and clean the response
        result_text = response.content[0].text.strip()
        
        # Handle potential markdown code blocks
        if result_text.startswith("```json"):
            result_text = result_text.replace("```json", "").replace("```", "").strip()
        elif result_text.startswith("```"):
            result_text = result_text.replace("```", "").strip()
        
        # Parse JSON response
        result = json.loads(result_text)
        
        # Validate the result has required fields
        if not result.get("sql"):
            return {
                "sql": "SELECT 'Error: No SQL generated' as error_message",
                "explanation": "Claude did not generate valid SQL",
                "confidence": 0.0,
                "error": "Invalid response from Claude"
            }
        
        # Ensure confidence is set
        if "confidence" not in result:
            result["confidence"] = 0.7
        
        return result
        
    except json.JSONDecodeError as e:
        return {
            "sql": "SELECT 'JSON parsing error' as error_message",
            "explanation": f"Could not parse Claude response as JSON: {str(e)}",
            "confidence": 0.0,
            "error": f"JSON parsing failed: {str(e)}",
            "claude_response": result_text if 'result_text' in locals() else "No response"
        }
        
    except Exception as e:
        return {
            "sql": "SELECT 'Claude API error' as error_message",
            "explanation": f"Claude API call failed: {str(e)}",
            "confidence": 0.0,
            "error": f"Claude API error: {str(e)}"
        }



@mcp_server.tool()
async def search_database(
    query: str,
    table_hint: Optional[str] = None
) -> str:
    """
    Search database using natural language query converted to SQL
    
    Args:
        query: Natural language search query
        table_hint: Optional hint about which table to search (claims, engines, warranty)
        
    Returns:
        JSON string with search results
    """
    
    debug_print(f"Searching database: {query}")
    
    try:
        # Convert text to SQL - FIXED: Pass claude_client parameter
        sql_result = text_to_sql(query, table_hint, claude_client)
        sql_query = sql_result["sql"]
        
        debug_print(f"Generated SQL: {sql_query}")
        
        # Execute SQL
        conn = sqlite3.connect('enterprise.db')
        conn.row_factory = sqlite3.Row  # Enable column access by name
        cursor = conn.cursor()
        
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        
        # Convert to list of dictionaries
        results = [dict(row) for row in rows]
        
        conn.close()
        
        return json.dumps({
            "success": True,
            "query": query,
            "sql_generated": sql_query,
            "sql_explanation": sql_result["explanation"],
            "confidence": sql_result["confidence"],
            "results_count": len(results),
            "results": results,
            "tables_searched": sql_result.get("tables_used", [])
        }, indent=2, default=str)
        
    except Exception as e:
        debug_print(f"Database search error: {e}")
        return json.dumps({
            "success": False,
            "error": f"Database search failed: {str(e)}",
            "query": query
        }, indent=2)

@mcp_server.tool()
async def update_engine_attribute(
    serial_number: str,
    attribute: str,
    new_value: str,
    user_id: str,
    justification: str = "User requested update"
) -> str:
    """
    Request to update engine attribute - requires approval for sensitive changes
    
    Args:
        serial_number: Engine serial number to update
        attribute: Attribute to change (model_name, power_rating, etc.)
        new_value: New value for the attribute
        user_id: User requesting the change
        justification: Reason for the change
        
    Returns:
        JSON string with approval request details
    """
    
    debug_print(f"Update request: Engine {serial_number}, {attribute} -> {new_value}")
    
    try:
        # Check if engine exists
        conn = sqlite3.connect('enterprise.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM engines WHERE serial_number = ?", (serial_number,))
        engine = cursor.fetchone()
        
        if not engine:
            conn.close()
            return json.dumps({
                "success": False,
                "error": f"Engine with serial number {serial_number} not found",
                "action": "search_failed"
            }, indent=2)
        
        engine_dict = dict(engine)
        old_value = engine_dict.get(attribute, "N/A")
        
        # Check if attribute exists
        if attribute not in engine_dict:
            conn.close()
            return json.dumps({
                "success": False,
                "error": f"Attribute '{attribute}' not found in engine table",
                "available_attributes": list(engine_dict.keys()),
                "action": "invalid_attribute"
            }, indent=2)
        
        # Sensitive attributes require approval
        sensitive_attributes = ["model_name", "engine_family", "power_rating", "displacement"]
        
        if attribute in sensitive_attributes:
            # Create approval request
            approval_id = str(uuid.uuid4())[:8]
            
            approval_request = {
                "approval_id": approval_id,
                "request_type": "engine_update",
                "serial_number": serial_number,
                "attribute": attribute,
                "old_value": old_value,
                "new_value": new_value,
                "user_id": user_id,
                "justification": justification,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "engine_details": engine_dict
            }
            
            PENDING_APPROVALS[approval_id] = approval_request
            
            # Send approval email (simulated)
            send_approval_email(approval_request)
            
            conn.close()
            
            return json.dumps({
                "success": True,
                "action": "approval_required",
                "approval_id": approval_id,
                "message": f"Update request submitted for approval",
                "details": {
                    "engine_serial": serial_number,
                    "attribute": attribute,
                    "change": f"{old_value} → {new_value}",
                    "status": "Pending admin approval",
                    "estimated_approval_time": "24-48 hours"
                },
                "approval_request": approval_request
            }, indent=2, default=str)
        
        else:
            # Non-sensitive attributes can be updated directly
            update_sql = f"UPDATE engines SET {attribute} = ?, last_updated = ? WHERE serial_number = ?"
            cursor.execute(update_sql, (new_value, datetime.now().isoformat(), serial_number))
            conn.commit()
            conn.close()
            
            return json.dumps({
                "success": True,
                "action": "updated_directly",
                "message": f"Engine {serial_number} updated successfully",
                "details": {
                    "attribute": attribute,
                    "old_value": old_value,
                    "new_value": new_value,
                    "updated_at": datetime.now().isoformat()
                }
            }, indent=2, default=str)
        
    except Exception as e:
        debug_print(f"Update error: {e}")
        return json.dumps({
            "success": False,
            "error": f"Update failed: {str(e)}",
            "action": "update_failed"
        }, indent=2)

@mcp_server.tool()
async def verify_claim_exists(
    claim_number: str
) -> str:
    """
    Verify if a specific claim exists in the system
    
    Args:
        claim_number: Claim number to verify (e.g., '1-ABCD')
        
    Returns:
        JSON string with verification results
    """
    
    debug_print(f"Verifying claim: {claim_number}")
    
    try:
        conn = sqlite3.connect('enterprise.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Search for exact match and similar claims
        cursor.execute("SELECT * FROM claims WHERE claim_number = ?", (claim_number,))
        exact_match = cursor.fetchone()
        
        if exact_match:
            conn.close()
            return json.dumps({
                "success": True,
                "found": True,
                "claim_number": claim_number,
                "message": f"Claim {claim_number} found in system",
                "claim_details": dict(exact_match),
                "action": "claim_exists"
            }, indent=2, default=str)
        
        # Search for similar claims
        cursor.execute("SELECT * FROM claims WHERE claim_number LIKE ? LIMIT 5", (f"%{claim_number}%",))
        similar_claims = cursor.fetchall()
        
        conn.close()
        
        if similar_claims:
            similar_list = [dict(row) for row in similar_claims]
            return json.dumps({
                "success": True,
                "found": False,
                "claim_number": claim_number,
                "message": f"Claim {claim_number} not found, but found {len(similar_claims)} similar claims",
                "similar_claims": similar_list,
                "action": "claim_not_found_similar_exists",
                "suggestion": "Check if you meant one of the similar claim numbers"
            }, indent=2, default=str)
        
        else:
            return json.dumps({
                "success": True,
                "found": False,
                "claim_number": claim_number,
                "message": f"Claim {claim_number} not found in system",
                "action": "claim_not_found",
                "possible_reasons": [
                    "Claim number may be incorrect",
                    "Claim might not be entered in system yet",
                    "Claim could be in different region database",
                    "System synchronization delay"
                ],
                "next_steps": [
                    "Verify claim number with customer",
                    "Check if claim was recently filed",
                    "Contact Brazil Claims team for manual verification"
                ]
            }, indent=2, default=str)
        
    except Exception as e:
        debug_print(f"Verification error: {e}")
        return json.dumps({
            "success": False,
            "error": f"Verification failed: {str(e)}",
            "claim_number": claim_number,
            "action": "verification_failed"
        }, indent=2)

def send_approval_email(approval_request: Dict[str, Any]):
    """Send approval email to admin (simulated)"""
    
    debug_print(f"Sending approval email for: {approval_request['approval_id']}")
    
    # In real implementation, send actual email
    # For now, just log the email content
    email_content = f"""
    APPROVAL REQUIRED: Engine Update Request
    
    Approval ID: {approval_request['approval_id']}
    Requested by: {approval_request['user_id']}
    Engine Serial: {approval_request['serial_number']}
    
    Requested Change:
    - Attribute: {approval_request['attribute']}
    - Current Value: {approval_request['old_value']}
    - New Value: {approval_request['new_value']}
    
    Justification: {approval_request['justification']}
    
    To approve: http://localhost:8083/approve/{approval_request['approval_id']}
    To reject: http://localhost:8083/reject/{approval_request['approval_id']}
    """
    
    debug_print(f"Email content: {email_content}")

debug_print("Tools registered: search_database, update_engine_attribute, verify_claim_exists")

# ================================
# FastAPI Wrapper
# ================================

def create_fastapi_app(mcp_server_instance) -> FastAPI:
    """Create FastAPI wrapper for the MCP server"""
    
    app = FastAPI(
        title="Database Query MCP Server",
        description="Text-to-SQL conversion and database operations",
        version="1.0.0"
    )
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # SSE transport
    sse_transport = SseServerTransport("/messages/")
    app.mount("/messages", sse_transport.handle_post_message)
    
    @app.get("/sse")
    async def handle_sse(request: Request):
        """SSE endpoint for MCP communication"""
        async with sse_transport.connect_sse(
            request.scope,
            request.receive,
            request._send
        ) as streams:
            await mcp_server_instance._mcp_server.run(
                streams[0],
                streams[1], 
                mcp_server_instance._mcp_server.create_initialization_options(),
            )
        return Response()
    
    @app.get("/")
    async def database_dashboard():
        """Database dashboard"""
        
        # Get database stats
        conn = sqlite3.connect('enterprise.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM claims")
        claims_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM engines")
        engines_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM warranty")
        warranty_count = cursor.fetchone()[0]
        
        # Get recent records
        cursor.execute("SELECT * FROM claims ORDER BY claim_date DESC LIMIT 5")
        recent_claims = cursor.fetchall()
        
        cursor.execute("SELECT * FROM engines ORDER BY last_updated DESC LIMIT 5")
        recent_engines = cursor.fetchall()
        
        conn.close()
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Database MCP Server Dashboard</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background: #2196F3; color: white; padding: 20px; border-radius: 5px; }}
                .stats {{ display: flex; gap: 20px; margin: 20px 0; }}
                .stat-box {{ background: #f5f5f5; padding: 15px; border-radius: 5px; flex: 1; text-align: center; }}
                .schema {{ background: #fff3cd; padding: 15px; border-radius: 5px; margin: 10px 0; }}
                .table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
                .table th, .table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                .table th {{ background-color: #f2f2f2; }}
                .pending {{ background: #fff3cd; padding: 10px; margin: 10px 0; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🗄️ Database MCP Server Dashboard</h1>
                <p>Text-to-SQL conversion and database operations</p>
            </div>
            
            <div class="stats">
                <div class="stat-box">
                    <h3>📋 Claims</h3>
                    <h2>{claims_count}</h2>
                </div>
                <div class="stat-box">
                    <h3>🔧 Engines</h3>
                    <h2>{engines_count}</h2>
                </div>
                <div class="stat-box">
                    <h3>🛡️ Warranties</h3>
                    <h2>{warranty_count}</h2>
                </div>
                <div class="stat-box">
                    <h3>⏳ Pending Approvals</h3>
                    <h2>{len(PENDING_APPROVALS)}</h2>
                </div>
            </div>
        """
        
        # Show pending approvals
        if PENDING_APPROVALS:
            html_content += "<h2>⏳ Pending Approvals</h2>"
            for approval_id, approval in PENDING_APPROVALS.items():
                html_content += f"""
                <div class="pending">
                    <h4>Approval ID: {approval_id}</h4>
                    <p><strong>Type:</strong> {approval['request_type']}</p>
                    <p><strong>Engine:</strong> {approval['serial_number']}</p>
                    <p><strong>Change:</strong> {approval['attribute']} from '{approval['old_value']}' to '{approval['new_value']}'</p>
                    <p><strong>Requested by:</strong> {approval['user_id']}</p>
                    <p><strong>Justification:</strong> {approval['justification']}</p>
                    <a href="/approve/{approval_id}">✅ Approve</a> | 
                    <a href="/reject/{approval_id}">❌ Reject</a>
                </div>
                """
        
        html_content += f"""
            <h2>🏗️ Database Schema</h2>
            <div class="schema">
                <h3>Available Tables:</h3>
                <ul>
                    <li><strong>claims</strong> - Brazil claims data ({claims_count} records)</li>
                    <li><strong>engines</strong> - Engine master data ({engines_count} records)</li>
                    <li><strong>warranty</strong> - Warranty coverage ({warranty_count} records)</li>
                </ul>
            </div>
            
            <h2>📊 Recent Claims</h2>
            <table class="table">
                <tr><th>Claim Number</th><th>Customer</th><th>Type</th><th>Status</th><th>Date</th></tr>
        """
        
        for claim in recent_claims:
            html_content += f"<tr><td>{claim[1]}</td><td>{claim[2]}</td><td>{claim[5]}</td><td>{claim[6]}</td><td>{claim[4]}</td></tr>"
        
        html_content += """
            </table>
            
            <h2>🔧 Recent Engines</h2>
            <table class="table">
                <tr><th>Serial Number</th><th>Model</th><th>Family</th><th>Power (HP)</th><th>Status</th></tr>
        """
        
        for engine in recent_engines:
            html_content += f"<tr><td>{engine[1]}</td><td>{engine[2]}</td><td>{engine[3]}</td><td>{engine[5]}</td><td>{engine[7]}</td></tr>"
        
        html_content += """
            </table>
            
            <h3>🔗 API Endpoints:</h3>
            <ul>
                <li><a href="/schema">📋 Database Schema (JSON)</a></li>
                <li><a href="/data/claims">📄 All Claims Data</a></li>
                <li><a href="/data/engines">🔧 All Engines Data</a></li>
                <li><a href="/approvals">⏳ Pending Approvals (JSON)</a></li>
                <li><a href="/health">🏥 Health Check</a></li>
                <li><a href="/tools">🔧 Available Tools</a></li>
            </ul>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
    
    @app.get("/schema")
    async def get_schema():
        """Get database schema for text-to-SQL"""
        return DATABASE_SCHEMA
    
    @app.get("/data/{table_name}")
    async def get_table_data(table_name: str):
        """Get all data from a specific table"""
        
        if table_name not in ["claims", "engines", "warranty"]:
            return {"error": f"Table {table_name} not found"}
        
        try:
            conn = sqlite3.connect('enterprise.db')
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            
            data = [dict(row) for row in rows]
            
            conn.close()
            
            return {
                "table": table_name,
                "count": len(data),
                "data": data
            }
            
        except Exception as e:
            return {"error": f"Failed to get data: {str(e)}"}
    
    @app.get("/approvals")
    async def get_pending_approvals():
        """Get all pending approvals"""
        return {
            "pending_count": len(PENDING_APPROVALS),
            "approvals": PENDING_APPROVALS
        }
    
    @app.get("/approve/{approval_id}")
    async def approve_request(approval_id: str):
        """Approve a pending request"""
        
        if approval_id not in PENDING_APPROVALS:
            return {"error": f"Approval {approval_id} not found"}
        
        approval = PENDING_APPROVALS[approval_id]
        
        try:
            # Execute the approved change
            conn = sqlite3.connect('enterprise.db')
            cursor = conn.cursor()
            
            if approval["request_type"] == "engine_update":
                update_sql = f"UPDATE engines SET {approval['attribute']} = ?, last_updated = ? WHERE serial_number = ?"
                cursor.execute(update_sql, (
                    approval['new_value'], 
                    datetime.now().isoformat(), 
                    approval['serial_number']
                ))
                conn.commit()
            
            conn.close()
            
            # Update approval status
            approval["status"] = "approved"
            approval["approved_at"] = datetime.now().isoformat()
            
            return {
                "success": True,
                "message": f"Request {approval_id} approved and executed",
                "approval": approval
            }
            
        except Exception as e:
            return {"error": f"Failed to execute approval: {str(e)}"}
    
    @app.get("/reject/{approval_id}")
    async def reject_request(approval_id: str):
        """Reject a pending request"""
        
        if approval_id not in PENDING_APPROVALS:
            return {"error": f"Approval {approval_id} not found"}
        
        approval = PENDING_APPROVALS[approval_id]
        approval["status"] = "rejected"
        approval["rejected_at"] = datetime.now().isoformat()
        
        return {
            "success": True,
            "message": f"Request {approval_id} rejected",
            "approval": approval
        }
    
    @app.get("/health")
    async def health_check():
        """Health check"""
        
        try:
            conn = sqlite3.connect('enterprise.db')
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM claims")
            claims_count = cursor.fetchone()[0]
            conn.close()
            
            return {
                "status": "healthy",
                "server": "Database Query MCP Server",
                "version": "1.0.0",
                "database_status": "connected",
                "records": {
                    "claims": claims_count
                },
                "pending_approvals": len(PENDING_APPROVALS)
            }
        except Exception as e:
            return {
                "status": "error",
                "error": f"Database connection failed: {str(e)}"
            }
    
    @app.get("/tools")
    async def list_tools():
        """List available tools"""
        return {
            "tools": [
                {
                    "name": "search_database",
                    "description": "Search database using natural language (text-to-SQL)",
                    "example": {
                        "query": "Find claim number 1-ABCD",
                        "table_hint": "claims"
                    }
                },
                {
                    "name": "update_engine_attribute",
                    "description": "Update engine attributes with approval workflow",
                    "example": {
                        "serial_number": "12345678",
                        "attribute": "model_name", 
                        "new_value": "X15",
                        "user_id": "test.user@company.com",
                        "justification": "Model upgrade required"
                    }
                },
                {
                    "name": "verify_claim_exists",
                    "description": "Verify if a claim number exists in system",
                    "example": {
                        "claim_number": "1-ABCD"
                    }
                }
            ]
        }
    
    return app

# ================================
# Server Startup
# ================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Database Query MCP Server')
    parser.add_argument('--host', default='localhost', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8083, help='Port to listen on')
    args = parser.parse_args()
    
    debug_print(f"Starting server on {args.host}:{args.port}")
    
    # Create FastAPI app
    fastapi_app = create_fastapi_app(mcp_server)
    
    debug_print("Database MCP server ready")
    debug_print("Available endpoints:")
    debug_print(f"  - Dashboard: http://{args.host}:{args.port}/")
    debug_print(f"  - SSE: http://{args.host}:{args.port}/sse")
    debug_print(f"  - Schema: http://{args.host}:{args.port}/schema")
    debug_print(f"  - Health: http://{args.host}:{args.port}/health")
    
    # Start server
    try:
        import uvicorn
        debug_print(f"Starting server...")
        uvicorn.run(
            fastapi_app,
            host=args.host,
            port=args.port,
            log_level="info"
        )
    except Exception as e:
        debug_print(f"Server error: {e}")
        raise