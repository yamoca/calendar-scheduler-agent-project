from typing import TypedDict, Literal

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command, RetryPolicy
from langchain_openrouter import ChatOpenRouter
# from langchain.messages import HumanMessage
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import RetryPolicy
from langchain.tools import tool, ToolRuntime

from langchain_mcp_adapters.client import MultiServerMCPClient

import asyncio

import os
import sys
from dotenv import load_dotenv

# hopefully cleaner async shutdown for dev
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()
if not os.getenv("OPENROUTER_API_KEY"):
    os.environ["OPENROUTER_API_KEY"] = os.getenv('API_KEY') 


class EmailClassification(TypedDict):
    urgency: Literal["low", "medium", "high", "critical"]
    tone: Literal["casual", "neutral", "professional", "formal"]
    topic: str
    summary: str


class EmailAgentState(TypedDict):
    # raw email data
    email_content: str
    sender_email: str
    email_id: str

    # classification result
    classification: EmailClassification | None

    # generated content
    draft_response: str | None
    messages: list[str] | None


mcp_client = MultiServerMCPClient(
    {
        "gmail_api_mcp_server": {
            "transport": "stdio",
            "command": "python",
            "args": ["mcp_server.py"],
            "env": os.environ.copy()
        }
    }
)

MODEL = "nvidia/nemotron-nano-12b-v2-vl:free"

llm = ChatOpenRouter(model=MODEL)




'''extract and parse email content'''
async def read_email(state: EmailAgentState, tools: dict) -> dict:
    print("entered read email node", file=sys.stderr)
    """
    fetch email from gmail via tool on mcp server

    "tools" is a dict of {tool_name: tool_callable} passed in at runtime
    """

    # skip actual fetch when email_content is prepopoluated AKA TEST SCENARIO
    if state.get("email_content"):
        return {
            "message": [HumanMessage(content=f"processing email: {state["email_content"]}")]
        }

    NAME_OF_TOOL_IN_MCP_SERVER = "gmail_get_message_by_id"
    get_email_tool = tools.get(NAME_OF_TOOL_IN_MCP_SERVER)
    if not get_email_tool:
        raise ValueError("MCP tool 'get_email' not found. check mcp_server.py for correct tool name")

    raw = await get_email_tool.ainvoke({"email_id": state["email_id"]})

    return {
        "email_content": raw.get("body", ""),
        # fallback in getting it from state is only for testing where state is prepopulated 
        "sender_email": raw.get("from", state.get("sender_email", "")),
        # this is for logging but bit goof that its counted as a HumanMessage 
        "messages": [HumanMessage(content=f"Fetched email from {raw.get("from")}: {raw.get("body", "")[:100]}")]
    }

def classify_intent(state: EmailAgentState) -> Command[Literal["draft_response"]]:
    print("entered classify intent node", file=sys.stderr)
    """Use LLM to classify email intent and urgency, then route accordingly"""

    # create structured llm that returns emailclassification dict
    structured_llm = llm.with_structured_output(EmailClassification)

    # fromat the prompt on-demand, not stored in state
    classification_prompt = f"""
    Analyze this incoming email and classify it:

    Email: {state['email_content']}
    From: {state['sender_email']}

    Provide classification including urgency, tone, topic, and summary.
    """

    # get structured response directly as dict
    classification = structured_llm.invoke(classification_prompt)

    

    #store classification as a single dict in state
    return Command(
        update={"classification": classification},
        goto="draft_response"
    )




def draft_response(state: EmailAgentState) -> Command[Literal["send_reply"]]:
    print("entered draft response node", file=sys.stderr)
    """generate response useing context and route based on quality"""

    classification = state.get("classification", {})

    # build the prompt with formatted context
    # WILL HAVE TO CHANGE WHEN ADDING CALENDAR INTEGRATIONS BECAUSE OF MEETING GUIDELINES
    draft_prompt = f"""
    Draft a response to this incoming email which has been flagged as relating to meeting up:
    {state['email_content']}

    Email tone: {classification.get("tone", "neutral")}
    Urgency level: {classification.get("urgency", "medium")}

    Guidelines:
    - Write the email in the correct tone as provided 
    - Be direct and clear
    - if a meetup time is already arranged, agree to it
    - if a meetup window is proposed, choose a time within the proposed window
    - if no meetup window is proposed, choose any sensible time 
    - if details are vague, send a clarification email
    - use the provided context
    - reply ONLY with the generated email body, your response will go directly into the email to be seen by the end recipients
    """

    response = llm.invoke(draft_prompt)

    # route to appropriate next node
    goto = "send_reply" 

    return Command(
        update={"draft_response": response.content},
        goto=goto
    )


    

async def send_reply(state: EmailAgentState, tools: dict) -> dict:
    print("entered send reply node", file=sys.stderr)
    """calls the mcp send_email tool directly, no agent needed as we know exactly what to call"""
    NAME_OF_TOOL_IN_MCP_SERVER = "gmail_send_message"
    send_email_tool = tools.get(NAME_OF_TOOL_IN_MCP_SERVER)
    if not send_email_tool:
        raise ValueError("MCP tool 'send_email' not found. check your mcp_server.py tool names")

    # sort this out because its not using the right arguments but should be correct
    await send_email_tool.ainvoke({
        "message_text": state["draft_response"],
        # subject, from, etc handled by mcp server
    })

    # might corrupt stdio
    print(f"sending reply: {state['draft_response'][:100]}...", file=sys.stderr)
    return {}



async def build_graph_and_run():
    async with mcp_client.session("gmail_api_mcp_server"):
        # load all tools once: build lookup dict by tool name
        raw_tools = await mcp_client.get_tools()
        tools = {t.name: t for t in raw_tools}

        print("Available MCP tools: ", list(tools.keys()))

        # wrap the tool using nodes in closuers so they receive "tools"
        async def read_email_node(state):
            return await read_email(state, tools)
        async def send_reply_node(state):
            return await send_reply(state, tools)

        # build the graph
        workflow = StateGraph(EmailAgentState)

        workflow.add_node("read_email", read_email_node)
        workflow.add_node("classify_intent", classify_intent)
        workflow.add_node("draft_response", draft_response)
        workflow.add_node("send_reply", send_reply_node)

        # add only the fixed edges as routing is mainly handled by nodes themselves (goto___)
        workflow.add_edge(START, "read_email")
        workflow.add_edge("read_email", "classify_intent")
        workflow.add_edge("send_reply", END)

        # compile with checkpointer for persistence in case run graph with local_server -> please compile without checkpointer
        memory = MemorySaver()
        app = workflow.compile(checkpointer=memory)

        # start with empty initial state, can prepoluate for testing see commented out initial statevar line 248
        initial_state = {}
        await monitor_inbox(app, tools, initial_state)




# build inbox monitoring loop
async def monitor_inbox(app, tools, initial_state):
    seen_ids = set()

    while True:
        print("checking inbox..", file=sys.stderr)

        # fetch inbox
        get_mesages_tool = tools.get("gmail_get_messages")
        messages = await get_mesages_tool.ainvoke({})

        # process unseen emails
        for message in messages:
            email_id = message["id"]
            if email_id in seen_ids:
                continue
            
            seen_ids.add(email_id)

            #each email gets its own thread_id for independant state / checkpointing so if one needs a human intevention, others can keep running
            config = {"configurable": {"thread_id": email_id}}

            # initial_state = {
            #     "email_content": "hey lets meet up at 5pm tomorrow",
            #     "sender_email": "john@example.com",
            #     "email_id": "email_123",
            #     "classification": None,
            #     "draft_response": None,
            #     "messages": []
            # }

            print(f"processing email {email_id}", file=sys.stderr)
            result = await app.ainvoke(initial_state, config) 
            print(f"result: {result}", file=sys.stderr)
            print(f"messages: {initial_state.get("messages", "no messages found")}", file=sys.stderr)


        await asyncio.sleep(60) # check inbox every minute


##########################################
# test with dummy data




async def test_run(app):
    initial_state = {
        "email_content": "I was charged twice for my subscription! This is urgent!",
        "sender_email": "customer@example.com",
        "email_id": "email_123",
        "classification": None,
        "draft_response": None,
        "messages": []
    }

    # Run with a thread_id for persistence
    config = {"configurable": {"thread_id": "customer_123"}}

    result = await app.ainvoke(initial_state, config)

    print(f"Email sent successfully!")
    print(f"Done. Final state keys:", list(result.keys()))


if __name__ == "__main__":
    asyncio.run(build_graph_and_run())