import os
import sys
from dotenv import load_dotenv

import asyncio

from langchain_openrouter import ChatOpenRouter

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain.agents import create_agent

# os.environ["OPENROUTER_API_KEY"] = os.getenv('API_KEY')

load_dotenv()

if not os.getenv("OPENROUTER_API_KEY"):
    os.environ["OPENROUTER_API_KEY"] = os.getenv('API_KEY') 

MODEL = "nvidia/nemotron-3-nano-30b-a3b:free"
task = "send a polite greeting email with a simple message of your choice. Everything apart from the message body is handled for you, so dont worry about the recipient, subject, etc"

client = MultiServerMCPClient(
    {
        "gmail_api_mcp_server": {
            "transport": "stdio",
            "command": "python",
            "args": ["mcp_server.py"],
            "env": os.environ.copy()
        }
    }
)


async def main():
    # Keep the session alive for the entire duration of the agent's work
    async with client.session("gmail_api_mcp_server") as session: 
        llm = ChatOpenRouter(model=MODEL)
        tools = await client.get_tools() 
        agent = create_agent(llm, tools)
        
        try:
            # If this is outside the 'async with', it will fail with Errno 9
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": task}]}
            )
            print(result["messages"], file=sys.stderr)
        except Exception as e:
            print(f"Caught inside loop: {e}", file=sys.stderr)

if __name__ == "__main__":
    asyncio.run(main())



# # tools = await client.get_tools()
# # agent = create_agent("claude", tools)


# async def main():
#     async with client.session("gmail_api_mcp_server") as session:
#         tools = await load_mcp_tools(session)
#         llm = ChatOpenRouter(model=MODEL)
#         agent = create_agent(llm, tools)
#         response = await agent.ainvoke({
#             "messages": [
#                 {
#                     "role": "user",
#                     "content": task 
#                 }
#             ]
#         })
#         print("agent response: ", response["message"][-1].content, file=sys.stderr)


# if __name__ == "__main__":
#     asyncio.run(main())