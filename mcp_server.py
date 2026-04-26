# log to stderr rather than stdio cause might interfere 
import sys

import re

# mcp
from mcp.server.fastmcp import FastMCP

# dotenv
from dotenv import load_dotenv

# gmail api
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from email.message import EmailMessage

# utility
import os.path
import base64

from typing import Literal
from functools import lru_cache

from gmail_scheduler_agent import CalendarEvent

# initialise sensitive variables
load_dotenv()

CRED_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH")
TOKEN_PATH = os.getenv("GOOGLE_TOKEN_PATH")
RECIPIENT = os.getenv("EMAIL_RECIPIENT")

# If modifying these scopes, delete the file token.json (because a new one needs to be generated)
SCOPES = ["https://www.googleapis.com/auth/gmail.send", "https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.compose", "https://www.googleapis.com/auth/calendar.events"]



mcp = FastMCP("demo")

# agent will only ingest emails from allowed senders
allowed_senders = ["leojwgulliver@gmail.com", "ljgulliver256@gmail.com"]




def get_credentials():
  '''Load pre-authorized user credentials from the environment.
  TODO(developer) - See https://developers.google.com/identity
  for guides on implementing OAuth2 for the application.
  '''

  creds = None
  # The file GOOGLE_TOKEN_PATH stores the user's access and refresh tokens, and is
  # created automatically when the authorization flow completes for the first
  # time.
  if os.path.exists(TOKEN_PATH):
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
  # If there are no (valid) credentials available, let the user log in.
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
      flow = InstalledAppFlow.from_client_secrets_file(
          CRED_PATH, SCOPES
      )
      creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open(TOKEN_PATH, "w") as token:
      token.write(creds.to_json())

  return creds




"""
the try except wont actually help with credential refreshs or anything 
because once cached this function never evaluates again

fix is to place the try except in a with_client_retry function 
then from the mcp tools call the with client retry function with the desired action

but keep it simple for now so just use this because creds probs wont expire while testing

also apparently no auth errors happen on build so not needed anyway
"""
@lru_cache(maxsize=2) # should only be getting gmail v1 and calendar v3
def get_google_client(service: Literal["gmail", "calendar"], version: str):
    creds = get_credentials()
    try:
       return build(service, version, credentials=creds, cache_discovery=False)
    except: # auth error
       get_google_client.cache_clear()
       return get_google_client(service, version)
       


# not async because gmail api client not async too old or smth
@mcp.tool()
def gmail_send_message(message_text: str):
    """Create and send an email message
    Print the returned  message id
    Returns: Message object, including message id
    """

    client = get_google_client("gmail", "v1") 

    try:
        message = EmailMessage()

        message.set_content(message_text)

        message["To"] = RECIPIENT 
        message["From"] = "test" # doesnt matter what you put in here it will just treat it as sent from whoevers email logged into api
        message["Subject"] = "Sent by an ai"

        # encoded message
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        create_message = {"raw": encoded_message}
        # dynamic attribute generation therefore:
        # pylint: disable=E1101
        send_message = (
            client.users()
            .messages()
            .send(userId="me", body=create_message)
            .execute()
        )
        # print(f'Message Id: {send_message["id"]}', file=sys.stderr)
        return {"status": "success", "message_id": send_message["id"]}

    except HttpError as error:
        return {"status": "error", "error": str(error)}


@mcp.tool()
def gmail_get_messages():
    # make sure to label read messages so ai doesnt loop
    client = get_google_client("gmail", "v1") 

    # build query
    query = f"from:({" OR ".join(allowed_senders)}) after:2026/01/01"

    results = client.users().messages().list(userId="me", labelIds=["INBOX", "UNREAD"], q=query, maxResults=5).execute()
    messages = results.get("messages", [])
    # firstmessage = messages[0]
    # email1 = client.users().messages().get(userId="me", id=firstmessage["id"]).execute()
    return messages
    # print(email1)
    # print(email1["snippet"])
    # headers = email1["payload"]["headers"]
    # sender = next((header["value"] for header in headers if header["name"] == "From"), "Unkown")
    # print(sender)


@mcp.tool()
def gmail_get_message_by_id(email_id: str):
    client = get_google_client("gmail", "v1") 
    result = client.users().messages().get(userId="me", id=email_id, format="full").execute()

    body = result.get("snippet")
    # print(body)

    headers = result["payload"]["headers"]
    sender_address_and_name = next(header["value"] for header in headers if header["name"] == "From")
    match = re.search(r"<(.*)>", sender_address_and_name)
    if match:
       sender_address = match.group(1)
    else:
       sender_address = sender_address_and_name

    # print(sender_address)

    return {
       "body": body,
       "from": sender_address
    }



def calendar_create_event(event: CalendarEvent):

    client = get_google_client("calendar", "v3")    

    attendees = [{"email": attendant} for attendant in event["attendees"]]
    json_event = {
        "summary": event["summary"],
        "location": event["location"],
        "description": event["description"],
        "start": {
           "dateTime": event["start"],
        },
        "end": {
           "dateTime": event["end"],
        },
        "attendees": attendees
    }

    event = client.events().insert(calendarId="primary", body=json_event).execute()
    print("event created: %s" % (event.get("htmlLink")))
  


if __name__ == "__main__":
    # mcp.run()
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("Europe/London"))
    start_time = (now.replace(hour=10, minute=0, second=0, microsecond=0))
    end_time = start_time + timedelta(hours=1)

    testEvent = CalendarEvent(
        summary="AI Agent Design Sync",
        start=start_time.isoformat(),
        end=end_time.isoformat(),
        attendees=["lpage@example.com", "sbrin@example.com"],
        location="London Office",
        description="Discussion on MCP tools, client caching, and agent architecture."
    )

    calendar_create_event(testEvent)
