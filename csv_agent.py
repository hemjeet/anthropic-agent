import streamlit as st
import anthropic
import pandas as pd
import io
from contextlib import redirect_stdout
from dotenv import load_dotenv

load_dotenv()
client = anthropic.Anthropic()

# ── Page config ────────────────────────────────────────────
st.set_page_config(
    page_title="Data Analyst Agent",
    page_icon="📊",
    layout="centered"
)

st.title("📊 Data Analyst Agent")
st.caption("Upload a CSV and ask anything about your data")

# ── Session state — persists across reruns ─────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

if "df" not in st.session_state:
    st.session_state.df = None

if "file_name" not in st.session_state:
    st.session_state.file_name = None

# ── CSV Upload ─────────────────────────────────────────────
uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])

if uploaded_file:
    # Only reload if a new file is uploaded
    if uploaded_file.name != st.session_state.file_name:
        st.session_state.df = pd.read_csv(uploaded_file)
        st.session_state.file_name = uploaded_file.name
        st.session_state.messages = []   # reset chat for new file
        st.success(f"✅ Loaded {uploaded_file.name} — {st.session_state.df.shape[0]} rows, {st.session_state.df.shape[1]} columns")

    # Show a preview of the data
    with st.expander("Preview data"):
        st.dataframe(st.session_state.df.head())

# ── Only show chat if CSV is uploaded ─────────────────────
if st.session_state.df is not None:
    df = st.session_state.df

    # ── Tools ──────────────────────────────────────────────
    tools = [
        {
            "name": "run_python",
            "description": """Run Python and pandas code to analyze 
            the dataframe. The dataframe is loaded as `df`. 
            Always use print() to show results.""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python/pandas code. Always use print()."
                    }
                },
                "required": ["code"]
            }
        }
    ]

    # ── Tool function ──────────────────────────────────────
    def run_python(code: str) -> str:
        output = io.StringIO()
        try:
            with redirect_stdout(output):
                exec(code, {"df": df, "pd": pd})
            result = output.getvalue()
            return result if result else "Code ran but no output. Use print()."
        except Exception as e:
            return f"Error: {e}"

    # ── System prompt ──────────────────────────────────────
    system_prompt = f"""You are a data analyst assistant.
You have access to a dataframe `df` with this structure:
- Shape: {df.shape}
- Columns: {list(df.columns)}
- Dtypes: {df.dtypes.to_dict()}

Sample data:
{df.head(3).to_string()}

Always use run_python tool to answer questions.
Always use print() in your code.
Explain results clearly after showing them."""

    # ── Display chat history ───────────────────────────────
    for msg in st.session_state.messages:
        if msg["role"] == "user" and isinstance(msg["content"], str):
            with st.chat_message("user"):
                st.write(msg["content"])
        elif msg["role"] == "assistant" and isinstance(msg["content"], str):
            with st.chat_message("assistant"):
                st.write(msg["content"])

    # ── Chat input ─────────────────────────────────────────
    user_input = st.chat_input("Ask anything about your data...")

    if user_input:
        # Show user message immediately
        with st.chat_message("user"):
            st.write(user_input)

        # Add to history
        st.session_state.messages.append({
            "role": "user",
            "content": user_input
        })

        # ── Agent loop ─────────────────────────────────────
        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):

                step = 0
                max_steps = 10

                while step < max_steps:
                    step += 1

                    response = client.messages.create(
                        model="claude-haiku-4-5",
                        max_tokens=1024,
                        system=system_prompt,
                        tools=tools,
                        messages=st.session_state.messages
                    )

                    # ── Done ───────────────────────────────
                    if response.stop_reason == "end_turn":
                        for block in response.content:
                            if hasattr(block, "text"):
                                st.write(block.text)
                                st.session_state.messages.append({
                                    "role": "assistant",
                                    "content": block.text
                                })
                        break

                    # ── Tool use ───────────────────────────
                    if response.stop_reason == "tool_use":
                        assistant_message = []
                        tool_results = []

                        for block in response.content:
                            if block.type == "text":
                                assistant_message.append({
                                    "type": "text",
                                    "text": block.text
                                })

                            elif block.type == "tool_use":
                                assistant_message.append({
                                    "type": "tool_use",
                                    "id": block.id,
                                    "name": block.name,
                                    "input": block.input
                                })

                                # Show code being run
                                with st.expander(f"🔧 Running code..."):
                                    st.code(block.input.get("code", ""), language="python")

                                result = run_python(block.input["code"])

                                # Show output
                                with st.expander("📊 Output"):
                                    st.text(result)

                                tool_results.append({
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": result
                                })

                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": assistant_message
                        })
                        st.session_state.messages.append({
                            "role": "user",
                            "content": tool_results
                        })

else:
    # No CSV uploaded yet
    st.info("👆 Upload a CSV file to get started")