import json
import logging
from typing import TypedDict, Annotated, List, Dict, Any, Literal
import time

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_ollama import ChatOllama

# We setup our logging (using the framework's existing config)
from execution.utils.logging_config import setup_logging
logger = setup_logging()

# ==========================================
# 1. State Definition
# ==========================================
class AgentState(TypedDict):
    """
    The state that gets passed around the nodes in LangGraph.
    It contains the chat history and the Case Brief details if a handover is triggered.
    """
    # The `add_messages` reducer appends new messages to the existing list.
    messages: Annotated[list, add_messages]
    
    # Flags for routing
    needs_handover: bool
    
    # The generated Case Brief data
    intent: str
    blocker: str
    data_gathered: str
    sentiment: str

# ==========================================
# 2. Pydantic Models for LLM Output
# ==========================================
class CaseBrief(BaseModel):
    """Structured output expected from the LLM when summarizing the case."""
    intent: str = Field(description="What is the user trying to do? Example: 'File 2025 Taxes'")
    blocker: str = Field(description="Why did the AI fail? Example: 'User cannot locate 1099-K form in the digital vault'")
    data_gathered: str = Field(description="What specific entities/info do we know? Example: 'User confirmed they worked for Uber and DoorDash'")
    sentiment: str = Field(description="Is the user angry, confused, or neutral? Provide a one-word label.")

# ==========================================
# 3. Copilot Nodes (The Actions)
# ==========================================

def primary_ai_node(state: AgentState) -> dict:
    """
    Node 1: The Frustration / Handover Detector ("Intuit Assist")
    Detects if the user is frustrated or explicitly requests a human.
    """
    logger.info("Executing Primary AI Node...")
    messages = state.get("messages", [])
    if not messages:
        return {"needs_handover": False}

    # Get the last user message
    last_user_msg = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content.lower()
            break

    # Simulated AI logic: Is the user frustrated or stuck?
    frustration_keywords = ["human", "agent", "useless", "stuck", "frustrated", "can't find", "support"]
    
    needs_handover = any(keyword in last_user_msg for keyword in frustration_keywords)
    
    if needs_handover:
        logger.warning(f"Handover triggered! Keyword match in: '{last_user_msg}'")
        return {"needs_handover": True}
    else:
        logger.info("Handling request normally...")
        # (In a real app, the AI would generate an answer here and append an AIMessage)
        return {"needs_handover": False}

def context_summary_agent_node(state: AgentState) -> dict:
    """
    Node 2: The Context-Summary Agent (The Briefing Engine Validator)
    This agent runs *only* when 'needs_handover' is True. 
    It leverages Llama 3.2 via Ollama to generate a structured Case Brief.
    """
    logger.info("Executing Context-Summary Agent (Building Case Brief via Llama 3.2)...")
    messages = state.get("messages", [])
    
    # Initialize the local Ollama LLM
    try:
        # We tell Ollama to use format="json" if using base ChatOllama, 
        # but with_structured_output works efficiently on newest models.
        llm = ChatOllama(model="llama3.2", temperature=0)
        structured_llm = llm.with_structured_output(CaseBrief)
    except Exception as e:
        logger.error(f"Failed to initialize Ollama: {e}")
        return {"intent": "Error", "blocker": "LLM Failure", "data_gathered": "None", "sentiment": "Unknown"}
    
    # We construct a precise command for the LLM based on the conversation history
    system_prompt = (
        "You are an expert handover-summarization agent. Your job is to read the chat log "
        "and extract the core issue into structured JSON. Be concise. Infer the sentiment. "
        "Summarize the main blocker causing the user to need human intervention."
    )
    
    prompt_messages = [
        {"role": "system", "content": system_prompt}
    ]
    
    # Add the chat log
    for m in messages:
        role = "user" if isinstance(m, HumanMessage) else "assistant"
        prompt_messages.append({"role": role, "content": m.content})
        
    try:
        # The LLM generates the JSON exactly matching the Pydantic schema
        structured_response = structured_llm.invoke(prompt_messages)
        
        logger.info("Case Brief generated successfully from LLaMA.")
        
        return {
            "intent": structured_response.intent,
            "blocker": structured_response.blocker,
            "data_gathered": structured_response.data_gathered,
            "sentiment": structured_response.sentiment
        }
    except Exception as e:
        logger.error(f"Llama 3.2 failed to parse output: {e}")
        return {
            "intent": "Fallback Intent (LLM Parsing Failed)",
            "blocker": "Fallback Blocker",
            "data_gathered": "Fallback Data",
            "sentiment": "Frustrated"
        }

def human_dashboard_node(state: AgentState) -> dict:
    """
    Node 3: The Delivery
    Pushes the Case Brief to the human expert's dashboard BEFORE they say hello.
    """
    print("\n" + "="*50)
    print("🚨 [DASHBOARD ALERT] NEW HUMAN TRANSFER")
    print("="*50)
    print("🤖 The Briefing Engine has prepared a Case Brief:")
    print("")
    print(f"🎯 INTENT: \n   {state.get('intent')}")
    print(f"🛑 BLOCKER: \n   {state.get('blocker')}")
    print(f"📁 DATA GATHERED: \n   {state.get('data_gathered')}")
    print(f"😡 SENTIMENT: \n   {state.get('sentiment')}")
    print("="*50)
    print("💬 Original Transcript Length: {} messages".format(len(state.get("messages", []))))
    print("="*50 + "\n")
    
    return {}

# ==========================================
# 3. Router (Conditional Edge)
# ==========================================

def should_handover(state: AgentState) -> Literal["context_summary", "end"]:
    """
    Router that decides where to go after the primary AI runs.
    """
    if state.get("needs_handover", False):
         return "context_summary"
    return "end"

# ==========================================
# 4. Building the LangGraph
# ==========================================

def build_briefing_engine():
    """Compiles the LangGraph workflow."""
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("primary_ai", primary_ai_node)
    workflow.add_node("context_summary", context_summary_agent_node)
    workflow.add_node("human_dashboard", human_dashboard_node)
    
    # Set entry point
    workflow.set_entry_point("primary_ai")
    
    # Add conditional edges from the AI
    workflow.add_conditional_edges(
        "primary_ai",
        should_handover,
        {
            "context_summary": "context_summary",
            "end": END
        }
    )
    
    # After the summary is built, send it to the dashboard, then end.
    workflow.add_edge("context_summary", "human_dashboard")
    workflow.add_edge("human_dashboard", END)
    
    # Compile
    return workflow.compile()

# ==========================================
# 5. Execution Test
# ==========================================

if __name__ == "__main__":
    engine = build_briefing_engine()
    
    logger.info("--- Simulating a normal AI interaction (No frustration) ---")
    normal_interaction = [
        HumanMessage(content="Hi, how do I file taxes?"),
        AIMessage(content="Hello! I can help you file your taxes. Do you have your W-2?"),
        HumanMessage(content="Yes, I do.")
    ]
    # The normal interaction won't trigger the handover
    engine.invoke({"messages": normal_interaction})
    
    
    print("\n\n" + "-"*60 + "\n\n")
    
    
    logger.info("--- Simulating a frustrated User (Triggering the Engine) ---")
    frustrated_interaction = [
        HumanMessage(content="Hi, I need to file my 2025 taxes."),
        AIMessage(content="Great! Did you work as an employee (W-2) or a contractor (1099)?"),
        HumanMessage(content="I drove for Uber and DoorDash."),
        AIMessage(content="Got it. You'll need a 1099-K form from both platforms. Please upload them. You can find them in your digital vault."),
        HumanMessage(content="I can't find my 1099-K anywhere in the digital vault. This is so frustrating, I need a human agent now.")
    ]
    # The frustrated interaction will trigger the full Briefing Engine Workflow
    engine.invoke({"messages": frustrated_interaction})
