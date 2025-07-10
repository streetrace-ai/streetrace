#!/usr/bin/env python3
"""Demo script to run the Step Executor Agent directly."""

import asyncio
import sys
from pathlib import Path

# Add the src directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from streetrace.agents.step_executor.agent import run_step_executor
from streetrace.llm.model_factory import ModelFactory
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import ToolProvider


async def main() -> None:
    """Run the Step Executor Agent demo."""
    if len(sys.argv) < 2:
        print("Usage: python step_executor_demo.py 'your requirements here'")
        print("Example: python step_executor_demo.py 'Create a user management system'")
        return

    requirements = " ".join(sys.argv[1:])
    work_dir = Path.cwd()
    
    print(f"🚀 Running Step Executor Agent...")
    print(f"📝 Requirements: {requirements}")
    print(f"📁 Working Directory: {work_dir}")
    print("=" * 60)
    
    try:
        # Initialize components (simplified for demo)
        # In a real scenario, these would be properly configured
        model_factory = ModelFactory("claude-3-sonnet-20240229", None)  # Simplified
        system_context = SystemContext(None, work_dir / ".streetrace")  # Simplified  
        tool_provider = ToolProvider(work_dir)
        
        # Get available tools for the agent
        tool_refs = [
            "streetrace:fs_tool::read_file",
            "streetrace:fs_tool::write_file",
            "streetrace:fs_tool::list_directory",
        ]
        tools = await tool_provider.get_tools(tool_refs)
        
        # Run the step executor
        result = await run_step_executor(
            requirements=requirements,
            model_factory=model_factory,
            system_context=system_context,
            tools=tools,
        )
        
        print("✅ Step Executor Agent completed successfully!")
        print("📋 Result:")
        print(result)
        
    except Exception as e:
        print(f"❌ Step Executor Agent failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)