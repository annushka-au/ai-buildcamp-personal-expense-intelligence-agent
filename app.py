"""
Simple Streamlit chat interface for the expense agent.

Lets you type a question, see the agent's answer, and expand a panel
showing which tools were called (name, arguments, result) for that
interaction. Every call goes through agent.run_agent_traced, which is
already instrumented with Logfire (logfire.instrument_openai + a
logfire.span("agent_session") around the whole run), so every
interaction run from this app shows up as its own trace in the Logfire
dashboard - no extra monitoring wiring needed here.

Run:
    uv run streamlit run app.py
"""

import streamlit as st

from agent import run_agent_traced

st.set_page_config(page_title="Expense Agent", page_icon="💰")
st.title("💰 Personal Expense Intelligence Agent")
st.caption("Ask about your spending. Every question is traced in Logfire.")

if "messages" not in st.session_state:
    st.session_state.messages = []


def render_answer(text):
    # Streamlit's markdown renders "$...$" as LaTeX math. Dollar amounts
    # like "$648.00 ... $389.00" otherwise get swallowed into a garbled
    # math span, so escape literal dollar signs before rendering.
    st.markdown(text.replace("$", "\\$"))


def render_tool_calls(tool_calls):
    if not tool_calls:
        return
    names = ", ".join(tc["name"] for tc in tool_calls)
    with st.expander(f"🔧 Tools called: {names}"):
        for tc in tool_calls:
            st.markdown(f"**{tc['name']}**")
            st.json({"args": tc["args"], "result": tc["result"]})


for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        render_answer(msg["content"])
        if msg["role"] == "assistant":
            render_tool_calls(msg.get("tool_calls"))

prompt = st.chat_input("e.g. Why were my expenses unusually high in September?")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        render_answer(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            answer, tool_calls = run_agent_traced(prompt)
        render_answer(answer)
        render_tool_calls(tool_calls)

    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "tool_calls": tool_calls}
    )
