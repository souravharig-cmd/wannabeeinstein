import os
import sys
import json
import asyncio
from typing import Dict, Any, List, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class MCPClientManager:
    def __init__(self, server_script_path: str = "backend/mcp_server.py"):
        self.server_script_path = server_script_path

    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Connect to MCP server via stdio and discover tools."""
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[self.server_script_path],
            env={"PATH": os.environ.get("PATH", "")}
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                tools_data = []
                for tool in tools_result.tools:
                    tools_data.append({
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.inputSchema
                    })
                return tools_data

    async def call_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Any:
        """Call a tool on the MCP server via stdio protocol."""
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[self.server_script_path],
            env={
                "PATH": os.environ.get("PATH", ""),
                "TASKPILOT_DATA_DIR": os.environ.get("TASKPILOT_DATA_DIR", "data"),
                "TASKPILOT_DB_PATH": os.environ.get("TASKPILOT_DB_PATH", "data/taskpilot.db")
            }
        )
        tool_error = None
        tool_result = None

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, tool_args)
                
                if result and result.isError:
                    error_messages = [
                        content.text
                        for content in result.content
                        if hasattr(content, "text")
                    ]
                    error_detail = (
                        "\n".join(error_messages) or "The MCP tool returned an error."
                    )
                    tool_error = f"MCP tool '{tool_name}' failed: {error_detail}"
                elif result and result.content:
                    # Extract content from TextContent objects
                    first_content = result.content[0]
                    if hasattr(first_content, "text"):
                        try:
                            tool_result = json.loads(first_content.text)
                        except json.JSONDecodeError:
                            tool_result = first_content.text
                    else:
                        tool_result = result
                else:
                    tool_result = result

        if tool_error:
            raise RuntimeError(tool_error)
        return tool_result

# Synchronous wrapper for convenience in engine loops
def call_mcp_tool_sync(tool_name: str, tool_args: Dict[str, Any]) -> Any:
    client = MCPClientManager()
    return asyncio.run(client.call_tool(tool_name, tool_args))

def discover_mcp_tools_sync() -> List[Dict[str, Any]]:
    client = MCPClientManager()
    return asyncio.run(client.get_available_tools())
