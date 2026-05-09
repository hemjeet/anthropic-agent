import anthropic
from dotenv import load_dotenv

# load env
load_dotenv()
# This creates a connection to Claude
client = anthropic.Anthropic()

message = []
print("Chat with Claude! Type 'quit' to stop.\n")
while True:
    user_input = input("You:")
    if user_input.lower() == 'quit':
        break
    message.append({
        "role": "user",
        "content": user_input
    })

    response = client.messages.create(
    model="claude-haiku-4-5",  # which Claude model to use
    max_tokens=1024,                    # max length of reply
    messages= message
)
    
    reply = response.content[0].text

    #add claudes reply
    message.append({
        "role": "assistant",
        "content": reply
    })
    print(f"Claude: {reply}\n")