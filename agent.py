# 1. IMPORTS 
import warnings
warnings.filterwarnings("ignore")
import os
from dotenv import load_dotenv

load_dotenv() 

from typing import Annotated, Literal
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from typing_extensions import TypedDict
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import HumanMessage

# 2. Configure Tools

search_tool = TavilySearchResults(max_results=3)
tools = [search_tool]

# temperature=0 makes it factual (good for research)
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", 
    temperature=0
)

# Bind tools to LLM
llm_with_tools = llm.bind_tools(tools)

#3. Define Agent State
class AgentState(TypedDict): #thisis memory
    # add_messages makes sure we add new messages to history, rather than overwriting
    messages: Annotated[list, add_messages]

#4. Define nodes

def chatbot(state: AgentState):
    """
    The 'Brain' node. It decides what to do.
    """
    # 1. Define the System Prompt (The Agent's "Job Description")
    system_instruction = SystemMessage(content="""
    You are a helpful research assistant. 
    You have access to a search engine (Tavily). 
    
    CRITICAL INSTRUCTIONS:
    - If the user asks for real-time information (like stock prices, weather, news), you MUST use the search tool.
    - Do NOT refuse to answer. Do NOT say "I cannot provide real-time info".
    - Just search, read the results, and provide the answer.
    """)
    
    # 2. Add the system message to the history
    messages = [system_instruction] + state["messages"]
    
    # 3. Invoke the LLM
    response = llm_with_tools.invoke(messages)
    
    return {"messages": [response]}

# Note: We use LangGraph's prebuilt ToolNode for the "Action" step
# It automatically executes whatever tool Gemini asks for.
tool_node = ToolNode(tools)

# 5. Build the Workflow

workflow = StateGraph(AgentState)

# Add the two main nodes
workflow.add_node("agent", chatbot)
workflow.add_node("tools", tool_node)

# Set the entry point (Start with the Agent)
workflow.add_edge(START, "agent")

# Add the Conditional Edge (The Logic Loop)
# Did Gemini ask for a tool?
# If YES -> Go to "tools" node
# If NO -> Go to END (we are done)
workflow.add_conditional_edges(
    "agent",
    tools_condition,
)

# Add an edge from Tools back to Agent
workflow.add_edge("tools", "agent")

# Compile the graph
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)

# make graph imjage
try:
    png_data = app.get_graph().draw_mermaid_png()
    with open("agent_graph.png", "wb") as f:
        f.write(png_data)
    print("📸 Graph saved as 'agent_graph.png'")
except Exception as e:
    print(f"Could not draw graph: {e}")

# main function

if __name__ == "__main__":
    print("🚀 Deep Research Agent is ON (with Memory).")
    print("Type 'quit' to exit.\n")
    
    thread: RunnableConfig = {"configurable": {"thread_id": "1"}}

    while True:
        user_input = input("User: ")
        if user_input.lower() in ["quit", "exit"]:
            break
        
        inputs: AgentState = {"messages": [HumanMessage(content=user_input)]}
        
        # Stream the output
        for event in app.stream(inputs, config=thread):
            for key, value in event.items():
                print(f"  --> Node '{key}' finished.")

        # Get the final state
        snapshot = app.get_state(thread)
        if snapshot.values and "messages" in snapshot.values:
            last_msg = snapshot.values["messages"][-1]
            content = last_msg.content
            
            print("\n🤖 Final Answer:")
            if isinstance(content, list):
                print(content[0]['text'])
            else:
                print(content)
            print("-" * 50)