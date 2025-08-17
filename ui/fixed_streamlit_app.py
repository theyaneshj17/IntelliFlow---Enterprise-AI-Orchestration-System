#!/usr/bin/env python3
"""
Fixed Streamlit App with Complete Workflow Integration
NOW INCLUDES: Research Query Support
"""

import streamlit as st
import asyncio
import json

# THIS IS THE KEY - Import the complete workflow
try:
    from complete_chatbot_workflow import CompleteChatbotWorkflow
    WORKFLOW_AVAILABLE = True
except ImportError as e:
    st.error(f"❌ Cannot import complete workflow: {e}")
    WORKFLOW_AVAILABLE = False

def main():
    st.set_page_config(
        page_title="Enterprise IT Support & Research Chatbot",
        page_icon="🤖",
        layout="wide"
    )
    
    st.title("🤖 Enterprise IT Support & Research Chatbot")
    st.markdown("**Complete Workflow: Intent Classification + MCP Integration + Research**")
    
    if not WORKFLOW_AVAILABLE:
        st.error("❌ Complete workflow not available. Check imports.")
        return
    
    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        claude_api_key = st.text_input(
            "Claude API Key",
            type="password",
            value="******",
            help="Your Claude API key for intent classification"
        )
        
        user_id = st.text_input(
            "User ID",
            value="test.user@company.com",
            help="Your user identifier"
        )
        
        st.markdown("---")
        st.markdown("**Server Status**")
        
        # Quick server status check
        if st.button("🔍 Check Servers"):
            try:
                import requests
                
                # Check ServiceNow server
                try:
                    response = requests.get("http://localhost:8082/health", timeout=3)
                    if response.status_code == 200:
                        st.success("✅ ServiceNow Server (8082)")
                    else:
                        st.error("❌ ServiceNow Server (8082)")
                except:
                    st.error("❌ ServiceNow Server (8082)")
                
                # Check Database server
                try:
                    response = requests.get("http://localhost:8083/health", timeout=3)
                    if response.status_code == 200:
                        st.success("✅ Database Server (8083)")
                    else:
                        st.error("❌ Database Server (8083)")
                except:
                    st.error("❌ Database Server (8083)")
                
                # NEW: Check Research server
                try:
                    response = requests.get("http://localhost:8084/health", timeout=3)
                    if response.status_code == 200:
                        st.success("✅ Research Server (8084)")
                    else:
                        st.error("❌ Research Server (8084)")
                except:
                    st.error("❌ Research Server (8084)")
                    
            except ImportError:
                st.warning("Install requests: pip install requests")
    
    # Main chat interface
    if not claude_api_key:
        st.warning("⚠️ Please enter your Claude API key to continue.")
        return
    
    # Initialize session state
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    # Chat interface
    st.header("💬 Chat Interface")
    
    # Display chat history
    for message in st.session_state.chat_history:
        if message["role"] == "user":
            st.chat_message("user").write(message["content"])
        else:
            st.chat_message("assistant").markdown(message["content"])
            
            # Show workflow details in expander
            if "workflow_details" in message:
                with st.expander("🔍 Workflow Details"):
                    st.json(message["workflow_details"])
    
    # Chat input
    if prompt := st.chat_input("Type your message here..."):
        # Add user message
        st.session_state.chat_history.append({
            "role": "user",
            "content": prompt
        })
        
        # Show user message
        st.chat_message("user").write(prompt)
        
        # Process with complete workflow
        with st.chat_message("assistant"):
            with st.spinner("🎯 Analyzing and processing your request..."):
                try:
                    # Initialize complete workflow
                    workflow = CompleteChatbotWorkflow(claude_api_key)
                    
                    # Process the complete workflow
                    result = asyncio.run(workflow.process_complete_workflow(prompt, user_id))
                    
                    # Display the response
                    st.markdown(result["message"])
                    
                    # Show workflow summary
                    workflow_type = result.get("workflow", "unknown")
                    success_status = result.get("success", "N/A")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Workflow", workflow_type.replace("_", " ").title())
                    
                    with col2:
                        status_emoji = "✅" if success_status else "❌" if success_status is False else "❓"
                        st.metric("Status", f"{status_emoji} {success_status}")
                    
                    with col3:
                        intent = result.get("classification_result", {}).get("classification", {})
                        if hasattr(intent, 'intent'):
                            st.metric("Intent", intent.intent.value.replace("_", " ").title())
                        else:
                            st.metric("Intent", "Unknown")
                    
                    # Add to chat history
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": result["message"],
                        "workflow_details": {
                            "workflow": result.get("workflow"),
                            "success": result.get("success"),
                            "classification": result.get("classification_result", {}),
                            "mcp_result": result.get("mcp_result", {}),
                            "research_result": result.get("research_result", {})  # NEW
                        }
                    })
                    
                except Exception as e:
                    error_message = f"❌ Error processing request: {str(e)}"
                    st.error(error_message)
                    
                    # Add error to history
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": error_message,
                        "workflow_details": {"error": str(e)}
                    })
    
    # Example buttons
    st.markdown("---")
    st.markdown("**💡 Try These Examples:**")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🚨 System Issue", use_container_width=True):
            st.session_state.example_query = "The downstream integration to Warranty system is not working"
            st.rerun()
    
    with col2:
        if st.button("🔍 Missing Claim", use_container_width=True):
            st.session_state.example_query = "I am missing Brazil claim number '1-ABCD' in the Claims report"
            st.rerun()
    
    with col3:
        if st.button("🔧 Engine Update", use_container_width=True):
            st.session_state.example_query = "I need help updating the Engine with Serial number '12345678' model name from 'X10' to 'X15'"
            st.rerun()
    
    with col4:  # NEW
        if st.button("📊 Research Query", use_container_width=True):
            st.session_state.example_query = "What are transformer models in machine learning?"
            st.rerun()
    
    # Second row of examples for research
    col5, col6, col7, col8 = st.columns(4)
    
    with col5:  # NEW
        if st.button("🧠 AI Comparison", use_container_width=True):
            st.session_state.example_query = "Compare LSTM and transformer architectures for NLP tasks"
            st.rerun()
    
    with col6:  # NEW
        if st.button("📈 Research Analysis", use_container_width=True):
            st.session_state.example_query = "Analyze recent advances in neural machine translation"
            st.rerun()
    
    with col7:  # NEW
        if st.button("🔬 Algorithm Study", use_container_width=True):
            st.session_state.example_query = "Find papers on attention mechanisms in deep learning"
            st.rerun()
    
    with col8:
        if st.button("📚 Process Info", use_container_width=True):
            st.session_state.example_query = "Can I get more information on how the Brazil claims are uploaded to reliability system?"
            st.rerun()
    
    # Handle example query
    if hasattr(st.session_state, 'example_query'):
        st.info(f"Example selected: {st.session_state.example_query}")
        if st.button("▶️ Send Example Query"):
            # Add the example as if user typed it
            st.session_state.chat_history.append({
                "role": "user", 
                "content": st.session_state.example_query
            })
            delattr(st.session_state, 'example_query')
            st.rerun()
    
    # NEW: Research-specific section
    st.markdown("---")
    st.markdown("**🔬 Research Capabilities**")
    
    with st.expander("📊 Research Features", expanded=False):
        st.markdown("""
        **What you can ask about:**
        
        **🤖 Machine Learning & AI:**
        - "What are transformer models?"
        - "Compare different neural network architectures"
        - "Explain attention mechanisms in deep learning"
        - "What are the latest advances in computer vision?"
        
        **📝 Natural Language Processing:**
        - "Compare LSTM vs transformer for NLP"
        - "How does BERT work?"
        - "Recent advances in neural machine translation"
        
        **🔍 Research Analysis:**
        - "Find relationships between concept A and concept B"
        - "Analyze the evolution of reinforcement learning"
        - "What are the current challenges in AI safety?"
        
        **📊 Technical Deep Dives:**
        - "Explain backpropagation algorithm"
        - "Compare different optimization techniques"
        - "What is federated learning?"
        
        The system uses multi-hop reasoning and knowledge graphs to provide comprehensive research insights!
        """)
        
        st.markdown("**🎯 Intent Detection Examples:**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            **System Issues → Incident Tickets:**
            - "The system is down"
            - "Integration not working"
            - "Database connection failed"
            """)
            
            st.markdown("""
            **Data Queries → Database Operations:**
            - "Find claim 1-ABCD"
            - "Update engine serial 12345"
            - "Missing warranty data"
            """)
        
        with col2:
            st.markdown("""
            **Research Queries → Knowledge Base:**
            - "What are transformers?"
            - "Compare algorithms"
            - "Recent AI research"
            """)
            
            st.markdown("""
            **Information Requests → Documentation:**
            - "How to upload claims?"
            - "Process documentation"
            - "Technical specifications"
            """)

if __name__ == "__main__":
    main()