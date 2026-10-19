import pytest

import agent as agent_module


@pytest.fixture(scope="session")
def agent():
    """The expenses agent module - exposes run_agent_traced() for tests
    that need to inspect tool calls, not just the final answer."""
    return agent_module
