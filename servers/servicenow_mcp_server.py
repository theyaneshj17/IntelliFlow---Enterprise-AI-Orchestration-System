#!/usr/bin/env python3
"""
Simple ServiceNow Ticket MCP Server
Just creates tickets - keep it simple!
"""

import json
import sys
import argparse
from typing import Optional
import uuid
from datetime import datetime

# FastAPI imports
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

# MCP imports
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport

def debug_print(message):
    """Debug print to stderr"""
    print(f"[TICKET-SERVER] {message}", file=sys.stderr, flush=True)

debug_print("Starting Simple ServiceNow Ticket MCP Server...")

# ================================
# In-Memory Ticket Storage
# ================================

# Store tickets in memory (replace with real database in production)
TICKET_STORAGE = {
    "incidents": {},
    "service_requests": {}
}

# ================================
# MCP Server Setup
# ================================

mcp_server = FastMCP("ServiceNow Ticket Server")

@mcp_server.tool()
async def create_incident_ticket(
    title: str,
    description: str,
    priority: str = "medium",
    urgency: str = "medium",
    assignment_group: str = "IT Support",
    caller_id: str = "system.user"
) -> str:
    """
    Create a ServiceNow incident ticket
    
    Args:
        title: Short description of the incident
        description: Detailed description
        priority: critical, high, medium, low
        urgency: critical, high, medium, low
        assignment_group: Team to assign to
        caller_id: User reporting the incident
        
    Returns:
        JSON string with ticket details
    """
    
    debug_print(f"Creating incident ticket: {title}")
    
    # Generate fake ticket number
    ticket_number = f"INC{hash(title) % 1000000:06d}"
    
    # Map priority to ServiceNow format
    priority_map = {"critical": "1", "high": "2", "medium": "3", "low": "4"}
    
    # Simulate ticket creation
    ticket_data = {
        "ticket_number": ticket_number,
        "short_description": title,
        "description": description,
        "priority": priority_map.get(priority.lower(), "3"),
        "urgency": priority_map.get(urgency.lower(), "3"),
        "assignment_group": assignment_group,
        "caller_id": caller_id,
        "state": "New",
        "created_on": datetime.now().isoformat(),
        "sys_id": str(uuid.uuid4()),
        "status": "created",
        "sla_response_time": {
            "critical": "30 minutes",
            "high": "4 hours", 
            "medium": "24 hours",
            "low": "72 hours"
        }.get(priority.lower(), "24 hours")
    }
    
    # Store ticket in memory
    TICKET_STORAGE["incidents"][ticket_number] = ticket_data
    
    debug_print(f"Ticket created: {ticket_number}")
    debug_print(f"Total incidents stored: {len(TICKET_STORAGE['incidents'])}")
    
    return json.dumps({
        "success": True,
        "ticket_created": True,
        "result": ticket_data,
        "message": f"Successfully created incident ticket {ticket_number}"
    }, indent=2)

@mcp_server.tool()
async def create_service_request(
    title: str,
    description: str,
    priority: str = "medium",
    assignment_group: str = "IT Support",
    caller_id: str = "system.user",
    category: str = "Data Request"
) -> str:
    """
    Create a ServiceNow service request
    
    Args:
        title: Short description of the request
        description: Detailed description
        priority: critical, high, medium, low
        assignment_group: Team to handle request
        caller_id: User making the request
        category: Request category
        
    Returns:
        JSON string with service request details
    """
    
    debug_print(f"Creating service request: {title}")
    
    # Generate fake request number
    request_number = f"REQ{hash(title) % 1000000:06d}"
    
    priority_map = {"critical": "1", "high": "2", "medium": "3", "low": "4"}
    
    # Simulate service request creation
    request_data = {
        "request_number": request_number,
        "short_description": title,
        "description": description,
        "priority": priority_map.get(priority.lower(), "3"),
        "assignment_group": assignment_group,
        "requested_by": caller_id,
        "category": category,
        "state": "Open",
        "created_on": datetime.now().isoformat(),
        "sys_id": str(uuid.uuid4()),
        "status": "created",
        "estimated_completion": {
            "critical": "4 hours",
            "high": "24 hours",
            "medium": "3 days", 
            "low": "5 days"
        }.get(priority.lower(), "3 days")
    }
    
    # Store service request in memory
    TICKET_STORAGE["service_requests"][request_number] = request_data
    
    debug_print(f"Service request created: {request_number}")
    debug_print(f"Total service requests stored: {len(TICKET_STORAGE['service_requests'])}")
    
    return json.dumps({
        "success": True,
        "request_created": True,
        "result": request_data,
        "message": f"Successfully created service request {request_number}"
    }, indent=2)

@mcp_server.tool()
async def get_ticket_status(
    ticket_number: str,
    ticket_type: str = "incident"
) -> str:
    """
    Get status of a ticket
    
    Args:
        ticket_number: The ticket number (e.g., INC000123)
        ticket_type: incident or service_request
        
    Returns:
        JSON string with ticket status
    """
    
    debug_print(f"Getting status for ticket: {ticket_number}")
    
    # Simulate ticket lookup
    if ticket_number.startswith("INC"):
        if ticket_number in TICKET_STORAGE["incidents"]:
            ticket_data = TICKET_STORAGE["incidents"][ticket_number]
            status_data = {
                "ticket_number": ticket_number,
                "ticket_type": "incident",
                "state": ticket_data["state"],
                "assigned_to": "John Smith",
                "assignment_group": ticket_data["assignment_group"],
                "created_on": ticket_data["created_on"],
                "priority": ticket_data["priority"],
                "short_description": ticket_data["short_description"],
                "last_updated": datetime.now().isoformat(),
                "work_notes": "Investigation in progress"
            }
            
            return json.dumps({
                "success": True,
                "found": True,
                "result": status_data
            }, indent=2)
        else:
            return json.dumps({
                "success": False,
                "found": False,
                "error": f"Incident {ticket_number} not found"
            }, indent=2)
    
    elif ticket_number.startswith("REQ"):
        if ticket_number in TICKET_STORAGE["service_requests"]:
            ticket_data = TICKET_STORAGE["service_requests"][ticket_number]
            status_data = {
                "ticket_number": ticket_number,
                "ticket_type": "service_request",
                "state": ticket_data["state"],
                "assignment_group": ticket_data["assignment_group"],
                "created_on": ticket_data["created_on"],
                "priority": ticket_data["priority"],
                "short_description": ticket_data["short_description"],
                "last_updated": datetime.now().isoformat()
            }
            
            return json.dumps({
                "success": True,
                "found": True,
                "result": status_data
            }, indent=2)
        else:
            return json.dumps({
                "success": False,
                "found": False,
                "error": f"Service request {ticket_number} not found"
            }, indent=2)
    else:
        return json.dumps({
            "success": False,
            "found": False,
            "error": f"Invalid ticket number format: {ticket_number}"
        }, indent=2)

debug_print("Tools registered: create_incident_ticket, create_service_request, get_ticket_status")

# ================================
# FastAPI Wrapper
# ================================

def create_fastapi_app(mcp_server_instance) -> FastAPI:
    """Create FastAPI wrapper for the MCP server"""
    
    app = FastAPI(
        title="ServiceNow Ticket MCP Server",
        description="Simple ServiceNow ticket creation via MCP",
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
    
    @app.get("/tickets")
    async def list_all_tickets():
        """List all created tickets"""
        return {
            "incidents": {
                "count": len(TICKET_STORAGE["incidents"]),
                "tickets": list(TICKET_STORAGE["incidents"].values())
            },
            "service_requests": {
                "count": len(TICKET_STORAGE["service_requests"]),
                "tickets": list(TICKET_STORAGE["service_requests"].values())
            },
            "total_tickets": len(TICKET_STORAGE["incidents"]) + len(TICKET_STORAGE["service_requests"])
        }
    
    @app.get("/tickets/{ticket_number}")
    async def get_specific_ticket(ticket_number: str):
        """Get specific ticket details"""
        
        # Check incidents
        if ticket_number in TICKET_STORAGE["incidents"]:
            return {
                "found": True,
                "type": "incident",
                "ticket": TICKET_STORAGE["incidents"][ticket_number]
            }
        
        # Check service requests
        if ticket_number in TICKET_STORAGE["service_requests"]:
            return {
                "found": True,
                "type": "service_request", 
                "ticket": TICKET_STORAGE["service_requests"][ticket_number]
            }
        
        return {
            "found": False,
            "error": f"Ticket {ticket_number} not found"
        }
    
    @app.get("/tickets/incidents")
    async def list_incidents():
        """List all incidents"""
        return {
            "count": len(TICKET_STORAGE["incidents"]),
            "incidents": list(TICKET_STORAGE["incidents"].values())
        }
    
    @app.get("/tickets/service_requests")
    async def list_service_requests():
        """List all service requests"""
        return {
            "count": len(TICKET_STORAGE["service_requests"]),
            "service_requests": list(TICKET_STORAGE["service_requests"].values())
        }
    
    @app.get("/")
    async def ticket_dashboard():
        """Simple HTML dashboard to view tickets"""
        
        incidents = list(TICKET_STORAGE["incidents"].values())
        service_requests = list(TICKET_STORAGE["service_requests"].values())
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>ServiceNow Ticket Dashboard</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background: #0066cc; color: white; padding: 20px; border-radius: 5px; }}
                .stats {{ display: flex; gap: 20px; margin: 20px 0; }}
                .stat-box {{ background: #f5f5f5; padding: 15px; border-radius: 5px; flex: 1; }}
                .ticket {{ background: white; border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }}
                .priority-critical {{ border-left: 5px solid #ff0000; }}
                .priority-high {{ border-left: 5px solid #ff6600; }}
                .priority-medium {{ border-left: 5px solid #ffcc00; }}
                .priority-low {{ border-left: 5px solid #00cc00; }}
                .refresh {{ background: #0066cc; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🎫 ServiceNow Ticket Dashboard</h1>
                <p>Real-time view of created tickets</p>
            </div>
            
            <div class="stats">
                <div class="stat-box">
                    <h3>🚨 Incidents</h3>
                    <h2>{len(incidents)}</h2>
                </div>
                <div class="stat-box">
                    <h3>📋 Service Requests</h3>
                    <h2>{len(service_requests)}</h2>
                </div>
                <div class="stat-box">
                    <h3>📊 Total Tickets</h3>
                    <h2>{len(incidents) + len(service_requests)}</h2>
                </div>
            </div>
            
            <button class="refresh" onclick="location.reload()">🔄 Refresh</button>
            
            <h2>🚨 Recent Incidents</h2>
        """
        
        if incidents:
            for ticket in sorted(incidents, key=lambda x: x['created_on'], reverse=True):
                priority_class = f"priority-{ticket.get('priority', '3').replace('1', 'critical').replace('2', 'high').replace('3', 'medium').replace('4', 'low')}"
                html_content += f"""
                <div class="ticket {priority_class}">
                    <h4>{ticket['ticket_number']} - {ticket['short_description']}</h4>
                    <p><strong>Priority:</strong> {ticket.get('priority', 'Unknown')} | 
                       <strong>Status:</strong> {ticket['state']} | 
                       <strong>Assigned:</strong> {ticket['assignment_group']}</p>
                    <p><strong>Created:</strong> {ticket['created_on']}</p>
                    <p><strong>Description:</strong> {ticket['description'][:100]}...</p>
                </div>
                """
        else:
            html_content += "<p>No incidents created yet.</p>"
        
        html_content += "<h2>📋 Recent Service Requests</h2>"
        
        if service_requests:
            for ticket in sorted(service_requests, key=lambda x: x['created_on'], reverse=True):
                html_content += f"""
                <div class="ticket">
                    <h4>{ticket['request_number']} - {ticket['short_description']}</h4>
                    <p><strong>Priority:</strong> {ticket.get('priority', 'Unknown')} | 
                       <strong>Status:</strong> {ticket['state']} | 
                       <strong>Category:</strong> {ticket.get('category', 'General')}</p>
                    <p><strong>Created:</strong> {ticket['created_on']}</p>
                    <p><strong>Description:</strong> {ticket['description'][:100]}...</p>
                </div>
                """
        else:
            html_content += "<p>No service requests created yet.</p>"
        
        html_content += """
            <hr>
            <h3>📍 API Endpoints:</h3>
            <ul>
                <li><a href="/tickets">📊 All Tickets (JSON)</a></li>
                <li><a href="/tickets/incidents">🚨 Incidents Only (JSON)</a></li>
                <li><a href="/tickets/service_requests">📋 Service Requests Only (JSON)</a></li>
                <li><a href="/health">🏥 Health Check</a></li>
                <li><a href="/tools">🔧 Available Tools</a></li>
            </ul>
        </body>
        </html>
        """
        
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html_content)
    
    @app.get("/health")
    async def health_check():
        """Health check"""
        return {
            "status": "healthy",
            "server": "ServiceNow Ticket MCP Server",
            "version": "1.0.0",
            "tickets_stored": {
                "incidents": len(TICKET_STORAGE["incidents"]),
                "service_requests": len(TICKET_STORAGE["service_requests"]),
                "total": len(TICKET_STORAGE["incidents"]) + len(TICKET_STORAGE["service_requests"])
            }
        }
    
    @app.get("/tools")
    async def list_tools():
        """List available tools"""
        return {
            "tools": [
                {
                    "name": "create_incident_ticket",
                    "description": "Create ServiceNow incident ticket",
                    "example": {
                        "title": "System down",
                        "description": "Warranty system not working",
                        "priority": "critical"
                    }
                },
                {
                    "name": "create_service_request",
                    "description": "Create ServiceNow service request", 
                    "example": {
                        "title": "Data search request",
                        "description": "Find missing claim record",
                        "category": "Data Request"
                    }
                },
                {
                    "name": "get_ticket_status",
                    "description": "Get ticket status",
                    "example": {
                        "ticket_number": "INC000123"
                    }
                }
            ]
        }
    
    return app

# ================================
# Server Startup
# ================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='ServiceNow Ticket MCP Server')
    parser.add_argument('--host', default='localhost', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8082, help='Port to listen on')
    args = parser.parse_args()
    
    debug_print(f"Starting server on {args.host}:{args.port}")
    
    # Create FastAPI app
    fastapi_app = create_fastapi_app(mcp_server)
    
    debug_print("FastAPI app created")
    debug_print("Available endpoints:")
    debug_print(f"  - SSE: http://{args.host}:{args.port}/sse")
    debug_print(f"  - Health: http://{args.host}:{args.port}/health")
    debug_print(f"  - Tools: http://{args.host}:{args.port}/tools")
    
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