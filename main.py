from openai import OpenAI
from dotenv import load_dotenv
import os
import json

from quickstart import *

gmail_client = create_gmail_api_client()

load_dotenv()

API_KEY = os.getenv('API_KEY')

# need a tool calling model
MODEL = "nvidia/nemotron-3-nano-30b-a3b:free"

client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=API_KEY
)


task = "send a polite greeting email with a simple message of your choice. Everything apart from the message body is handled for you, so dont worry about the recipient, subject, etc"

messages = [
  {
    "role": "system",
    "content": "you are a helpful assistant."
  },
  {
    "role": "user",
    "content": task,
  }
]


tools = [{
  "type": "function",
  "function": {
  "name": "send_email",
  "description": "send an email with gmail",
  "parameters": {
    "type": "object",
    "properties": {
      "message_text": {
        "type": "string",
        "description": "The body of the email to be sent."
      }
    },
    "required": ["message_text"]
    } 
  }
}]

TOOL_MAPPING = {
    "send_email": gmail_send_message
}

request_1 = {
  "model": MODEL,
  "tools": tools,
  "messages": messages
}

# should check the finish_reason to make sure it actually wants to call the tool but do that later
response_1 = client.chat.completions.create(**request_1).choices[0].message
print(response_1)

# append response to message array so llm has full context
messages.append(response_1)


# Now we process the requested tool calls, and use our book lookup tool
for tool_call in response_1.tool_calls:
    '''
    In this case we only provided one tool, so we know what function to call.
    When providing multiple tools, you can inspect `tool_call.function.name`
    to figure out what function you need to call locally.
    '''
    tool_name = tool_call.function.name
    tool_args = json.loads(tool_call.function.arguments)
    tool_response = TOOL_MAPPING[tool_name](**tool_args, client=gmail_client)
    messages.append({
      "role": "tool",
      "tool_call_id": tool_call.id,
      "content": json.dumps(tool_response),
    })


request_2 = {
  "model": MODEL,
  "messages": messages,
  "tools": tools
}

response_2 = client.chat.completions.create(**request_2)

print(response_2.choices[0].message.content)

'''
completion = client.chat.completions.create(
  model=MODEL,
  messages=[
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "send a polite greeting email"
        }
      ]
    }
  ],
  tools=[
      {
        "type": "function",
        "function": {
        "name": "send_email",
        "description": "send an email with gmail",
        "parameters": {
          "type": "object",
          "properties": {
            "message_text": {
              "type": "string",
              "description": "The body of the email to be sent."
            }
          },
          "required": ["message_text"]
        } 
      }
    }
  ]
)
print(completion.choices[0].message.content)
'''