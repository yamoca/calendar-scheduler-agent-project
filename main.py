from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

API_KEY = os.getenv('API_KEY')

client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=API_KEY
)

completion = client.chat.completions.create(
  extra_headers={
    "HTTP-Referer": "<YOUR_SITE_URL>", # Optional. Site URL for rankings on openrouter.ai.
    "X-OpenRouter-Title": "<YOUR_SITE_NAME>", # Optional. Site title for rankings on openrouter.ai.
  },
  extra_body={},
  model="google/gemma-3n-e4b-it:free",
  messages=[
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "What is in this image?"
        }#,
        # {
        #   "type": "image_url",
        #   "image_url": {
        #     "url": "https://live.staticflickr.com/3851/14825276609_098cac593d_b.jpg"
        #   }
        # }
      ]
    }
  ]
)
print(completion.choices[0].message.content)
