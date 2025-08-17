#!/usr/bin/env python3
"""
Enhanced Chatbot Client - COMPLETE FIXED VERSION
Uses direct HTTP calls for research server to avoid SSE issues
"""

import asyncio
import json
import aiohttp
from typing import Dict, Any, Optional
from mcp import ClientSession
from mcp.client.sse import sse_client

class MultiMCPClient:
    """Client that coordinates multiple MCP servers - FIXED VERSION"""
    
    def __init__(self):
        self.servers = {
            "servicenow": "http://localhost:8082/sse",
            "database": "http://localhost:8083/sse", 
            "knowledge": "http://localhost:8084/sse",
            "research": "http://localhost:8084"  # FIXED: Use direct HTTP for research
        }
    
    async def _call_mcp_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on a specific MCP server"""
        
        # SPECIAL HANDLING: Use direct HTTP for research server
        if server_name == "research":
            return await self._call_research_tool_direct(tool_name, arguments)
        
        # Original SSE implementation for other servers
        server_url = self.servers.get(server_name)
        if not server_url:
            return {"error": f"Server {server_name} not configured"}
        
        try:
            async with sse_client(server_url) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    
                    result = await session.call_tool(tool_name, arguments=arguments)
                    
                    if hasattr(result, 'content') and result.content:
                        return json.loads(result.content[0].text)
                    else:
                        return {"error": "No response from MCP server"}
                        
        except Exception as e:
            return {"error": f"MCP call failed: {str(e)}"}
    
    async def _call_research_tool_direct(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """FIXED: Direct HTTP call to research server to avoid SSE issues"""
        
        try:
            research_base_url = self.servers["research"]
            
            # Prepare the request payload
            payload = {
                "name": tool_name,
                "arguments": arguments
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{research_base_url}/tools/call",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        return result
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "error": f"HTTP {response.status}: {error_text}"
                        }
                        
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Research server timeout - query took too long"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Research server call failed: {str(e)}"
            }
    
    # ===== DATABASE OPERATIONS =====
    
    async def search_database(self, query: str, table_hint: Optional[str] = None) -> Dict[str, Any]:
        """Search database using natural language"""
        return await self._call_mcp_tool("database", "search_database", {
            "query": query,
            "table_hint": table_hint
        })
    
    async def verify_claim_exists(self, claim_number: str) -> Dict[str, Any]:
        """Verify if claim exists in database"""
        return await self._call_mcp_tool("database", "verify_claim_exists", {
            "claim_number": claim_number
        })
    
    async def update_engine_attribute(self, serial_number: str, attribute: str, new_value: str, 
                                    user_id: str, justification: str) -> Dict[str, Any]:
        """Update engine attribute with approval workflow"""
        return await self._call_mcp_tool("database", "update_engine_attribute", {
            "serial_number": serial_number,
            "attribute": attribute,
            "new_value": new_value,
            "user_id": user_id,
            "justification": justification
        })
    
    # ===== SERVICENOW OPERATIONS =====
    
    async def create_incident_ticket(self, title: str, description: str, priority: str, 
                                   assignment_group: str, caller_id: str) -> Dict[str, Any]:
        """Create ServiceNow incident ticket"""
        return await self._call_mcp_tool("servicenow", "create_incident_ticket", {
            "title": title,
            "description": description,
            "priority": priority,
            "urgency": priority,
            "assignment_group": assignment_group,
            "caller_id": caller_id
        })
    
    async def create_service_request(self, title: str, description: str, priority: str,
                                   assignment_group: str, caller_id: str, category: str) -> Dict[str, Any]:
        """Create ServiceNow service request"""
        return await self._call_mcp_tool("servicenow", "create_service_request", {
            "title": title,
            "description": description,
            "priority": priority,
            "assignment_group": assignment_group,
            "caller_id": caller_id,
            "category": category
        })
    
    # ===== RESEARCH OPERATIONS (Direct HTTP calls) =====
    
    async def search_research_papers(self, query: str, max_results: int = 10, 
                                   include_reasoning: bool = True) -> Dict[str, Any]:
        """Search research papers using multi-hop reasoning"""
        return await self._call_mcp_tool("research", "search_research_papers", {
            "query": query,
            "max_results": max_results,
            "include_reasoning": include_reasoning
        })
    
    async def analyze_research_topic(self, topic: str, analysis_type: str = "comprehensive") -> Dict[str, Any]:
        """Deep analysis of a research topic"""
        return await self._call_mcp_tool("research", "analyze_research_topic", {
            "topic": topic,
            "analysis_type": analysis_type
        })
    
    async def find_paper_relationships(self, concept1: str, concept2: str, 
                                     max_hops: int = 3) -> Dict[str, Any]:
        """Find relationships between research concepts"""
        return await self._call_mcp_tool("research", "find_paper_relationships", {
            "concept1": concept1,
            "concept2": concept2,
            "max_hops": max_hops
        })
    
    # ===== COMPLEX WORKFLOWS =====
    
    async def handle_missing_claim_workflow(self, claim_number: str, user_id: str) -> Dict[str, Any]:
        """
        Complex workflow: Search for claim, if not found, create ticket to Brazil Claims team
        Coordinates database search + ticket creation
        """
        
        print(f"🔍 Starting missing claim workflow for: {claim_number}")
        
        # Step 1: Search for the claim in database
        print(f"📊 Step 1: Searching database for claim {claim_number}")
        verification_result = await self.verify_claim_exists(claim_number)
        
        if verification_result.get("success") and verification_result.get("found"):
            # Claim found - return the details
            return {
                "workflow": "missing_claim",
                "step": "search_completed",
                "action": "claim_found",
                "result": verification_result,
                "message": f"✅ Claim {claim_number} found in system!",
                "claim_details": verification_result.get("claim_details")
            }
        
        elif verification_result.get("success") and not verification_result.get("found"):
            # Claim not found - check for similar claims first
            similar_claims = verification_result.get("similar_claims", [])
            
            if similar_claims:
                return {
                    "workflow": "missing_claim",
                    "step": "search_completed", 
                    "action": "similar_claims_found",
                    "result": verification_result,
                    "message": f"⚠️ Claim {claim_number} not found, but found {len(similar_claims)} similar claims",
                    "similar_claims": similar_claims,
                    "suggestion": "Please check if you meant one of the similar claim numbers, or proceed to create a ticket"
                }
            
            # No similar claims - create ticket to Brazil Claims team
            print(f"🎫 Step 2: Creating ticket to Brazil Claims team")
            
            ticket_result = await self.create_service_request(
                title=f"Missing Brazil Claim Investigation: {claim_number}",
                description=f"""
Investigation Request for Missing Brazil Claim

Claim Number: {claim_number}
Reported by: {user_id}
Search Result: Claim not found in system database

Possible reasons for missing claim:
{chr(10).join(f"• {reason}" for reason in verification_result.get("possible_reasons", []))}

Next steps required:
{chr(10).join(f"• {step}" for step in verification_result.get("next_steps", []))}

Please investigate and update the requestor with findings.
                """.strip(),
                priority="medium",
                assignment_group="Brazil Claims Team",
                caller_id=user_id,
                category="Missing Record Investigation"
            )
            
            if ticket_result.get("success"):
                return {
                    "workflow": "missing_claim",
                    "step": "ticket_created",
                    "action": "investigation_ticket_created",
                    "search_result": verification_result,
                    "ticket_result": ticket_result,
                    "message": f"""
📋 **Missing Claim Investigation Initiated**

**Claim Number:** {claim_number}
**Status:** Not found in system database

✅ **Service Request Created:**
• **Ticket Number:** {ticket_result.get("result", {}).get("request_number", "Unknown")}
• **Assigned to:** Brazil Claims Team
• **Priority:** Medium
• **Expected Response:** 24-48 hours

The Brazil Claims team will investigate and contact you with findings.
                    """.strip()
                }
            else:
                return {
                    "workflow": "missing_claim",
                    "step": "ticket_creation_failed",
                    "action": "manual_escalation_required",
                    "search_result": verification_result,
                    "ticket_error": ticket_result.get("error"),
                    "message": f"""
❌ **Automated Process Failed**

Claim {claim_number} not found and ticket creation failed.
Error: {ticket_result.get("error")}

Please contact Brazil Claims team directly:
• Email: brazil.claims@company.com
• Phone: +55 11 1234-5678
                    """.strip()
                }
        
        else:
            # Search failed
            return {
                "workflow": "missing_claim",
                "step": "search_failed",
                "action": "manual_verification_required",
                "error": verification_result.get("error"),
                "message": f"""
❌ **Database Search Failed**

Unable to search for claim {claim_number} due to system error.
Error: {verification_result.get("error")}

Please try again later or contact IT support.
                """.strip()
            }
    
    async def handle_engine_update_workflow(self, serial_number: str, attribute: str, 
                                          new_value: str, user_id: str, justification: str) -> Dict[str, Any]:
        """
        Complex workflow: Update engine attribute with approval process
        """
        
        print(f"🔧 Starting engine update workflow: {serial_number} {attribute} -> {new_value}")
        
        # Step 1: Attempt the update (will trigger approval process if needed)
        update_result = await self.update_engine_attribute(
            serial_number=serial_number,
            attribute=attribute,
            new_value=new_value,
            user_id=user_id,
            justification=justification
        )
        
        if update_result.get("success"):
            
            if update_result.get("action") == "updated_directly":
                # Non-sensitive attribute updated directly
                return {
                    "workflow": "engine_update",
                    "step": "completed",
                    "action": "updated_directly",
                    "result": update_result,
                    "message": f"""
✅ **Engine Updated Successfully**

**Engine Serial:** {serial_number}
**Attribute:** {attribute}
**New Value:** {new_value}
**Updated:** {update_result.get("details", {}).get("updated_at", "Now")}

The change has been applied immediately as this is a non-sensitive attribute.
                    """.strip()
                }
            
            elif update_result.get("action") == "approval_required":
                # Sensitive attribute requires approval
                approval_details = update_result.get("details", {})
                
                return {
                    "workflow": "engine_update",
                    "step": "approval_pending",
                    "action": "approval_required",
                    "result": update_result,
                    "message": f"""
⏳ **Approval Required for Engine Update**

**Engine Serial:** {serial_number}
**Requested Change:** {approval_details.get("change", f"{attribute} -> {new_value}")}
**Approval ID:** {update_result.get("approval_id")}

**Status:** {approval_details.get("status", "Pending admin approval")}
**Expected Timeline:** {approval_details.get("estimated_approval_time", "24-48 hours")}

An admin has been notified and will review your request. You'll receive an email update once the decision is made.

**Justification Provided:** {justification}
                    """.strip()
                }
        
        else:
            # Update failed
            return {
                "workflow": "engine_update",
                "step": "failed",
                "action": update_result.get("action", "update_failed"),
                "error": update_result.get("error"),
                "message": f"""
❌ **Engine Update Failed**

**Engine Serial:** {serial_number}
**Requested Change:** {attribute} -> {new_value}
**Error:** {update_result.get("error", "Unknown error")}

Please verify the engine serial number and attribute name, then try again.
                """.strip()
            }

    # ===== RESEARCH WORKFLOWS =====
    
    async def handle_research_query_workflow(self, query: str, user_id: str, 
                                        analysis_type: str = "comprehensive") -> Dict[str, Any]:
        """
        FIXED: Complex workflow for research queries using real RAG system
        """
        
        print(f"📊 Starting research query workflow: {query}")
        
        try:
            # Step 1: Search for research papers
            print("🔍 Step 1: Searching research papers")
            search_result = await self.search_research_papers(
                query=query,
                max_results=10,
                include_reasoning=True
            )
            
            print(f"🔍 Search result received: {search_result.get('success', 'Unknown')}")
            
            # FIXED: Check for success properly
            if search_result.get("success") == True:
                return {
                    "workflow": "research_query",
                    "step": "completed",
                    "action": "research_found",
                    "result": search_result,
                    "success": True,  # IMPORTANT: Set this explicitly
                    "message": f"""
    📊 **Research Query Results**

    **Query:** {query}

    **Answer:**
    {search_result.get("answer", "No answer available")}

    **Research Analysis:**
    • **Entities Found:** {search_result.get("summary", {}).get("entities_found", 0)}
    • **Reasoning Paths:** {search_result.get("summary", {}).get("reasoning_paths", 0)}
    • **Knowledge Connections:** {search_result.get("summary", {}).get("context_triples", 0)}

    **Key Research Entities:**
    {chr(10).join(f"• {entity}" for entity in search_result.get("reasoning_details", {}).get("entities_used", [])[:5])}

    **Top Reasoning Paths:**
    {chr(10).join(f"• {path.get('path_string', 'Unknown path')}" for path in search_result.get("reasoning_details", {}).get("top_reasoning_paths", [])[:3])}
                    """.strip()
                }
            else:
                # FIXED: Better error handling
                print(f"❌ Search failed with result: {search_result}")
                return {
                    "workflow": "research_query",
                    "step": "failed",
                    "action": "research_unavailable",
                    "success": False,
                    "error": search_result.get("error", "Unknown error"),
                    "message": f"""
    ❌ **Research Query Failed**

    **Query:** {query}
    **Error:** {search_result.get("error", "Research system unavailable")}

    **Debug Info:**
    • Full result: {str(search_result)[:200]}...

    **Suggestions:**
    • Check if research MCP server is running on port 8084
    • Verify Neo4j database connection
    • Try rephrasing your research question
    • Contact research support team
                    """.strip()
                }
        
        except Exception as e:
            print(f"❌ Exception in research workflow: {e}")
            return {
                "workflow": "research_query",
                "step": "error", 
                "action": "exception_occurred",
                "success": False,
                "error": str(e),
                "message": f"""
    ❌ **Research Workflow Error**

    **Query:** {query}
    **Error:** {str(e)}

    Please try again or contact technical support.
                """.strip()
            }
# Example usage functions for testing
async def test_missing_claim_workflow():
    """Test the missing claim workflow"""
    
    client = MultiMCPClient()
    
    print("Testing Missing Claim Workflow")
    print("=" * 40)
    
    # Test 1: Existing claim
    print("\n1. Testing existing claim (1-AAAA):")
    result1 = await client.handle_missing_claim_workflow("1-AAAA", "test.user@company.com")
    print(f"Action: {result1['action']}")
    print(f"Message: {result1['message']}")
    
    # Test 2: Non-existing claim
    print("\n2. Testing non-existing claim (1-ABCD):")
    result2 = await client.handle_missing_claim_workflow("1-ABCD", "test.user@company.com")
    print(f"Action: {result2['action']}")
    print(f"Message: {result2['message']}")

async def test_engine_update_workflow():
    """Test the engine update workflow"""
    
    client = MultiMCPClient()
    
    print("Testing Engine Update Workflow")
    print("=" * 40)
    
    # Test 1: Sensitive attribute (requires approval)
    print("\n1. Testing sensitive attribute update (model_name):")
    result1 = await client.handle_engine_update_workflow(
        serial_number="12345678",
        attribute="model_name",
        new_value="X15",
        user_id="test.user@company.com",
        justification="Model upgrade required for performance improvement"
    )
    print(f"Action: {result1['action']}")
    print(f"Message: {result1['message']}")
    
    # Test 2: Non-sensitive attribute (direct update)
    print("\n2. Testing non-sensitive attribute update (location):")
    result2 = await client.handle_engine_update_workflow(
        serial_number="12345678",
        attribute="location",
        new_value="Mexico Plant",
        user_id="test.user@company.com",
        justification="Engine transferred to new facility"
    )
    print(f"Action: {result2['action']}")
    print(f"Message: {result2['message']}")

async def test_research_workflow():
    """Test the research workflow with real RAG system"""
    
    client = MultiMCPClient()
    
    print("Testing Research Query Workflow")
    print("=" * 40)
    
    # Test 1: Transformer query
    print("\n1. Testing transformer research query:")
    result1 = await client.handle_research_query_workflow(
        query="What are transformer models and how do they work?",
        user_id="test.user@company.com",
        analysis_type="technical"
    )
    print(f"Action: {result1['action']}")
    print(f"Success: {result1.get('result', {}).get('success', 'Unknown')}")
    if result1.get('result', {}).get('success'):
        print(f"Entities found: {result1['result']['summary']['entities_found']}")
        print(f"Reasoning paths: {result1['result']['summary']['reasoning_paths']}")
    print(f"Message preview: {result1['message'][:300]}...")
    
    # Test 2: Direct research paper search
    print("\n2. Testing direct research paper search:")
    search_result = await client.search_research_papers(
        query="attention mechanisms in neural networks",
        max_results=5,
        include_reasoning=True
    )
    print(f"Search success: {search_result.get('success', False)}")
    if search_result.get('success'):
        print(f"Answer preview: {search_result['answer'][:200]}...")
        print(f"Entities: {search_result['summary']['entities_found']}")
    else:
        print(f"Error: {search_result.get('error', 'Unknown error')}")
    
    # Test 3: Research topic analysis
    print("\n3. Testing research topic analysis:")
    analysis_result = await client.analyze_research_topic(
        topic="neural machine translation",
        analysis_type="comprehensive"
    )
    print(f"Analysis success: {analysis_result.get('success', False)}")
    if analysis_result.get('success'):
        print(f"Key entities: {analysis_result.get('key_entities', [])[:3]}")
        print(f"Research depth: {analysis_result.get('research_depth', {})}")
    else:
        print(f"Error: {analysis_result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "test_claim":
            asyncio.run(test_missing_claim_workflow())
        elif sys.argv[1] == "test_engine":
            asyncio.run(test_engine_update_workflow())
        elif sys.argv[1] == "test_research":
            asyncio.run(test_research_workflow())
        else:
            print("Usage: python enhanced_chatbot_client.py [test_claim|test_engine|test_research]")
    else:
        print("Enhanced Multi-MCP Client loaded. Use in Streamlit app.")
        print("Available methods:")
        print("  - handle_missing_claim_workflow()")
        print("  - handle_engine_update_workflow()")
        print("  - handle_research_query_workflow()  # NEW - Real RAG integration")
        print("  - search_database()")
        print("  - create_incident_ticket()")
        print("  - create_service_request()")
        print("  - search_research_papers()  # NEW - Direct RAG calls")
        print("  - analyze_research_topic()  # NEW - Real analysis")
        print("  - find_paper_relationships()  # NEW - Real relationships")