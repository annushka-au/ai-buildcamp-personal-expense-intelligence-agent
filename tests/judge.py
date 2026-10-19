"""
LLM-as-a-judge helper, following the same pattern as the course reference
project's tests/judge.py - but built on plain OpenAI structured outputs
instead of PydanticAI, since agent.py doesn't use PydanticAI.

assert_criteria() takes the agent's final answer plus its tool-call trace
(from agent.run_agent_traced()) and a list of natural-language criteria,
asks a judge model to evaluate each one with evidence, and fails the test
with the judge's own explanation if any criterion isn't satisfied.
"""

import json

from agent import openai_client

JUDGE_INSTRUCTIONS = """
You are an expert judge evaluating the performance of an AI expense agent.

Evaluate every criterion independently and strictly. Use the agent's final
answer and its tool-call trace as evidence - do not assume a criterion is
satisfied without clear evidence in that trace or answer.
""".strip()

JUDGE_USER_PROMPT_TEMPLATE = """
Evaluate the agent's performance based on the following criteria:
<CRITERIA>
{criteria}
</CRITERIA>

The agent's final answer was:
<AGENT_OUTPUT>
{output}
</AGENT_OUTPUT>

Tool calls made by the agent, in order:
<TOOL_CALLS>
{tool_calls}
</TOOL_CALLS>
""".strip()

JUDGE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "criteria": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterion_description": {"type": "string"},
                    "passed": {"type": "boolean"},
                    "judgement": {"type": "string"},
                },
                "required": ["criterion_description", "passed", "judgement"],
                "additionalProperties": False,
            },
        },
        "feedback": {"type": "string"},
    },
    "required": ["criteria", "feedback"],
    "additionalProperties": False,
}


def _format_tool_calls(tool_calls):
    if not tool_calls:
        return "(no tool calls)"
    return "\n".join(
        f"{call['name']}({call['args']}) -> {call['result']}"
        for call in tool_calls
    )


def assert_criteria(answer, tool_calls, criteria, model="gpt-4o-mini"):
    """Fails the test if any natural-language criterion is not satisfied,
    per the judge model - printing its explanation either way."""
    user_prompt = JUDGE_USER_PROMPT_TEMPLATE.format(
        criteria="\n".join(f"- {c}" for c in criteria),
        output=answer,
        tool_calls=_format_tool_calls(tool_calls),
    )

    response = openai_client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": JUDGE_INSTRUCTIONS},
            {"role": "user", "content": user_prompt},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "judge_feedback",
                "schema": JUDGE_RESPONSE_SCHEMA,
                "strict": True,
            }
        },
    )

    feedback = json.loads(response.output_text)

    print("\nJudge feedback:", feedback["feedback"])

    assert len(feedback["criteria"]) == len(criteria), (
        f"Judge evaluated {len(feedback['criteria'])} criteria, "
        f"expected {len(criteria)}"
    )

    for criterion in feedback["criteria"]:
        print(
            f"{criterion['criterion_description']}: "
            f"{criterion['passed']} - {criterion['judgement']}"
        )
        assert criterion["passed"], (
            f"{criterion['criterion_description']}: {criterion['judgement']}"
        )
