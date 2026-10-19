import re

from tests.utils import collect_tool_names


def test_agent_does_not_hallucinate_spending_for_unknown_category(agent):
    """
    Scenario 7 from Question 1: "entertainment" is not one of the 7 real
    expense categories (groceries, utilities, transport, dining, household,
    health, subscriptions). query_expenses should correctly find nothing,
    and the agent must say so rather than inventing a dollar figure.
    """
    question = "How much have I spent on entertainment?"

    answer, tool_calls = agent.run_agent_traced(question)

    tool_names = collect_tool_names(tool_calls)
    assert "query_expenses" in tool_names, (
        f"Expected query_expenses to be called for an exact-amount question, "
        f"got: {tool_names}"
    )

    query_call = next(call for call in tool_calls if call["name"] == "query_expenses")
    category_used = query_call["args"].get("filters", {}).get("category", "")
    assert category_used.lower() == "entertainment"

    # "entertainment" isn't a real category, so the tool should have found
    # nothing to work with.
    assert query_call["result"] == []

    # The agent must not report a non-zero dollar figure for a category with
    # no matching records - that would mean it hallucinated a number instead
    # of relying on the (empty) tool result.
    dollar_amounts = re.findall(r"\$\s?([0-9][0-9,]*\.?[0-9]*)", answer)
    nonzero_amounts = [a for a in dollar_amounts if float(a.replace(",", "")) > 0]

    assert nonzero_amounts == [], (
        f"Agent reported non-zero dollar amount(s) for an unknown category: "
        f"{nonzero_amounts}\nFull answer: {answer}"
    )
