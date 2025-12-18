import streamlit as st
import uuid
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage
from agent import app 

# --- PAGE SETUP ---
st.set_page_config(page_title="Deep Research Agent", page_icon="🧐")
st.title("Deep Research Agent 🧐")
st.markdown("Ask me anything. I will search the web, read pages, and give you a report.")

# --- SESSION STATE (Memory) ---
# 1. Create a unique Thread ID for this specific user session
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

# 2. Initialize Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- DISPLAY CHAT HISTORY ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- HANDLE USER INPUT ---
if prompt := st.chat_input("What would you like to research?"):
    # 1. Display User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Run Agent
    with st.chat_message("assistant"):
        # Create a status container to show "Thinking..."
        with st.status("🧠 Deep Research in progress...", expanded=True) as status:
            st.write("Initializing agent...")
            
            # Prepare config with the unique thread ID
            config: RunnableConfig = {"configurable": {"thread_id": st.session_state.thread_id}}
            
            # Run the agent stream
            final_response = None
            
            # We stream the events to see the "steps"
            for event in app.stream({"messages": [HumanMessage(content=prompt)]}, config=config):
                # Inspect the event to see what node just finished
                for key, value in event.items():
                    if key == "agent":
                        st.write("🤖 Agent is planning next steps...")
                    elif key == "tools":
                        st.write("🔎 Searching external sources...")
            
            # Update status to complete
            status.update(label="Research Complete!", state="complete", expanded=False)

        # 3. Get and Display Final Answer
        # We fetch the final state from the agent's memory
        final_state = app.get_state(config)
        
        if final_state.values and "messages" in final_state.values:
            last_msg = final_state.values["messages"][-1]
            final_response = last_msg.content
            
            # Clean up if it's a list (sometimes Gemini returns lists)
            if isinstance(final_response, list):
                final_response = final_response[0]['text']
            
            st.markdown(final_response)
            
            # Save to history
            st.session_state.messages.append({"role": "assistant", "content": final_response})