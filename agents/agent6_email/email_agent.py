import anthropic
import smtplib
import os
import hashlib
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv
import PyPDF2

load_dotenv()
client = anthropic.Anthropic()

# ── Global Cost & Tracking State ───────────────────────────
total_input_tokens = 0
total_output_tokens = 0
applied_job_hashes = set()

def sanitize_input(job_post: str) -> str:
    """Removes common prompt injection phrases and wraps in XML tags."""
    malicious_phrases = ["ignore previous instructions", "system prompt", "you are now"]
    sanitized = job_post
    for phrase in malicious_phrases:
        sanitized = re.sub(phrase, "", sanitized, flags=re.IGNORECASE)
    return f"<job_description>\n{sanitized.strip()}\n</job_description>"

# ── Read resume once at start ──────────────────────────────
def read_resume(path: str = "resume.pdf") -> str:
    """Reads PDF resume and returns text"""
    try:
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
        return text
    except Exception as e:
        return f"Error reading resume: {e}"

resume_text = read_resume()
print("Resume loaded successfully\n")



# ── Tools ──────────────────────────────────────────────────
tools = [
    {
        "name": "write_cover_letter",
        "description": """Write a professional, personalized cover letter 
        for a job application based on the job post and resume provided.
        Returns the complete email subject and body.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "Email subject line"
                },
                "body": {
                    "type": "string",
                    "description": "Full cover letter email body"
                }
            },
            "required": ["subject", "body"]
        }
    },
    {
        "name": "send_email",
        "description": "Sends the email with resume attached after user confirms.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to_email": {
                    "type": "string",
                    "description": "Recipient email address"
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject"
                },
                "body": {
                    "type": "string",
                    "description": "Email body"
                }
            },
            "required": ["to_email", "subject", "body"]
        }
    }
]

# ── Tool functions ─────────────────────────────────────────
def write_cover_letter(subject: str, body: str) -> str:
    global total_input_tokens, total_output_tokens
    print("\n🔍 Reviewer Agent is checking the cover letter...")
    
    review_prompt = f"""You are an expert copywriter reviewing a cover letter.
Make sure the tone is professional, grammar is perfect, and it reads naturally.
Fix any issues and return ONLY the final polished cover letter body. Do not include any extra commentary.
    
DRAFT COVER LETTER:
{body}"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            system=review_prompt,
            messages=[{"role": "user", "content": "Review and fix this cover letter."}]
        )
        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens
        
        polished_body = response.content[0].text.strip()
        print("✨ Reviewer Agent has polished the letter.")
        return f"SUBJECT: {subject}\n\nBODY:\n{polished_body}"
    except Exception as e:
        print(f"Reviewer Agent failed: {e}. Using original draft.")
        return f"SUBJECT: {subject}\n\nBODY:\n{body}"

# ── Make resume_path a global so send_email can use it ────
resume_path = None   # declare at top of file

def send_email(to_email: str, subject: str, body: str) -> str:
    try:
        gmail = os.getenv("GMAIL_ADDRESS")
        app_password = os.getenv("GMAIL_APP_PASSWORD")

        msg = MIMEMultipart()
        msg["From"] = gmail
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        # Use the actual path user provided
        if resume_path and os.path.exists(resume_path):
            with open(resume_path, "rb") as f:
                attachment = MIMEBase("application", "octet-stream")
                attachment.set_payload(f.read())
                encoders.encode_base64(attachment)
                attachment.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=os.path.basename(resume_path)  
                )
                msg.attach(attachment)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail, app_password)
            server.sendmail(gmail, to_email, msg.as_string())

        return f"Email sent to {to_email} with {os.path.basename(resume_path)} attached"

    except Exception as e:
        return f"Failed: {e}"

def run_tool(tool_name, tool_input):
    if tool_name == "write_cover_letter":
        return write_cover_letter(
            tool_input["subject"],
            tool_input["body"]
        )
    elif tool_name == "send_email":
        #--------------Human in Loop confirmation------------------#
        print("\n" + "="*50)
        print("-AGENT IS READY TO SEND THE EMAIL-")
        print(f"To:      {tool_input['to_email']}")
        print(f"Subject: {tool_input['subject']}")
        print("="*50)
        confirm = input("\nDo you want to send this email now? (y/n): ").strip()
        if confirm.lower() == 'y':
            print('Sending....')
            return send_email(
                tool_input["to_email"],
                tool_input["subject"],
                tool_input["body"]
            )
        else:
            print("Send cancelled by user.")
            return "User reviewed the draft but chose NOT to send the email. Ask the user what they want to change."
    return f"Unknown tool: {tool_name}"




# ── Memory ─────────────────────────────────────────────────
messages = []

# ── Agent loop ─────────────────────────────────────────────
def chat(user_input):
    global total_input_tokens, total_output_tokens
    print(f"\nYou: {user_input}")
    print("-" * 50)

    # Duplicate check for long inputs (assumed to be job descriptions)
    if len(user_input) > 50:
        job_hash = hashlib.sha256(user_input.encode()).hexdigest()
        if job_hash in applied_job_hashes:
            print("\nDuplicate Detected: You have already processed this exact job post in this session. Skipping to save tokens.")
            return
        applied_job_hashes.add(job_hash)

    sanitized_input = sanitize_input(user_input) if len(user_input) > 50 else user_input

    messages.append({
        "role": "user",
        "content": sanitized_input
    })

    step = 0
    max_steps = 10
    
    # ── System prompt ──────────────────────────────────────────
    system_prompt = f"""
    You are a professional job application assistant.

    The candidate's resume is below:

    {resume_text}

    Your responsibilities:

    1. Carefully analyze the job description provided by the user

    2. Use the write_cover_letter tool to generate a tailored cover letter:
    - Match the candidate's skills and experience with the job requirements
    - Highlight the most relevant achievements
    - Keep the tone professional, concise, and human
    - Write 3-4 short paragraphs
    - End with a polite call to action
    - Avoid exaggeration or false claims

    3. After generating the cover letter:
    - Show the complete draft to the user
    - Ask for confirmation before sending any email

    4. Only call the send_email tool if the user explicitly confirms with messages like:
    - "yes"
    - "send"
    - "confirm"
    - "looks good"
    - or equivalent clear approval

    5. Never send an email without explicit user confirmation.

    Additional rules:
    - Always write professionally
    - Do not invent experience, skills, or achievements
    - Sign the email using the candidate's name from the resume
    """
    while step < max_steps:
        step += 1
        # ── Context Window Management ──────────────────────
        MAX_HISTORY = 20
        if len(messages) > MAX_HISTORY:
            keep_msg = messages[-MAX_HISTORY:]
            if keep_msg[0]["role"] == "assistant":
                keep_msg = keep_msg[1:]
            messages[:] = keep_msg

        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=2048,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"}
                }
            ],
            tools=tools,
            messages=messages
        )
        
        total_input_tokens += (response.usage.input_tokens)
        total_output_tokens += (response.usage.output_tokens)

        # ── Done ──────────────────────────────────────────
        if response.stop_reason == "end_turn":
            assistant_content = []
            for block in response.content:
                if hasattr(block, "text"):
                    print(f"\nAgent: {block.text}")
                    assistant_content.append({
                        "type": "text",
                        "text": block.text
                    })
            if assistant_content:
                messages.append({
                    "role": "assistant",
                    "content": assistant_content
                })
            break

        # ── Tool use ───────────────────────────────────────
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
                        print(f"\nAgent: {block.text.strip()}")

                elif block.type == "tool_use":
                    assistant_message.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input
                    })

                    if block.name == "write_cover_letter":
                        print(f"\n Writing cover letter...")

                    elif block.name == "send_email":
                        print(f"\n Sending email to {block.input['to_email']}...")

                    result = run_tool(block.name, block.input)
                    print(f"\n{result}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            messages.append({
                "role": "assistant",
                "content": assistant_message
            })
            messages.append({
                "role": "user",
                "content": tool_results
            })

# ── Run it ─────────────────────────────────────────────────
if __name__ == "__main__":
    print("Email Agent")
    print("-" * 40)
    print("TIP: Use forward slashes in path. Example:")
    print("     E:/anthropic/kumar_resume.pdf\n")

    resume_path = input("Enter path to your resume: ").strip()
    resume_path = resume_path.replace("\\", "/")  

    if not os.path.exists(resume_path):
        print(f"File not found: {resume_path}")
        print("Make sure the path is correct and file exists.")
        exit()

    resume_text = read_resume(resume_path)
    print(f"Resume loaded — {len(resume_text)} characters read\n")
   
    
    print("Tell me the recruiter's email and paste the job post.")
    print("Type 'exit' to quit.\n")

    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit", "bye"]:
            print("Goodbye!")
            break
        chat(user_input)

    # Calculate and print cost at exit
    cost_in = (total_input_tokens / 1_000_000) * 0.25
    cost_out = (total_output_tokens / 1_000_000) * 1.25
    print("\n" + "="*40)
    print("SESSION COST SUMMARY")
    print(f"Input Tokens:  {total_input_tokens} (${cost_in:.4f})")
    print(f"Output Tokens: {total_output_tokens} (${cost_out:.4f})")
    print(f"Total Cost:    ${cost_in + cost_out:.4f}")
    print("="*40)