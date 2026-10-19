def collect_tool_names(tool_calls):
    """Pulls just the tool names, in call order, out of a run_agent_traced()
    trace - the list of {"name", "args", "result"} dicts."""
    return [call["name"] for call in tool_calls]
