import anthropic
from dotenv import load_dotenv

# load env
load_dotenv()

# This creates a connection to Claude
client = anthropic.Anthropic()

# This sends a message to Claude
response = client.messages.create(
    model="claude-haiku-4-5",  # which Claude model to use
    max_tokens=1024,                    # max length of reply
    messages=[
        {"role": "user", "content": "Say hello!"}
    ]
)

# This prints Claude's reply
print(response.content[0].text)