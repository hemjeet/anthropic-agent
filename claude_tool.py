import anthropic
from dotenv import load_dotenv

# load env
load_dotenv()
# This creates a connection to Claude
client = anthropic.Anthropic()

tools = [
    {
        "name": "calculate",
        "description": "Use this to do any math calculation. Pass a math expression as a string.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "A math expression. Example: '25 * 4' or '100 / 3'"
                }
            },
            "required": ["expression"]
        }
    }
]

# ── STEP B: The actual Python function ───────────────────────
# This runs when Claude decides to call the tool
def calculate(expression):
    try:
        result = eval(expression)
        return str(result)
    except Exception as e:
        return f"Error: {e}"
    
response = client.messages.create(
    model="claude-haiku-4-5",  # which Claude model to use
    max_tokens=1024,                    # max length of reply
    messages=[
        {"role": "user", "content": "What is 1234 multiplied by 567?"}
    ],
    tools= tools
)

# ── STEP D: Check what Claude wants to do ───────────────────
print(f"Claude's decision: {response.stop_reason}")
# stop_reason = "tool_use"  → Claude wants to call a tool
# stop_reason = "end_turn"  → Claude is done, giving final answer

for block in response.content:
    print(f"Block type: {block.type}")
    if block.type == 'tool_use':
        print(f"Tool Claude wants to call: {block.name}")
        print(f"With this input: {block.input}")

        # Actually run the tool
        result = calculate(block.input["expression"])
        print(f"Result from our function: {result}")