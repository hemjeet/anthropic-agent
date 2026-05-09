import anthropic
from dotenv import load_dotenv

# load env
load_dotenv()
# This creates a connection to Claude
client = anthropic.Anthropic()

# ── Tools ────────────────────────────────────────────────────
tools = [
    {
        "name": "calculate",
        "description": "Does math calculations. Pass any math expression.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Math expression like '25 * 4'"
                }
            },
            "required": ["expression"]
        }
    },
    {
        "name": "get_weather",
        "description": "Gets the weather for a city.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name like 'Mumbai' or 'Delhi'"
                }
            },
            "required": ["city"]
        }
    }
]

# ── Tool functions ───────────────────────────────────────────
def calculate(expression):
    try:
        return str(eval(expression))
    except Exception as e:
        return f"Error: {e}"

def get_weather(city):
    # Fake for now — later you can plug in a real weather API
    weather_data = {
        "mumbai": "32°C, humid and partly cloudy",
        "delhi": "38°C, hot and sunny",
        "bangalore": "24°C, pleasant with light breeze"
    }
    return weather_data.get(city.lower(), f"Weather data not available for {city}")


def run_tool(tool_name, tool_input):
    if tool_name == 'calculate':
        return calculate(tool_input["expression"])
    elif tool_name == 'get_weather':
        return get_weather(tool_input["city"])
    else:
        return f"Unknown tool: {tool_name}"
    
# ── The agent loop ───────────────────────────────────────────

def run_agent(user_input):
    print(f"\n{'='*50}")
    print(f"Question: {user_input}")
    print(f"{'='*50}")

    messages = [
        {'role': 'user', 'content': user_input}
    ]
    while True:
        response  = client.messages.create(

            model="claude-haiku-4-5",  # which Claude model to use
            max_tokens=1024, 
            tools= tools,
            messages= messages
        )
        print(f"\nClaude's status: {response.stop_reason}")
        
        # ── Case 1: Claude is done, give final answer ────────
        if response.stop_reason == 'end_turn':
            for block in response.content:
                if hasattr(block, 'text'):
                    print(f"\n✅ Final Answer: {block.text}")
            break

        # ── Case 2: Claude wants to use a tool ──────────────
        if response.stop_reason == 'tool_use':      
            assistant_message = []
            tool_results = []

            for block in response.content:
                    if block.type == 'text':
                        assistant_message.append({
                            "type": "text",
                            "text": block.text
                        })
                        print(f"Claude says: {block.text}")

                    elif block.type == 'tool_use':
                        assistant_message.append({
                            "type": "tool_use",
                            "id": block.id,        # unique ID — only added once
                            "name": block.name,
                            "input": block.input
                        })
                        print(f"\n🔧 Claude is calling: {block.name}")
                        print(f"   Input: {block.input}")

                        result = run_tool(block.name, block.input)
                        print(f"   Result: {result}")
                    
                        # Package the result to send back
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,  # must match the tool call
                            "content": result
                        })
        # ✅ Add assistant message ONCE
        messages.append({
            "role": "assistant",
            "content": assistant_message
        })

        # ✅ Add tool results ONCE
        messages.append({
            "role": "user",
            "content": tool_results
        })

if __name__ == '__main__':
    run_agent("What's the weather in Mumbai and also what is 15% of 8500?")

