import anthropic
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup

load_dotenv()
client = anthropic.Anthropic()

# ── Tools ──────────────────────────────────────────────────
tools = [
    {
        "name": "search_web",
        "description": """Search the internet for any topic and get 
        back results with titles, links and summaries.
        Always use this FIRST when researching anything.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query. Be specific for better results."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "fetch_page",
        "description": """Read the full content of a webpage given its URL.
        Use this AFTER search_web to get detailed information 
        from a specific page.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Full URL of the webpage to read."
                }
            },
            "required": ["url"]
        }
    }
]

# ── Tool functions ─────────────────────────────────────────
def search_web(query: str) -> str:
    """
    Uses DuckDuckGo HTML search — much better results than the API.
    No API key needed.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
        response = requests.get(url, headers=headers, timeout=10)

        soup = BeautifulSoup(response.text, "html.parser")

        results = []
        # DuckDuckGo HTML results are in elements with class "result__body"
        for result in soup.find_all("div", class_="result__body")[:5]:
            title = result.find("a", class_="result__a")
            snippet = result.find("a", class_="result__snippet")
            link = result.find("a", class_="result__url")

            if title and snippet:
                results.append(f"Title: {title.get_text()}")
                results.append(f"Snippet: {snippet.get_text()}")
                if link:
                    results.append(f"URL: https://{link.get_text().strip()}")
                results.append("")

        if results:
            return "\n".join(results)
        else:
            return f"No results found for '{query}'"

    except Exception as e:
        return f"Search failed: {e}"


def fetch_page(url: str) -> str:
    """
    Downloads a webpage and returns clean text.
    Strips all HTML — only keeps readable content.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()   # raises error if page not found

        # Parse HTML
        soup = BeautifulSoup(response.text, "html.parser")

        # Remove useless tags
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        # Extract clean text
        text = soup.get_text(separator="\n")

        # Remove blank lines
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        clean_text = "\n".join(lines)

        # Return first 3000 chars — enough for Claude to work with
        if len(clean_text) > 3000:
            return clean_text[:3000] + "\n...[page truncated]"
        return clean_text

    except Exception as e:
        return f"Could not fetch page: {e}"


def run_tool(tool_name, tool_input):
    if tool_name == "search_web":
        return search_web(tool_input["query"])
    elif tool_name == "fetch_page":
        return fetch_page(tool_input["url"])
    return f"Unknown tool: {tool_name}"


# ── System prompt ──────────────────────────────────────────
system_prompt = """You are a thorough web research assistant.

When given a research question:
1. ALWAYS start by searching the web first
2. If a result looks useful, fetch that page for more detail
3. Search multiple times with different queries if needed
4. Give a clear, well structured summary at the end
5. Always mention your sources at the end

Be thorough. Don't answer from memory — always search first."""


# ── Memory ─────────────────────────────────────────────────
messages = []


# ── Chat function ──────────────────────────────────────────
def chat(user_input):
    print(f"\nYou: {user_input}")
    print("-" * 40)

    messages.append({
        "role": "user",
        "content": user_input
    })

    step = 1

    while True:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=2048,
            system=system_prompt,
            tools=tools,
            messages=messages
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    print(f"\nAssistant: {block.text}")
                    messages.append({
                        "role": "assistant",
                        "content": block.text
                    })
            break

        if response.stop_reason == "tool_use":
            assistant_message = []
            tool_results = []

            for block in response.content:
                if block.type == "text":
                    assistant_message.append({
                        "type": "text",
                        "text": block.text
                    })
                    if block.text.strip():
                        print(f"\n💭 {block.text.strip()}")

                elif block.type == "tool_use":
                    assistant_message.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input
                    })

                    # Show what's happening
                    if block.name == "search_web":
                        print(f"\n🌐 Step {step}: Searching '{block.input['query']}'...")
                    elif block.name == "fetch_page":
                        print(f"\n📄 Step {step}: Reading {block.input['url'][:60]}...")

                    step += 1

                    result = run_tool(block.name, block.input)

                    # Show a short preview
                    preview = result[:120] + "..." if len(result) > 120 else result
                    print(f"   → {preview}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            messages.append({"role": "assistant", "content": assistant_message})
            messages.append({"role": "user", "content": tool_results})


# ── Run it ─────────────────────────────────────────────────
if __name__ == "__main__":
    print("🔍 Web Research Agent ready!")
    print("   Ask me to research anything.")
    print("   Type 'exit' to quit.\n")

    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit", "bye"]:
            print("Goodbye!")
            break
        chat(user_input)