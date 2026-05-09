import anthropic
from dotenv import load_dotenv
import datetime

# load env
load_dotenv()
# This creates a connection to Claude
client = anthropic.Anthropic()

# ── Tools ─────────────────────────────────────────────────
tools = [
    {
        "name": "calculate",
        "description": "Perform any math calculation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Math expression like '200 * 12'"
                }
            },
            "required": ["expression"]
        }
    },
    {
        "name": "get_current_date",
        "description": "Returns today's date and current time.",
        "input_schema": {
            "type": "object",
            "properties": {}  # no inputs needed
        }
    },
    {
        "name": "convert_currency",
        "description": "Converts an amount from one currency to another.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "description": "The amount to convert"
                },
                "from_currency": {
                    "type": "string",
                    "description": "Currency to convert from. Example: USD, INR, EUR"
                },
                "to_currency": {
                    "type": "string",
                    "description": "Currency to convert to. Example: USD, INR, EUR"
                }
            },
            "required": ["amount", "from_currency", "to_currency"]
        }
    }
]

# ── Tool functions ─────────────────────────────────────────
def calculate(expression):
    try:
        return str(eval(expression))
    except Exception as e:
        return f"Error: {e}"

def get_current_date():
    now = datetime.datetime.now()
    return f"Today is {now.strftime('%A, %B %d %Y')}. Current time: {now.strftime('%I:%M %p')}"

def convert_currency(amount, from_currency, to_currency):
    # Fixed rates for learning purposes
    # In a real agent you'd call a currency API here
    rates_to_usd = {
        "USD": 1.0,
        "INR": 0.012,
        "EUR": 1.08,
        "GBP": 1.27
    }

    if from_currency not in rates_to_usd or to_currency not in rates_to_usd:
        return f"Sorry, I only support USD, INR, EUR, GBP"

    in_usd = amount * rates_to_usd[from_currency]
    result = in_usd / rates_to_usd[to_currency]
    return f"{amount} {from_currency} = {result:.2f} {to_currency}"

def run_tool(tool_name, tool_input):
    if tool_name == 'calculate':
        return calculate(tool_input['expression'])
    elif tool_name == 'get_current_date':
        return get_current_date()
    elif tool_name == 'convert_currency':
        return convert_currency(
            tool_input['amount'],
            tool_input['from_currency'],
            tool_input['to_currency']
        )
    return f"Unknown tool: {tool_name}"
# ── Agent loop ─────────────────────────────────────────────

def run_agent(user_input):
    print(f"\nYou: {user_input}")
    print("-" * 40)
    
    system_prompt = """You are a helpful personal assistant.You help with math, dates, and currency conversions.
    Always be clear and concise in your answers.If you need to do a calculation, use the calculate tool.
    If asked about today's date or time, use get_current_date tool."""

    messages = [
        {"role": "user", "content": user_input}
    ]

    while True:
        response  = client.messages.create(

            model="claude-haiku-4-5",  # which Claude model to use
            max_tokens=1024, 
            tools= tools,
            system=system_prompt,
            messages= messages
        )
        print(f"\nClaude's status: {response.stop_reason}")

        if response.stop_reason == 'end_turn':
            for block in response.content:
                if hasattr(block, "text"):
                    print(f"Assistant: {block.text}")
            break

        if response.stop_reason == 'tool_use':
            assistant_message = []
            tool_results = []

            for block in response.content:
                if block.type == 'text':
                    assistant_message.append({
                        "type": "text",
                        "text": block.text
                    })

                elif block.type == 'tool_use':
                    assistant_message.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input
                    })

                    print(f"[using {block.name}...]")
                    result = run_tool(block.name, block.input)
                    tool_results.append({
                        'type': 'tool_result',
                        'tool_use_id': block.id,
                        'content': result
                    })
        messages.append({"role": "assistant", "content": assistant_message})
        messages.append({"role": "user", "content": tool_results})



if __name__ == '__main__':
    run_agent("What is today's date and what is 15% tip on a bill of 2400 rupees?")
    run_agent("Convert 500 USD to INR")
    run_agent("If I save 8500 rupees every month for 2 years, how much will I have?")
