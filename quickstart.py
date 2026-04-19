import os.path
import base64
from dotenv import load_dotenv

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from email.message import EmailMessage



load_dotenv()

CRED_PATH = os.getenv("GOOGLE_CREDENTIAL_PATH")
TOKEN_PATH = os.getenv("GOOGLE_TOKEN_PATH")
RECIPIENT = os.getenv("EMAIL_RECIPIENT")

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.send", "https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.compose"]



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


# make sure to only have one gmail client at a time
class ClientSingleton:
    """Singleton for managing the client instance."""
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            credentials = get_credentials()
            cls._instance = cls._initialize_client(credentials)
        return cls._instance

    @staticmethod
    def _initialize_client(credentials):
        """Initialize the client with the given credentials."""
        # Example: Replace with actual client initialization logic
        return build("gmail", "v1", credentials=credentials) 



def gmail_send_message(client, message_text):
  """Create and send an email message
  Print the returned  message id
  Returns: Message object, including message id
  """

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
    print(f'Message Id: {send_message["id"]}')

  except HttpError as error:
    print(f"An error occurred: {error}")
    send_message = None

  return send_message 



if __name__ == "__main__":
  gmail_client = ClientSingleton.get_instance()
  test = gmail_send_message(client=gmail_client)
  print(test)