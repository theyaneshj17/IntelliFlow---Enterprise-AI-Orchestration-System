#!/usr/bin/env python3
"""
Complete Chatbot Workflow with Intent Classification + MCP Integration
UPDATED VERSION - Now includes Research Query handling
"""

import asyncio
import json
import anthropic
from typing import Dict, Any, Optional
from enum import Enum

# Import your existing components - FIXED IMPORTS
try:
    from intent_classifier import SmartChatbotOrchestrator, IntentType
except ImportError:
    print("Warning: intent_classifier not found, creating minimal version")
    
    # Minimal IntentType enum if import fails
    class IntentType(Enum):
        SYSTEM_INCIDENT = "system_incident"
        DATA_QUERY = "data_query"
        INFORMATION_REQUEST = "information_request"
        RESEARCH_QUERY = "research_query"  # NEW
    
    # Minimal orchestrator if import fails
    class SmartChatbotOrchestrator:
        def __init__(self, api_key):
            self.api_key = api_key
        
        def process_user_input(self, user_input, user_id):
            # Simple fallback classification
            if any(word in user_input.lower() for word in ["down", "not working", "error", "broken", "issue"]):
                intent = IntentType.SYSTEM_INCIDENT
            elif any(word in user_input.lower() for word in ["find", "search", "get", "show", "update", "delete"]):
                intent = IntentType.DATA_QUERY
            elif any(word in user_input.lower() for word in ["research", "paper", "algorithm", "analysis", "compare"]):
                intent = IntentType.RESEARCH_QUERY  # NEW
            else:
                intent = IntentType.INFORMATION_REQUEST
            
            return {
                "classification": type('obj', (object,), {
                    'intent': intent,
                    'confidence': 0.8
                })(),
                "specialized_analysis": {
                    "severity": "medium",
                    "affected_system": "unknown",
                    "target_system": "database",
                    "research_type": "topic_analysis",  # NEW
                    "analysis_depth": "comprehensive"   # NEW
                }
            }

try:
    from enhanced_streamlit_chatbot import MultiMCPClient
except ImportError:
    print("Warning: enhanced_streamlit_chatbot not found, creating minimal version")
    
    # Minimal MCP client if import fails
    class MultiMCPClient:
        def __init__(self):
            pass
        
        async def search_database(self, query, table_hint=None):
            return {"success": False, "error": "MCP client not available"}
        
        async def create_service_request(self, title, description, priority, assignment_group, caller_id, category):
            return {"success": False, "error": "MCP client not available"}
        
        async def create_incident_ticket(self, title, description, priority, assignment_group, caller_id):
            return {"success": False, "error": "MCP client not available"}
        
        # NEW: Research methods
        async def handle_research_query_workflow(self, query, user_id, analysis_type="comprehensive"):
            return {"success": False, "error": "Research MCP client not available"}

class CompleteChatbotWorkflow:
    """
    Complete workflow that combines:
    1. Intent Classification (Claude)
    2. Specialized Analysis (Claude) 
    3. MCP Server Calls (Actual execution)
    4. NEW: Research Query Processing
    """
    
    def __init__(self, claude_api_key: str):
        # Initialize intent classifier
        self.intent_orchestrator = SmartChatbotOrchestrator(claude_api_key)
        
        # Initialize MCP client
        self.mcp_client = MultiMCPClient()
        
        # Store Claude client for data manipulation detection
        self.claude_client = anthropic.Anthropic(api_key=claude_api_key)
    
    def is_missing_data_query(self, user_input: str) -> bool:
        """
        Detect if user is reporting missing/lost data vs just searching
        """
        
        missing_keywords = [
            "missing", "can't find", "cannot find", "not found", "lost", 
            "disappeared", "absent", "unavailable", "not showing up",
            "not in the system", "not there", "where is"
        ]
        
        # Check if query contains missing data indicators
        query_lower = user_input.lower()
        
        for keyword in missing_keywords:
            if keyword in query_lower:
                return True
        
        return False
    
    async def detect_data_manipulation_with_llm(self, user_input: str) -> Dict[str, Any]:
        """
        Use Claude to detect and parse data manipulation requests
        """
        
        prompt = f"""
You are a data operation analyzer. Determine if the user wants to manipulate data (UPDATE/DELETE/INSERT) vs just search/read data.

USER INPUT: "{user_input}"

Analyze the request and return JSON with this exact structure:

{{
    "is_manipulation": true/false,
    "operation_type": "update" | "delete" | "insert" | "search",
    "entity_type": "claim" | "engine" | "warranty" | "unknown",
    "entity_identifier": "extracted ID/serial/number",
    "target_field": "field being changed",
    "old_value": "current value",
    "new_value": "desired new value",
    "sql_intent": "Plain English description of what SQL would do",
    "requires_approval": true/false
}}

EXAMPLES:

Input: "Update engine serial 12345678 model from X10 to X15"
Output: {{
    "is_manipulation": true,
    "operation_type": "update",
    "entity_type": "engine", 
    "entity_identifier": "12345678",
    "target_field": "model_name",
    "old_value": "X10",
    "new_value": "X15",
    "sql_intent": "Update engines table SET model_name='X15' WHERE serial_number='12345678'",
    "requires_approval": true
}}

Input: "Can u update claim Number '1-CCCC' to '1-DDDD'"
Output: {{
    "is_manipulation": true,
    "operation_type": "update",
    "entity_type": "claim",
    "entity_identifier": "1-CCCC", 
    "target_field": "claim_number",
    "old_value": "1-CCCC",
    "new_value": "1-DDDD",
    "sql_intent": "Update claims table SET claim_number='1-DDDD' WHERE claim_number='1-CCCC'",
    "requires_approval": true
}}

Input: "Find claim 1-ABCD"
Output: {{
    "is_manipulation": false,
    "operation_type": "search",
    "entity_type": "claim",
    "entity_identifier": "1-ABCD",
    "target_field": null,
    "old_value": null,
    "new_value": null,
    "sql_intent": "Select from claims table WHERE claim_number='1-ABCD'",
    "requires_approval": false
}}

RULES:
- UPDATE/MODIFY/CHANGE/ALTER/SET = manipulation (requires approval)
- DELETE/REMOVE/DROP = manipulation (requires approval)  
- INSERT/ADD/CREATE = manipulation (requires approval)
- FIND/GET/SHOW/SEARCH = search (no approval needed)
- All data manipulation requires approval for safety

Analyze the input now:
"""

        try:
            response = self.claude_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=800,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}]
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
            
            return result
            
        except Exception as e:
            print(f"LLM data manipulation detection error: {e}")
            # Fallback: assume it's a search if we can't parse
            return {
                "is_manipulation": False,
                "operation_type": "search",
                "entity_type": "unknown",
                "entity_identifier": None,
                "target_field": None,
                "old_value": None,
                "new_value": None,
                "sql_intent": f"Search for: {user_input}",
                "requires_approval": False,
                "error": str(e)
            }
    
    async def process_complete_workflow(self, user_input: str, user_id: str) -> Dict[str, Any]:
        """
        Complete processing workflow:
        1. Classify intent with Claude
        2. Analyze with specialized handlers
        3. Execute via appropriate MCP servers
        4. NEW: Handle research queries
        """
        
        print(f"🎯 Starting complete workflow for: '{user_input}'")
        
        # STEP 1: Intent Classification (Claude)
        print("📊 Step 1: Intent Classification")
        
        try:
            classification_result = self.intent_orchestrator.process_user_input(user_input, user_id)
            
            classification = classification_result["classification"]
            analysis = classification_result.get("specialized_analysis")
            
            print(f"   Intent: {classification.intent.value}")
            print(f"   Confidence: {classification.confidence:.2f}")
        except Exception as e:
            print(f"   Error in intent classification: {e}")
            # Fallback to data query
            classification = type('obj', (object,), {
                'intent': IntentType.DATA_QUERY,
                'confidence': 0.5
            })()
            analysis = {"target_system": "database"}
            classification_result = {"classification": classification, "specialized_analysis": analysis}
        
        # STEP 2: Route to appropriate MCP workflow
        if classification.intent == IntentType.SYSTEM_INCIDENT:
            return await self._handle_system_incident_workflow(analysis, user_input, user_id, classification_result)
            
        elif classification.intent == IntentType.DATA_QUERY:
            return await self._handle_data_query_workflow(analysis, user_input, user_id, classification_result)
            
        elif classification.intent == IntentType.INFORMATION_REQUEST:
            return await self._handle_information_workflow(analysis, user_input, user_id, classification_result)
            
        elif classification.intent == IntentType.RESEARCH_QUERY:  # NEW
            return await self._handle_research_workflow(analysis, user_input, user_id, classification_result)
            
        else:
            return {
                "workflow": "unknown",
                "classification_result": classification_result,
                "message": "I'm not sure how to help with that. Can you provide more details?",
                "suggestions": [
                    "Try: 'The system is not working'",
                    "Try: 'Find claim number 1-ABCD'",
                    "Try: 'How do I upload claims?'",
                    "Try: 'What are transformer models?'"  # NEW
                ]
            }
    
    async def _handle_system_incident_workflow(self, analysis: Dict[str, Any], user_input: str, 
                                             user_id: str, classification_result: Dict[str, Any]) -> Dict[str, Any]:
        """Handle system incidents: Claude analysis → MCP ticket creation"""
        
        print("🚨 Step 2: System Incident Workflow")
        
        # Use Claude's analysis to create MCP ticket
        ticket_result = await self.mcp_client.create_incident_ticket(
            title=analysis.get("ticket_summary", user_input[:80]),
            description=analysis.get("ticket_description", user_input),
            priority=analysis.get("severity", "medium").lower(),
            assignment_group=analysis.get("assignment_group", "IT Support"),
            caller_id=user_id
        )
        
        if ticket_result.get("success"):
            ticket_data = ticket_result.get("result", {})
            
            return {
                "workflow": "system_incident",
                "classification_result": classification_result,
                "mcp_result": ticket_result,
                "success": True,
                "message": f"""
🚨 **Critical System Incident - Ticket Created**

**Analysis Results:**
• **Severity:** {analysis.get('severity', 'Unknown').upper()}
• **System:** {analysis.get('affected_system', 'Unknown').title()}
• **Impact:** {analysis.get('business_impact', 'System functionality affected')}

**Ticket Created:**
• **Ticket Number:** {ticket_data.get('ticket_number', 'Unknown')}
• **Priority:** {analysis.get('severity', 'medium').upper()}
• **Assigned to:** {analysis.get('assignment_group', 'IT Support')}
• **Expected Response:** {ticket_data.get('sla_response_time', '24 hours')}

**Immediate Actions:**
{chr(10).join(f"• {action}" for action in analysis.get('immediate_actions', ['Ticket created', 'Team notified']))}

You'll receive email updates as the incident progresses.
                """.strip()
            }
        else:
            return {
                "workflow": "system_incident",
                "classification_result": classification_result,
                "mcp_result": ticket_result,
                "success": False,
                "message": f"""
❌ **Incident Analysis Complete - Ticket Creation Failed**

**Analysis Results:**
• **Severity:** {analysis.get('severity', 'Unknown').upper()}
• **Impact:** {analysis.get('business_impact', 'System functionality affected')}

**Error:** {ticket_result.get('error', 'Unknown error')}

**Manual Steps:**
• Contact {analysis.get('assignment_group', 'IT Support')} directly
• Reference this analysis in your communication
• Escalate if critical: {"Yes" if analysis.get('escalation_needed') else "No"}
                """.strip()
            }
    
    async def _handle_data_query_workflow(self, analysis: Dict[str, Any], user_input: str,
                                         user_id: str, classification_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhanced workflow with LLM-based data manipulation detection
        """
        
        print("🔍 Step 2: Data Query Workflow with LLM Detection")
        
        # Step 1: Use LLM to analyze the request
        manipulation_analysis = await self.detect_data_manipulation_with_llm(user_input)
        
        print(f"   🤖 LLM Analysis: {manipulation_analysis['operation_type']} operation")
        print(f"   📝 Is Manipulation: {manipulation_analysis['is_manipulation']}")
        
        # Step 2: Route based on operation type
        if manipulation_analysis["is_manipulation"] and manipulation_analysis["requires_approval"]:
            # This is a data manipulation request - create approval ticket
            print("🎫 Step 3: Data manipulation detected - Creating approval request")
            
            ticket_result = await self._create_data_manipulation_approval(
                user_input, user_id, manipulation_analysis
            )
            
            return {
                "workflow": "data_manipulation_approval",
                "classification_result": classification_result,
                "manipulation_analysis": manipulation_analysis,
                "ticket_result": ticket_result,
                "success": True,
                "message": f"""
🔒 **Data Manipulation Request - Admin Approval Required**

**Operation:** {manipulation_analysis['operation_type'].upper()}
**Entity:** {manipulation_analysis['entity_type'].title()} - {manipulation_analysis['entity_identifier']}
**Change:** {manipulation_analysis['target_field']} from '{manipulation_analysis['old_value']}' to '{manipulation_analysis['new_value']}'

**SQL Intent:** {manipulation_analysis['sql_intent']}

✅ **Approval Request Created:**
• **Ticket Number:** {ticket_result.get("result", {}).get("request_number", "Unknown")}
• **Assigned to:** Data Administration Team
• **Priority:** Medium
• **Expected Response:** 24-48 hours

**⚠️ Important:** This operation will modify live data and requires admin approval for safety.

You'll receive an email notification once the request is reviewed.
                """.strip()
            }
        
        else:
            # This is a search operation - proceed with normal database search
            print("🔍 Step 3: Search operation - Proceeding with database search")
            
            # Check if this is a "missing data" query for ticket creation
            is_missing_query = self.is_missing_data_query(user_input)
            
            search_result = await self.mcp_client.search_database(
                query=user_input,
                table_hint=analysis.get("target_system", "").replace("_db", "") if analysis else None
            )
            
            if search_result.get("success"):
                results = search_result.get("results", [])
                
                if results and len(results) > 0:
                    return {
                        "workflow": "database_search",
                        "classification_result": classification_result,
                        "mcp_result": search_result,
                        "success": True,
                        "message": f"""
🔍 **Database Search Results**

**Query:** {user_input}
**Results Found:** {len(results)}

**Data Preview:**
{self._format_search_results(results[:3])}

{"... and " + str(len(results) - 3) + " more results" if len(results) > 3 else ""}
                        """.strip()
                    }
                
                elif is_missing_query:
                    # Missing data - create investigation ticket
                    ticket_result = await self._create_missing_data_ticket(user_input, user_id, search_result)
                    
                    return {
                        "workflow": "missing_data_investigation", 
                        "classification_result": classification_result,
                        "search_result": search_result,
                        "ticket_result": ticket_result,
                        "success": True,
                        "message": f"""
📋 **Missing Data Investigation Initiated**

**Query:** {user_input}
**Status:** No records found in database

✅ **Investigation Ticket Created:**
• **Ticket Number:** {ticket_result.get("result", {}).get("request_number", "Unknown")}
• **Assigned to:** {self._get_assignment_group(user_input)}

The appropriate team will investigate and contact you with findings.
                        """.strip()
                    }
                
                else:
                    # Regular search with no results
                    return {
                        "workflow": "database_search",
                        "classification_result": classification_result,
                        "mcp_result": search_result,
                        "success": True,
                        "message": f"""
🔍 **Database Search Complete**

**Query:** {user_input}
**Results Found:** 0

No matching records found. Try:
• Checking spelling of search terms
• Using partial names or numbers
• Broadening your search criteria
                        """.strip()
                    }
            
            else:
                # Search failed
                return {
                    "workflow": "database_search", 
                    "classification_result": classification_result,
                    "mcp_result": search_result,
                    "success": False,
                    "message": f"""
❌ **Database Search Failed**

**Query:** {user_input}
**Error:** {search_result.get('error', 'Unknown error')}

Please try again or contact support.
                    """.strip()
                }
    
    # NEW: Research Query Workflow Handler
    async def _handle_research_workflow(self, analysis: Dict[str, Any], user_input: str,
                                       user_id: str, classification_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        NEW: Handle research queries using Research MCP server
        """
        
        print("📊 Step 2: Research Query Workflow")
        
        # Extract analysis type from Claude's analysis
        analysis_type = analysis.get("analysis_depth", "comprehensive") if analysis else "comprehensive"
        
        # Call the research workflow from MCP client
        research_result = await self.mcp_client.handle_research_query_workflow(
            query=user_input,
            user_id=user_id,
            analysis_type=analysis_type
        )
        
        if research_result.get("success", False):
            return {
                "workflow": "research_query",
                "classification_result": classification_result,
                "research_result": research_result,
                "success": True,
                "message": research_result.get("message", "Research completed successfully.")
            }
        else:
            # Research failed - provide fallback response
            return {
                "workflow": "research_query",
                "classification_result": classification_result,
                "research_result": research_result,
                "success": False,
                "message": f"""
❌ **Research Query Processing Failed**

**Query:** {user_input}
**Error:** {research_result.get('error', 'Research system unavailable')}

**Alternative Resources:**
• Academic databases (IEEE, ACM, arXiv)
• Company knowledge base
• Technical documentation
• Subject matter experts

**Next Steps:**
• Try rephrasing your research question
• Check if research MCP server is running
• Contact research support team

Would you like me to help you rephrase your research question?
                """.strip()
            }
    
    async def _create_data_manipulation_approval(self, user_input: str, user_id: str, 
                                                manipulation_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create approval ticket for data manipulation requests
        """
        
        operation = manipulation_analysis["operation_type"].upper()
        entity_type = manipulation_analysis["entity_type"].title()
        entity_id = manipulation_analysis["entity_identifier"]
        
        return await self.mcp_client.create_service_request(
            title=f"Data {operation} Approval: {entity_type} {entity_id}",
            description=f"""
**Data Manipulation Approval Request**

**Original Request:** {user_input}
**Requested by:** {user_id}
**Operation Type:** {operation}

**Entity Details:**
• Type: {entity_type}
• Identifier: {entity_id}
• Field: {manipulation_analysis["target_field"]}
• Current Value: {manipulation_analysis["old_value"]}
• New Value: {manipulation_analysis["new_value"]}

**SQL Intent:** 
{manipulation_analysis["sql_intent"]}

**Risk Assessment:**
• Data manipulation operation detected
• Requires admin review for data integrity
• Backup recommended before execution

**Approval Required:**
Please review this request and either:
1. ✅ Approve and execute the change
2. ❌ Reject with reason
3. 🔄 Request clarification from user

**Note:** All data manipulation operations require approval for safety and audit compliance.
            """.strip(),
            priority="medium",
            assignment_group="Data Administration Team",
            caller_id=user_id,
            category="Data Manipulation Approval"
        )
    
    async def _create_missing_data_ticket(self, user_input: str, user_id: str, search_result: Dict) -> Dict:
        """Create investigation ticket for missing data"""
        
        assignment_group = self._get_assignment_group(user_input)
        
        return await self.mcp_client.create_service_request(
            title=f"Missing Data Investigation: {user_input[:60]}{'...' if len(user_input) > 60 else ''}",
            description=f"""
**Missing Data Investigation Request**

**Original Query:** {user_input}
**Reported by:** {user_id}
**Search Result:** No matching records found

**Database Search Details:**
• SQL Generated: {search_result.get('sql_generated', 'N/A')}
• Tables Searched: {', '.join(search_result.get('tables_searched', ['Unknown']))}
• Search Confidence: {search_result.get('confidence', 'N/A')}

**Investigation Required:**
Please investigate why the requested data is not available and provide status to the user.

**Possible Actions:**
• Verify data entry status
• Check data synchronization
• Review access permissions
• Contact source system owners
            """.strip(),
            priority="medium",
            assignment_group=assignment_group,
            caller_id=user_id,
            category="Missing Data Investigation"
        )

    def _get_assignment_group(self, user_input: str) -> str:
        """Determine appropriate assignment group based on query content"""
        
        query_lower = user_input.lower()
        
        if "claim" in query_lower:
            return "Brazil Claims Team"
        elif "engine" in query_lower:
            return "Engine Data Team"
        elif "warranty" in query_lower:
            return "Warranty Support Team"
        else:
            return "Data Support Team"
    
    async def _handle_information_workflow(self, analysis: Dict[str, Any], user_input: str,
                                         user_id: str, classification_result: Dict[str, Any]) -> Dict[str, Any]:
        """Handle information requests: Return knowledge base info"""
        
        print("📚 Step 2: Information Request Workflow")
        
        # For now, return static information
        # In future, this would call Knowledge Base MCP server
        
        topic = analysis.get("topic_area", "general") if analysis else "general"
        category = analysis.get("info_category", "general") if analysis else "general"
        
        knowledge_responses = {
            "claims": {
                "process": """
📋 **Brazil Claims Upload Process**

**Steps:**
1. **Data Collection:** Gather claim details (customer info, product serial, issue description)
2. **Validation:** Verify claim meets warranty criteria
3. **System Entry:** Upload to reliability system via web portal
4. **Review:** Brazil Claims team reviews within 24-48 hours
5. **Processing:** Approved claims enter payment workflow

**Required Fields:**
• Customer Name and Contact
• Product Serial Number
• Claim Date and Amount
• Issue Description
• Supporting Documentation

**Upload Methods:**
• Web Portal: https://claims.company.com
• Bulk Upload: Excel template available
• API Integration: For automated systems
                """,
                "technical": """
🔧 **Technical Integration Details**

**API Endpoints:**
• POST /api/claims/create - Create new claim
• GET /api/claims/{id} - Retrieve claim details
• PUT /api/claims/{id} - Update claim status

**Database Schema:**
• claims.claim_id (Primary Key)
• claims.customer_info (JSON)
• claims.product_data (Foreign Key)
• claims.status_history (Audit Trail)

**Data Flow:**
1. Claims Portal → API Gateway
2. API Gateway → Validation Service
3. Validation Service → Database
4. Database → Reliability System Sync
                """
            }
        }
        
        if topic in knowledge_responses and category in knowledge_responses[topic]:
            knowledge_content = knowledge_responses[topic][category]
        else:
            knowledge_content = f"""
📚 **Information Request: {topic.title()} - {category.title()}**

I understand you're looking for information about {topic} processes. 

**Available Resources:**
• Internal Documentation Portal
• Process Wiki Pages  
• Training Materials
• Subject Matter Experts

**Recommended Next Steps:**
• Check the internal knowledge base
• Contact the {topic} team directly
• Schedule a training session

For specific technical details, please contact the appropriate team or submit a detailed information request.
            """.strip()
        
        return {
            "workflow": "information_request",
            "classification_result": classification_result,
            "success": True,
            "message": knowledge_content
        }
    
    def _format_search_results(self, results: list) -> str:
        """Format search results for display"""
        
        if not results:
            return "No results found"
        
        formatted = ""
        for i, result in enumerate(results, 1):
            formatted += f"\n**Result {i}:**\n"
            for key, value in result.items():
                if key not in ['sys_id', 'last_updated']:  # Skip technical fields
                    formatted += f"  • {key.replace('_', ' ').title()}: {value}\n"
        
        return formatted.strip()

# Example usage for testing
async def test_complete_workflow():
    """Test the complete workflow including NEW research queries"""
    
    # Replace with your actual Claude API key
    claude_api_key = "******"
    
    workflow = CompleteChatbotWorkflow(claude_api_key)
    
    test_cases = [
        "The downstream integration to Warranty system is not working",
        "I am missing Brazil claim number '1-ABCD' in the Claims report",
        "Update engine serial 12345678 model from X10 to X15",
        "Can I get more information on how the Brazil claims are uploaded to reliability system?",
        "What are transformer models in machine learning?",  # NEW
        "Compare LSTM and transformer architectures for NLP",  # NEW
        "Analyze recent advances in neural machine translation"  # NEW
    ]
    
    for test_input in test_cases:
        print(f"\n{'='*80}")
        print(f"Testing: {test_input}")
        print('='*80)
        
        result = await workflow.process_complete_workflow(test_input, "test.user@company.com")
        
        print(f"Workflow: {result['workflow']}")
        print(f"Success: {result.get('success', 'N/A')}")
        print(f"Message:\n{result['message']}")

if __name__ == "__main__":
    asyncio.run(test_complete_workflow())