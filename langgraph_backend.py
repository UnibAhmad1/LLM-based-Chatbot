from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_core.messages import HumanMessage, BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver

from langgraph.prebuilt import ToolNode, tools_condition
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage

import requests
import random
import sqlite3
from dotenv import load_dotenv

load_dotenv()

# Define LLM
llm = ChatGoogleGenerativeAI(model= "gemini-2.5-flash", temperature=0.2, max_retries=1)


# Tool 1
@tool
def calculator(first_num: float, second_num: float, operation: str) -> dict:
    """
    Perform a basic arthmetic operations on two or more numbers.
    Supported operations: add, sub, mul, div
    """
    try:
        if operation == "add":
            result = first_num+second_num
        elif operation == "sub":
            result = first_num-second_num
        elif operation == "mul":
            result = first_num*second_num
        elif operation == "div":
            if second_num == 0:
                return {"error": "Divison by zero is not allowed"}
            result = first_num/second_num
        else:
            return {"error": f"Unsupported operation '{operation}'"}
        
        return f"the result is {result}"
    except Exception as e:
        return {"error": str(e)}
    

# Tool 3 (Stock market)
@tool
def get_stock_price(symbol: str) -> dict:
    """
    Fetch latest stock price for given symbol. 
    using alpha vangtage with API key in the url.
    """
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={symbol}&apikey=NJ1VOM6S7AD4L7DV"
    r = requests.get(url)
    return r.json()

# Make tools list
tools = [get_stock_price, calculator]

# Make the LLm tool aware
llm_with_tools = llm.bind_tools(tools)



# Define State
class ChatState(TypedDict):
    
    messages: Annotated[list[BaseMessage], add_messages]
    
# Function for chatbot
def chat_node(state: ChatState):
    
    # take user query from state
    
    messages = state["messages"]
    
    system_prompt = SystemMessage(
    content="""
    You are a helpful AI assistant.

    IMPORTANT:
    - Use tools ONLY when necessary.
    - If the question can be answered directly, DO NOT use any tool.
    - Never say you need a tool unless absolutely required.

    STRICT RULES:
    - Always give clean, final answers.
    - Never show raw tool output.

    STYLE:
    - Max 20 words.
    """
    )
    
    # send to llm 
    response = llm.invoke([system_prompt] + messages)
    # store the response in state
    return {'messages': [response]}

tool_node =  ToolNode(tools)

connection = sqlite3.connect(database='chatbot.db', check_same_thread=False)
# CheckPointer
checkpointer = SqliteSaver(conn=connection)

# Define graph
graph = StateGraph(ChatState)

# add node
graph.add_node('chat_node', chat_node)
graph.add_node("tools", tool_node)

# add edges
graph.add_edge(START, 'chat_node')

# If the LLM ask for tool, go to toolnode: else finish
graph.add_conditional_edges('chat_node', tools_condition)
graph.add_edge('tools', 'chat_node')

#compile
chatbot = graph.compile(checkpointer=checkpointer)

def retrieve_all_threads():
    all_threads = set()
    for checkpoint in checkpointer.list(None):
        all_threads.add(checkpoint.config['configurable']['thread_id'])
        
    return list(all_threads)


# to delete the conversation from side bar
def delete_thread(thread_id):
    """
    Delete all chat history related to a thread_id from database.
    """
    
    cursor = connection.cursor()   # create cursor to run SQL query
    
    cursor.execute(
        """
        DELETE FROM checkpoints
        WHERE thread_id = ?
        """,
        (str(thread_id),)   # pass thread_id safely
    )
    
    connection.commit()   # save changes to database
    
    