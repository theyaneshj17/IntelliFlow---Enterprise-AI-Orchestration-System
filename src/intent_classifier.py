import anthropic
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class IntentType(Enum):
    SYSTEM_INCIDENT = "system_incident"      # System down, not working, broken
    DATA_QUERY = "data_query"               # Missing values, DB queries, updates
    INFORMATION_REQUEST = "information_request"  # Documentation, process info
    RESEARCH_QUERY = "research_query"       # Research papers, academic queries
    UNKNOWN = "unknown"

@dataclass
class IntentClassification:
    intent: IntentType
    confidence: float
    reasoning: str
    keywords_matched: List[str]
    urgency_indicators: List[str]

class IntentClassifier:
    def __init__(self, claude_api_key: str):
        self.client = anthropic.Anthropic(api_key=claude_api_key)
        
    def classify_intent(self, user_input: str) -> IntentClassification:
        """
        Enhanced intent classification with research query support
        """
        
        classification_prompt = f"""
        You are an expert intent classifier for enterprise IT support and research assistance. Classify the user input into one of these categories:

        **Categories:**
        1. **SYSTEM_INCIDENT**: System outages, not working, broken, down, failed, critical issues
        2. **DATA_QUERY**: Missing data, database queries, updates, specific record searches, attribute changes  
        3. **INFORMATION_REQUEST**: Documentation, process questions, how-to guides, design details
        4. **RESEARCH_QUERY**: Academic papers, machine learning, algorithms, technical research, literature analysis

        **User Input:** "{user_input}"

        Analyze and return ONLY valid JSON:
        {{
            "intent": "system_incident|data_query|information_request|research_query|unknown",
            "confidence": 0.0-1.0,
            "reasoning": "Brief explanation of classification",
            "keywords_matched": ["keyword1", "keyword2"],
            "urgency_indicators": ["indicator1", "indicator2"]
        }}

        **Classification Guidelines:**
        - "not working", "down", "broken", "failed", "critical" → SYSTEM_INCIDENT (high confidence)
        - "missing", "update", "search", "claim number", "serial number" → DATA_QUERY (high confidence)  
        - "how", "what is", "information on", "design", "process" → INFORMATION_REQUEST (high confidence)
        - "research", "paper", "machine learning", "algorithm", "neural network", "transformer", "analysis of", "compare algorithms" → RESEARCH_QUERY (high confidence)
        - Mixed signals → lower confidence score
        - Confidence > 0.8 = high confidence routing
        - Confidence 0.5-0.8 = medium confidence, may need clarification
        - Confidence < 0.5 = low confidence, ask for clarification
        """

        try:
            response = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=500,
                temperature=0.1,
                messages=[{"role": "user", "content": classification_prompt}]
            )
            
            result = json.loads(response.content[0].text)
            
            return IntentClassification(
                intent=IntentType(result["intent"]),
                confidence=result["confidence"],
                reasoning=result["reasoning"],
                keywords_matched=result["keywords_matched"],
                urgency_indicators=result["urgency_indicators"]
            )
            
        except Exception as e:
            print(f"Classification error: {e}")
            return IntentClassification(
                intent=IntentType.UNKNOWN,
                confidence=0.3,
                reasoning="Classification failed",
                keywords_matched=[],
                urgency_indicators=[]
            )

class SystemIncidentHandler:
    def __init__(self, claude_api_key: str):
        self.client = anthropic.Anthropic(api_key=claude_api_key)
        
    def analyze_incident(self, user_input: str) -> Dict:
        """
        Specialized analysis for system incidents - focus on criticality and impact
        """
        
        incident_prompt = f"""
        You are a critical incident analyzer. Analyze this system incident report:

        **User Input:** "{user_input}"

        Return JSON analysis:
        {{
            "severity": "critical|high|medium|low",
            "affected_system": "warranty|claims|engine|integration|general",
            "business_impact": "Brief impact description",
            "urgency_justification": "Why this severity level",
            "immediate_actions": ["action1", "action2"],
            "assignment_group": "team name",
            "escalation_needed": true|false,
            "estimated_downtime": "time estimate or unknown",
            "ticket_summary": "Concise ticket title",
            "ticket_description": "Detailed technical description"
        }}

        **Severity Guidelines:**
        - CRITICAL: Complete system down, all users affected, business-critical
        - HIGH: Major functionality broken, significant user impact  
        - MEDIUM: Partial functionality issues, workaround available
        - LOW: Minor issues, minimal impact

        Focus on business impact and technical details for ServiceNow ticket creation.
        """

        try:
            response = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=800,
                temperature=0.1,
                messages=[{"role": "user", "content": incident_prompt}]
            )
            
            return json.loads(response.content[0].text)
            
        except Exception as e:
            return self._fallback_incident_analysis(user_input)
    
    def _fallback_incident_analysis(self, user_input: str) -> Dict:
        return {
            "severity": "high",
            "affected_system": "general", 
            "business_impact": "System functionality impacted",
            "urgency_justification": "User reported system not working",
            "immediate_actions": ["Create incident ticket", "Notify on-call team"],
            "assignment_group": "IT Support Team",
            "escalation_needed": True,
            "estimated_downtime": "unknown",
            "ticket_summary": f"System Issue: {user_input[:50]}",
            "ticket_description": f"User reported: {user_input}"
        }

class DataQueryHandler:
    def __init__(self, claude_api_key: str):
        self.client = anthropic.Anthropic(api_key=claude_api_key)
        
    def analyze_data_query(self, user_input: str) -> Dict:
        """
        Specialized analysis for data queries - focus on DB operations and missing data
        """
        
        data_query_prompt = f"""
        You are a data query analyzer. Analyze this data-related request:

        **User Input:** "{user_input}"

        Return JSON analysis:
        {{
            "query_type": "search|update|insert|delete|verification",
            "target_system": "claims_db|warranty_db|engine_db|general_db",
            "data_elements": ["element1", "element2"],
            "search_criteria": {{"field": "value"}},
            "requires_approval": true|false,
            "risk_level": "low|medium|high",
            "sql_intent": "Brief description of what SQL operation would be needed",
            "business_justification": "Why this data operation is needed",
            "next_steps": ["step1", "step2"],
            "estimated_complexity": "simple|moderate|complex"
        }}

        **Query Type Guidelines:**
        - SEARCH: "missing", "find", "lookup", "where is"
        - UPDATE: "change", "update", "modify", "correct"
        - VERIFICATION: "confirm", "check", "validate", "exists"
        - INSERT: "add", "create", "new record"

        Focus on data accuracy, approval requirements, and operational impact.
        """

        try:
            response = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=800,
                temperature=0.1,
                messages=[{"role": "user", "content": data_query_prompt}]
            )
            
            return json.loads(response.content[0].text)
            
        except Exception as e:
            return self._fallback_data_analysis(user_input)
    
    def _fallback_data_analysis(self, user_input: str) -> Dict:
        return {
            "query_type": "search",
            "target_system": "general_db",
            "data_elements": ["unknown"],
            "search_criteria": {},
            "requires_approval": False,
            "risk_level": "low",
            "sql_intent": "Search for requested data",
            "business_justification": "User data inquiry",
            "next_steps": ["Verify user permissions", "Execute search"],
            "estimated_complexity": "moderate"
        }

class InformationRequestHandler:
    def __init__(self, claude_api_key: str):
        self.client = anthropic.Anthropic(api_key=claude_api_key)
        
    def analyze_info_request(self, user_input: str) -> Dict:
        """
        Specialized analysis for information requests - focus on knowledge base and documentation
        """
        
        info_request_prompt = f"""
        You are a knowledge base analyzer. Analyze this information request:

        **User Input:** "{user_input}"

        Return JSON analysis:
        {{
            "info_category": "process|technical|policy|training|troubleshooting",
            "topic_area": "claims|warranty|engine|integration|general",
            "specificity": "general|specific|detailed",
            "knowledge_sources": ["confluence", "wiki", "documentation", "sme"],
            "urgency": "immediate|routine|reference",
            "response_format": "text|diagram|flowchart|step_by_step",
            "estimated_response_time": "minutes|hours|days",
            "follow_up_likely": true|false,
            "suggested_resources": ["resource1", "resource2"],
            "complexity_level": "basic|intermediate|advanced"
        }}

        **Category Guidelines:**
        - PROCESS: "how to", "steps", "procedure", "workflow"
        - TECHNICAL: "design", "architecture", "integration", "data flow"  
        - POLICY: "guidelines", "rules", "compliance", "approval"
        - TROUBLESHOOTING: "error", "issue", "problem", "fix"

        Focus on finding the right knowledge source and response format.
        """

        try:
            response = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=800,
                temperature=0.1,
                messages=[{"role": "user", "content": info_request_prompt}]
            )
            
            return json.loads(response.content[0].text)
            
        except Exception as e:
            return self._fallback_info_analysis(user_input)
    
    def _fallback_info_analysis(self, user_input: str) -> Dict:
        return {
            "info_category": "general",
            "topic_area": "general",
            "specificity": "general",
            "knowledge_sources": ["documentation"],
            "urgency": "routine",
            "response_format": "text",
            "estimated_response_time": "minutes",
            "follow_up_likely": True,
            "suggested_resources": ["Knowledge Base"],
            "complexity_level": "basic"
        }

class ResearchQueryHandler:
    """NEW: Handler for research paper queries"""
    
    def __init__(self, claude_api_key: str):
        self.client = anthropic.Anthropic(api_key=claude_api_key)
        
    def analyze_research_query(self, user_input: str) -> Dict:
        """
        Specialized analysis for research queries - focus on academic content and analysis type
        """
        
        research_prompt = f"""
        You are a research query analyzer. Analyze this research-related request:

        **User Input:** "{user_input}"

        Return JSON analysis:
        {{
            "research_type": "paper_search|topic_analysis|comparison|methodology|survey",
            "subject_area": "machine_learning|nlp|computer_vision|ai|general_cs|other",
            "analysis_depth": "overview|detailed|comprehensive|technical",
            "query_complexity": "simple|moderate|complex|expert",
            "expected_output": "summary|detailed_analysis|comparison_table|technical_explanation",
            "knowledge_graph_needed": true|false,
            "multi_hop_reasoning": true|false,
            "academic_level": "undergraduate|graduate|research|industry",
            "time_sensitivity": "immediate|routine|background_research",
            "follow_up_questions": ["question1", "question2"],
            "suggested_approach": "direct_search|multi_source_analysis|concept_mapping"
        }}

        **Research Type Guidelines:**
        - PAPER_SEARCH: "find papers", "literature on", "research about"
        - TOPIC_ANALYSIS: "analyze", "explain", "what is", "overview of"
        - COMPARISON: "compare", "difference between", "vs", "versus"
        - METHODOLOGY: "how does X work", "algorithm details", "technique"
        - SURVEY: "state of the art", "recent advances", "trends in"

        Focus on academic rigor and research methodology.
        """

        try:
            response = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=800,
                temperature=0.1,
                messages=[{"role": "user", "content": research_prompt}]
            )
            
            return json.loads(response.content[0].text)
            
        except Exception as e:
            return self._fallback_research_analysis(user_input)
    
    def _fallback_research_analysis(self, user_input: str) -> Dict:
        return {
            "research_type": "topic_analysis",
            "subject_area": "general_cs",
            "analysis_depth": "overview",
            "query_complexity": "moderate",
            "expected_output": "summary",
            "knowledge_graph_needed": True,
            "multi_hop_reasoning": True,
            "academic_level": "graduate",
            "time_sensitivity": "routine",
            "follow_up_questions": ["Can you provide more specific details?"],
            "suggested_approach": "direct_search"
        }

class SmartChatbotOrchestrator:
    def __init__(self, claude_api_key: str):
        self.intent_classifier = IntentClassifier(claude_api_key)
        self.incident_handler = SystemIncidentHandler(claude_api_key)
        self.data_handler = DataQueryHandler(claude_api_key)
        self.info_handler = InformationRequestHandler(claude_api_key)
        self.research_handler = ResearchQueryHandler(claude_api_key)  # NEW
        
        self.CONFIDENCE_THRESHOLD = 0.7
        
    def process_user_input(self, user_input: str, user_id: str) -> Dict:
        """
        Enhanced orchestrator - now handles research queries too
        """
        
        print(f"🎯 Classifying intent for: '{user_input}'")
        
        # Step 1: Intent Classification
        classification = self.intent_classifier.classify_intent(user_input)
        
        print(f"📊 Intent: {classification.intent.value} | Confidence: {classification.confidence:.2f}")
        print(f"🔍 Keywords: {classification.keywords_matched}")
        
        result = {
            "user_input": user_input,
            "classification": classification,
            "specialized_analysis": None,
            "action_taken": None,
            "response_message": "",
            "confidence_level": "high" if classification.confidence > 0.8 else "medium" if classification.confidence > 0.5 else "low"
        }
        
        # Step 2: Route to specialized handler based on confidence
        if classification.confidence < 0.5:
            result["response_message"] = self._handle_low_confidence(user_input, classification)
            result["action_taken"] = "clarification_requested"
            
        elif classification.intent == IntentType.SYSTEM_INCIDENT:
            analysis = self.incident_handler.analyze_incident(user_input)
            result["specialized_analysis"] = analysis
            result["response_message"] = self._format_incident_response(analysis)
            result["action_taken"] = "incident_ticket_created"
            
        elif classification.intent == IntentType.DATA_QUERY:
            analysis = self.data_handler.analyze_data_query(user_input)
            result["specialized_analysis"] = analysis
            result["response_message"] = self._format_data_query_response(analysis)
            result["action_taken"] = "data_operation_initiated"
            
        elif classification.intent == IntentType.INFORMATION_REQUEST:
            analysis = self.info_handler.analyze_info_request(user_input)
            result["specialized_analysis"] = analysis
            result["response_message"] = self._format_info_response(analysis)
            result["action_taken"] = "knowledge_search_performed"
            
        elif classification.intent == IntentType.RESEARCH_QUERY:  # NEW
            analysis = self.research_handler.analyze_research_query(user_input)
            result["specialized_analysis"] = analysis
            result["response_message"] = self._format_research_response(analysis)
            result["action_taken"] = "research_analysis_initiated"
            
        else:
            result["response_message"] = "I'm not sure how to help with that. Can you provide more details?"
            result["action_taken"] = "general_fallback"
        
        return result
    
    def _handle_low_confidence(self, user_input: str, classification: IntentClassification) -> str:
        return f"""
        I'm not entirely sure how to categorize your request (confidence: {classification.confidence:.1f}).
        
        Could you help me understand if you're asking about:
        1. 🚨 A **system issue** (something not working/broken)
        2. 🔍 A **data question** (missing records, updates, searches)  
        3. 📚 An **information request** (documentation, processes)
        4. 📊 A **research query** (academic papers, algorithms, analysis)
        
        This will help me assist you better!
        """
    
    def _format_incident_response(self, analysis: Dict) -> str:
        return f"""
        🚨 **Critical System Incident Detected**
        
        **Severity:** {analysis['severity'].upper()}
        **System:** {analysis['affected_system'].title()}
        **Impact:** {analysis['business_impact']}
        
        ✅ **Immediate Actions Taken:**
        • Created {analysis['severity']} priority incident ticket
        • Assigned to: {analysis['assignment_group']}
        • {"Escalated to management" if analysis['escalation_needed'] else "Standard response process"}
        
        📋 **Ticket Details:**
        • **Title:** {analysis['ticket_summary']}
        • **Estimated Response:** {self._get_sla_time(analysis['severity'])}
        
        You'll receive updates as the incident progresses. Is there additional context you can provide?
        """
    
    def _format_data_query_response(self, analysis: Dict) -> str:
        approval_msg = "⚠️ **Admin approval required**" if analysis['requires_approval'] else "✅ **No approval needed**"
        
        return f"""
        🔍 **Data Query Request**
        
        **Operation:** {analysis['query_type'].title()}
        **Target System:** {analysis['target_system'].replace('_', ' ').title()}
        **Complexity:** {analysis['estimated_complexity'].title()}
        
        {approval_msg}
        
        📋 **Next Steps:**
        {chr(10).join(f"• {step}" for step in analysis['next_steps'])}
        
        **Business Justification:** {analysis['business_justification']}
        
        Would you like me to proceed with this data operation?
        """
    
    def _format_info_response(self, analysis: Dict) -> str:
        return f"""
        📚 **Information Request**
        
        **Category:** {analysis['info_category'].title()}
        **Topic:** {analysis['topic_area'].title()}
        **Complexity:** {analysis['complexity_level'].title()}
        
        **Recommended Sources:**
        {chr(10).join(f"• {resource}" for resource in analysis['suggested_resources'])}
        
        **Response Format:** {analysis['response_format'].title()}
        **Estimated Time:** {analysis['estimated_response_time']}
        
        Let me search our knowledge base for this information...
        """
    
    def _format_research_response(self, analysis: Dict) -> str:
        """NEW: Format research query response"""
        return f"""
        📊 **Research Query Analysis**
        
        **Research Type:** {analysis['research_type'].replace('_', ' ').title()}
        **Subject Area:** {analysis['subject_area'].replace('_', ' ').title()}
        **Analysis Depth:** {analysis['analysis_depth'].title()}
        **Academic Level:** {analysis['academic_level'].title()}
        
        **Approach:** {analysis['suggested_approach'].replace('_', ' ').title()}
        **Multi-hop Reasoning:** {"Required" if analysis['multi_hop_reasoning'] else "Not needed"}
        **Knowledge Graph:** {"Will be used" if analysis['knowledge_graph_needed'] else "Not required"}
        
        **Expected Output:** {analysis['expected_output'].replace('_', ' ').title()}
        **Time Sensitivity:** {analysis['time_sensitivity'].replace('_', ' ').title()}
        
        🔍 **Processing your research query through our academic knowledge base...**
        
        **Potential Follow-up Questions:**
        {chr(10).join(f"• {q}" for q in analysis.get('follow_up_questions', []))}
        """
    
    def _get_sla_time(self, severity: str) -> str:
        sla_times = {
            "critical": "30 minutes",
            "high": "4 hours", 
            "medium": "24 hours",
            "low": "72 hours"
        }
        return sla_times.get(severity, "24 hours")

# Example Usage
if __name__ == "__main__":
    # Initialize the enhanced orchestrator
    chatbot = SmartChatbotOrchestrator("*******")
    
    # Enhanced test cases including research queries
    test_cases = [
        "The down stream integration to Warranty system is not working",
        "I am missing Brazil claim number '1-ABCD' in the Claims report", 
        "Can I get more information on how the Brazil claims are uploaded to reliability system?",
        "What are transformer models in machine learning?",  # NEW
        "Compare LSTM and transformer architectures",        # NEW
        "Analyze neural machine translation techniques"      # NEW
    ]
    
    for test_input in test_cases:
        print(f"\n{'='*60}")
        result = chatbot.process_user_input(test_input, "test.user@company.com")
        print(result["response_message"])
        print(f"Action: {result['action_taken']} | Confidence: {result['confidence_level']}")