from tests.judge import assert_criteria


def test_explains_september_spike_with_specific_evidence(agent):
    """
    Scenario 1 from Question 1: an open-ended "why" question should use
    search_expenses (not query_expenses) and the answer should name the
    actual September spike drivers with real figures, not just gesture at
    "higher spending" in general.
    """
    question = "Why were my expenses unusually high in September?"
    answer, tool_calls = agent.run_agent_traced(question)

    assert_criteria(answer, tool_calls, [
        "the agent called the 'search_expenses' tool rather than 'query_expenses', since this is an open-ended 'why' question rather than one needing an exact calculation or aggregation",
        "the answer explicitly names both the Qantas flight and the Bunnings washing machine purchase as reasons for the September spending increase",
        "the answer includes at least one specific dollar amount tied to a named transaction, not just merchant names with no figures attached",
    ])
