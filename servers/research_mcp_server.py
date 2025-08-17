#!/usr/bin/env python3
"""
Research Paper MCP Server - Production Version
Direct integration with your working EnhancedMultiHopRAG system
No fallbacks or dummy responses - production ready
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import uvicorn

# Import your WORKING RAG system directly
from enhanced_rag_system import EnhancedMultiHopRAG

# Global variables
app = FastAPI(title="Research Paper MCP Server", version="1.0.0")
rag_system = None

@app.on_event("startup")
async def startup_event():
    """Initialize the RAG system on startup"""
    global rag_system
    try:
        rag_system = EnhancedMultiHopRAG()
        logging.basicConfig(level=logging.INFO)
        logging.info("✅ Research Paper MCP Server started with real RAG system")
    except Exception as e:
        logging.error(f"❌ Failed to initialize RAG system: {e}")
        raise e

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global rag_system
    if rag_system:
        rag_system.close()
    logging.info("🔄 Research Paper MCP Server shut down")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "research_paper_mcp",
        "rag_system": "active" if rag_system else "unavailable",
        "version": "1.0.0"
    }

# Direct tool call endpoint (matching your other MCP servers)
@app.post("/tools/call")
async def call_tool_direct(request: dict):
    """Direct tool call endpoint matching ServiceNow/Database MCP pattern"""
    
    try:
        tool_name = request.get("name")
        arguments = request.get("arguments", {})
        
        logging.info(f"📞 Research tool call: {tool_name}")
        
        # Route to appropriate tool handler
        if tool_name == "search_research_papers":
            result = await handle_search_research_papers(arguments)
        elif tool_name == "analyze_research_topic":
            result = await handle_analyze_research_topic(arguments)
        elif tool_name == "find_paper_relationships":
            result = await handle_find_paper_relationships(arguments)
        else:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}",
                "available_tools": ["search_research_papers", "analyze_research_topic", "find_paper_relationships"]
            }
        
        return result
        
    except Exception as e:
        logging.error(f"Error in tool call: {e}")
        return {
            "success": False,
            "error": f"Tool call failed: {str(e)}"
        }

# Tool Handlers - Direct integration with your RAG system
async def handle_search_research_papers(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Search research papers using your real RAG system"""
    
    query = arguments.get("query", "")
    max_results = arguments.get("max_results", 10)
    include_reasoning = arguments.get("include_reasoning", True)
    
    if not query:
        return {
            "success": False,
            "error": "Query parameter is required"
        }
    
    global rag_system
    if not rag_system:
        return {
            "success": False,
            "error": "RAG system not initialized"
        }
    
    try:
        # Use your actual RAG system
        result = rag_system.query(query)
        
        response = {
            "success": True,
            "query": query,
            "answer": result["answer"],
            "summary": {
                "entities_found": len(result["entities_used"]),
                "reasoning_paths": result["reasoning_paths_count"],
                "context_triples": result["context_triples_count"]
            }
        }
        
        if include_reasoning:
            response["reasoning_details"] = {
                "entities_used": result["entities_used"],
                "top_reasoning_paths": result["top_reasoning_paths"][:5],
                "context_triples": result["context_triples"][:10]
            }
        
        logging.info(f"✅ Research search completed: {len(result['entities_used'])} entities, {result['reasoning_paths_count']} paths")
        return response
        
    except Exception as e:
        logging.error(f"Error in search_research_papers: {e}")
        return {
            "success": False,
            "error": f"Search failed: {str(e)}"
        }

async def handle_analyze_research_topic(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze research topic using your real RAG system"""
    
    topic = arguments.get("topic", "")
    analysis_type = arguments.get("analysis_type", "comprehensive")
    
    if not topic:
        return {
            "success": False,
            "error": "Topic parameter is required"
        }
    
    global rag_system
    if not rag_system:
        return {
            "success": False,
            "error": "RAG system not initialized"
        }
    
    try:
        # Create analysis-specific query based on type
        if analysis_type == "technical":
            query = f"What are the technical details, methodologies, and implementation aspects of {topic}?"
        elif analysis_type == "comparative":
            query = f"Compare different approaches, methods, and techniques related to {topic}"
        else:  # comprehensive
            query = f"Provide a comprehensive overview of {topic} including background, methods, current research, and applications"
        
        # Use your actual RAG system
        result = rag_system.query(query)
        
        return {
            "success": True,
            "topic": topic,
            "analysis_type": analysis_type,
            "analysis": result["answer"],
            "key_entities": result["entities_used"],
            "research_depth": {
                "reasoning_paths": result["reasoning_paths_count"],
                "knowledge_connections": result["context_triples_count"]
            },
            "reasoning_paths": result["top_reasoning_paths"][:3],
            "supporting_triples": result["context_triples"][:5]
        }
        
    except Exception as e:
        logging.error(f"Error in analyze_research_topic: {e}")
        return {
            "success": False,
            "error": f"Analysis failed: {str(e)}"
        }

async def handle_find_paper_relationships(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Find relationships between research concepts using your real RAG system"""
    
    concept1 = arguments.get("concept1", "")
    concept2 = arguments.get("concept2", "")
    max_hops = arguments.get("max_hops", 3)
    
    if not concept1 or not concept2:
        return {
            "success": False,
            "error": "Both concept1 and concept2 parameters are required"
        }
    
    global rag_system
    if not rag_system:
        return {
            "success": False,
            "error": "RAG system not initialized"
        }
    
    try:
        # Create relationship-focused query
        query = f"What is the relationship between {concept1} and {concept2}? How are they connected in research? What are the pathways that link these concepts?"
        
        # Use your actual RAG system
        result = rag_system.query(query)
        
        # Filter reasoning paths that contain both concepts
        relevant_paths = []
        for path in result.get("top_reasoning_paths", []):
            path_str = path.get("path_string", "").lower()
            if concept1.lower() in path_str and concept2.lower() in path_str:
                relevant_paths.append(path)
        
        # Filter context triples that involve either concept
        relevant_triples = []
        for triple in result.get("context_triples", []):
            triple_lower = triple.lower()
            if concept1.lower() in triple_lower or concept2.lower() in triple_lower:
                relevant_triples.append(triple)
        
        return {
            "success": True,
            "concept1": concept1,
            "concept2": concept2,
            "max_hops": max_hops,
            "relationship_analysis": result["answer"],
            "direct_connections": len(relevant_paths),
            "connection_paths": relevant_paths[:5],
            "related_entities": result["entities_used"],
            "supporting_triples": relevant_triples[:10],
            "total_reasoning_paths": result["reasoning_paths_count"]
        }
        
    except Exception as e:
        logging.error(f"Error in find_paper_relationships: {e}")
        return {
            "success": False,
            "error": f"Relationship search failed: {str(e)}"
        }

# List available tools (matching other MCP servers)
@app.get("/tools/list")
async def list_tools():
    """List available tools"""
    return {
        "tools": [
            {
                "name": "search_research_papers",
                "description": "Search research papers using multi-hop reasoning and knowledge graph",
                "parameters": {
                    "query": "Research question or topic",
                    "max_results": "Maximum results (default: 10)",
                    "include_reasoning": "Include reasoning details (default: true)"
                }
            },
            {
                "name": "analyze_research_topic",
                "description": "Deep analysis of research topics using knowledge graph relationships",
                "parameters": {
                    "topic": "Research topic to analyze",
                    "analysis_type": "comprehensive|technical|comparative (default: comprehensive)"
                }
            },
            {
                "name": "find_paper_relationships",
                "description": "Find relationships between research concepts using multi-hop reasoning",
                "parameters": {
                    "concept1": "First research concept",
                    "concept2": "Second research concept",
                    "max_hops": "Maximum reasoning hops (default: 3)"
                }
            }
        ]
    }

# Test endpoint to verify RAG system is working
@app.get("/test/simple-query")
async def test_simple_query(q: str = "What are transformers?"):
    """Test endpoint to verify RAG system is working"""
    global rag_system
    if not rag_system:
        return {"error": "RAG system not initialized"}
    
    try:
        result = rag_system.query(q)
        return {
            "test": "success",
            "query": q,
            "entities_found": len(result["entities_used"]),
            "reasoning_paths": result["reasoning_paths_count"],
            "answer_preview": result["answer"][:200] + "..." if len(result["answer"]) > 200 else result["answer"]
        }
    except Exception as e:
        return {"test": "failed", "error": str(e)}

if __name__ == "__main__":
    print("🚀 Starting Production Research Paper MCP Server...")
    print("📚 Real RAG integration - No fallbacks or dummy responses")
    print("🔗 Available at: http://localhost:8084")
    print("🔧 Tools endpoint: http://localhost:8084/tools/call")
    print("🩺 Health check: http://localhost:8084/health")
    print("🧪 Test query: http://localhost:8084/test/simple-query?q=your_question")
    
    uvicorn.run(
        "research_mcp_server:app",
        host="0.0.0.0",
        port=8084,
        reload=True,
        log_level="info"
    )