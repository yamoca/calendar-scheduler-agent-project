from mcp.server.fastmcp import FastMCP

mcp = FastMCP("demo")

@mcp.tool()
def add(a: int, b: int) -> int:
    # add two numbers
    return a + b

@mcp.resource("greeting://{name}")
def greeting(name: str) -> str:
    return f"hell {name}"

if __name__ == "__main__":
    mcp.run()