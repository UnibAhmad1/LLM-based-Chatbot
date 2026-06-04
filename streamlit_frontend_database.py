import streamlit as st
from langgraph_backend import chatbot, retrieve_all_threads
from langgraph_backend import delete_thread
from langchain_core.messages import HumanMessage
import uuid

# ****************************** Utility function ********************************************

# to generate random thread ID
def generate_thread_id():
    thread_id = uuid.uuid4()
    return thread_id

# to reset the chat when clikcing on new conversation
def reset_chat():
    thread_id = generate_thread_id()
    st.session_state['thread_id'] = thread_id
    add_thread(st.session_state['thread_id'])
    st.session_state['message_history'] = []
    
# to add the new conversation thread Id in side bar
def add_thread(thread_id):
    if thread_id not in st.session_state['chat_threads']:
        st.session_state['chat_threads'].append(thread_id)
        
# to load the converstaion when you clicked on particular thread id
def load_conversation(thread_id):
    state = chatbot.get_state(config={'configurable': {'thread_id': thread_id}})
    return state.values.get("messages", [])

# To give title to coversation instead of thread ID
def get_thread_title(thread_id):
    messages = load_conversation(thread_id)

    for msg in messages:
        if hasattr(msg, "content"):
            return str(msg.content)[:30]

    return "New Chat"
        
# ********************************* Session setup***********************************************
if 'message_history' not in st.session_state:
    st.session_state['message_history'] = []
    
if 'thread_id' not in st.session_state:
    st.session_state['thread_id'] = generate_thread_id()

if 'chat_threads' not in st.session_state:
    st.session_state['chat_threads'] = retrieve_all_threads()
    
add_thread(st.session_state['thread_id'])
    
# ******************************** Side bar UI **************************************************
st.sidebar.title('Generative AI ChatBot')

if st.sidebar.button('New Conversation'):
    reset_chat()

st.sidebar.header('My Conversation')

for thread_id in st.session_state['chat_threads'][::-1]:
    
    col1, col2 = st.sidebar.columns([6,2])  # create 2 columns
    
    # Chat button
    
    thread_title = get_thread_title(thread_id)
    if col1.button(thread_title, key=f"open_{thread_id}"):
        st.session_state['thread_id'] = thread_id
        messages = load_conversation(thread_id)

        temp_messages = []
        
        for msg in messages:
            if isinstance(msg, HumanMessage):
                role = 'user'
            else:
                role ='assistant'
            temp_messages.append({'role': role, 'content': msg.content})
            
        st.session_state['message_history'] = temp_messages

    #  Delete button --> keyword (Del)
    if col2.button(" 🗑️ ", key=f"delete_{thread_id}"):

        delete_thread(thread_id)  # delete from DB

        st.session_state['chat_threads'].remove(thread_id)  # remove from UI

        # if current chat deleted → reset
        if st.session_state['thread_id'] == thread_id:
            reset_chat()

        st.rerun()
        
# *************************************** Main UI *************************************************   

st.info("""
Welcome to my Generative AI Chatbot!

This project is powered by the free Gemini 2.5 Flash model and is intended for learning and demonstration purposes.

• Responses may be slower than commercial AI assistants.
• Very long prompts or frequent requests may temporarily exceed the free API limits.
• If API limits are reached, the chatbot may become unavailable until the quota resets.
• For a better experience, try asking concise questions.

Thank you for trying it out! 
""") 
user_input  = st.chat_input('Type Here!')

CONFIG = {'configurable': {'thread_id': st.session_state['thread_id']}}
 
# for loading the conversation history
for messages in st.session_state['message_history']:
    with st.chat_message(messages['role']):
        st.text(messages['content'])

if user_input:
    
    # first add the message to message history
    st.session_state['message_history'].append({'role': 'user', 'content': user_input})
    with st.chat_message('user'):
        st.text(user_input)
     
    
    # first add the message to message history   
        
    with st.chat_message('assistant'):
        
        def stream_text():
            for message_chunk, metadata in chatbot.stream(
                {"messages": [HumanMessage(content=user_input)]},
                config=CONFIG,
                stream_mode="messages",
            ):
            
                content = message_chunk.content

                # If content is list (Gemini format)
                if isinstance(content, list):
                    for item in content:
                        if item.get("type") == "text":
                            yield item.get("text", "")
            
                # If content is dict
                elif isinstance(content, dict):
                    yield content.get("text", "")
            
                # If already plain string
                else:
                    yield content

    ai_message = st.write_stream(stream_text())
        
    st.session_state['message_history'].append({'role': 'assistant', 'content': ai_message})
