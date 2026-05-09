# Anthropic Claude Agents Collection

A collection of AI agents built using the Anthropic Claude API, ranging from basic conversation loops to advanced data analysis and web research.

## Structure

```
agents/
│
├── agent1_basic_loop/
│   └── agent1.py          # Basic agent with tool use
│
├── agent2_system_prompt/
│   └── agent2.py          # Agent guided by system prompts
│
├── agent3_memory/
│   └── agent3.py          # Chat agent with conversation memory
│
├── agent4_data_analyst/
│   ├── agent4.py          # CLI-based Data Analyst agent
│   └── app.py             # Streamlit UI for Data Analyst agent
│
├── agent5_web_research/
│   └── agent5.py          # Web Research agent
│
└── agent6_email/
    └── email_agent.py     # Email management agent
```

## Setup & Installation

1. Clone the repository.
2. Copy `.env.example` to `.env` and configure your keys:
   - `ANTHROPIC_API_KEY`: Your Claude API key.
   - `GMAIL_APP_PASSWORD` & `GMAIL_ADDRESS`: Required for the email agent.
3. Install dependencies:
   ```bash
   pip install anthropic python-dotenv pandas streamlit beautifulsoup4 requests
   ```
4. Run the agents individually using `python agents/agentX_folder/script.py`. For the data analyst UI, run `streamlit run agents/agent4_data_analyst/app.py`.
