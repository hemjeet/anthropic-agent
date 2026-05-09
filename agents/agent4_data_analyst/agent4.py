import anthropic
from dotenv import load_dotenv
import pandas as pd
import io
from contextlib import redirect_stdout

load_dotenv()
client = anthropic.Anthropic()

# read file 
df = pd.read_csv('salary_info.csv')

print(f"✅ Loaded dataset: {df.shape[0]} rows, {df.shape[1]} columns")
print(f"   Columns: {list(df.columns)}\n")

# ── Tools ──────────────────────────────────────────────────
tools = [
    {
        "name": "run_python",
        "description": """Run Python and pandas code to analyze the dataframe.
        The dataframe is already loaded as `df`.
        Always use print() to show your results.
        Use this for ANY question about the data.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python/pandas code to run. Always use print()."
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "calculate",
        "description": "Do simple math calculations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Math expression like '95000 * 12'"
                }
            },
            "required": ["expression"]
        }
    }
]

# ── Tool functions ─────────────────────────────────────────
def run_python(code: str) -> str:
    """
    Runs Python code with df available.
    Captures print() output and returns it as a string.
    If code errors, returns the error so Claude can fix it.
    """
    output = io.StringIO()
    try:
        with redirect_stdout(output):          # captures print() output
            exec(code, {"df": df, "pd": pd})   # runs code with df available
        result = output.getvalue()
        return result if result else "Code ran but no output. Did you use print()?"
    except Exception as e:
        return f"Error: {e}" 
    
# def calculate(expression):
#     try:
#         return str(eval(expression))
#     except Exception as e:
#          return f"Error: {e}"

def run_tool(tool_name, tool_input):
    if tool_name == 'run_python':
        return run_python(tool_input['code'])
    # elif tool_name == 'calculate':
    #     return calculate(tool_input['expression'])
    else:
        return f"Unknow too {tool_name}"
    
# ── System prompt — tells Claude about the data ────────────
system_prompt = f"""You are a data analyst assistant.
You have access to a dataframe `df` with this structure:
- Shape: {df.shape}
- Columns: {list(df.columns)}
- Dtypes: {df.dtypes.to_dict()}

Sample data (first 3 rows):
{df.head(3).to_string()}

When answering questions about the data:
1. Always use the run_python tool to get accurate answers
2. Always use print() in your code to show results
3. Write clean, simple pandas code
4. Explain what the numbers mean after showing them
5. If your code errors, fix it and try again"""

# ── Memory ────────────────────────────────────────────────
messages = []

# ── Chat function ─────────────────────────────────────────
def chat(user_input):
    print(f"\nYou: {user_input}")
    print("-" * 40)

    messages.append({
        'role': 'user',
        'content': user_input
    })



    while True:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            system=system_prompt,
            tools=tools,
            messages=messages
        )

        if response.stop_reason =='end_turn':
            for block in response.content:
                if hasattr(block, 'text'):
                    print(f"Assistant: {block.text}")
                    messages.append({
                        "role": "assistant",
                        "content": block.text
                    })
            break

        if response.stop_reason == 'tool_use':
            assistant_message = []
            tool_results = []
            for block in response.content:
                if block.type == 'text':
                    assistant_message.append({
                        'type': 'text',
                        'content': block.text
                    })

                
                elif block.type == 'tool_use':
                    assistant_message.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input
                    })

                    print(f"\n[using {block.name}...]")
                    print(f"Code:\n{block.input.get('code', block.input)}")

                    result = run_tool(block.name, block.input)
                    print(f"Output: {result}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })
            messages.append({"role": "assistant", "content": assistant_message})
            messages.append({"role": "user", "content": tool_results})

# ── Run it ────────────────────────────────────────────────
if __name__ == "__main__":
    print("📊 Data Analyst Agent ready! Ask me anything about the dataset.")
    print("   Type 'exit' to quit.\n")

    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit", "bye"]:
            print("Goodbye!")
            break
        chat(user_input)