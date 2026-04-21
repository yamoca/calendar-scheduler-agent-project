from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

import asyncio
import os
import sys
from dotenv import load_dotenv
load_dotenv()


# Create server parameters for stdio connection
server_params = StdioServerParameters(
    command="python",  # Executable
    args=["mcp_server.py"],  # Optional command line arguments
    env=os.environ.copy(),  # Optional environment variables
)

async def run():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            await session.initialize()

            # List available resources
            resources = await session.list_resources()
            print("LISTING RESOURCES")
            for resource in resources:
                print("Resource: ", resource)

            # List available tools
            tools = await session.list_tools()
            print("LISTING TOOLS")
            for tool in tools.tools:
                print("Tool: ", tool.name)


            # Call a tool
            print("CALL TOOL")
            result = await session.call_tool("gmail_send_message", arguments={"message_text": "hey there sent from custom mcp client"})
            # result = await session.call_tool("add", arguments={"a": 10, "b": 5})
            print()
            print()
            print(result)


if __name__ == "__main__":
    asyncio.run(run())