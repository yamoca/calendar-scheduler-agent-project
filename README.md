# Calendar Scheduler

## Goal
Build an agentic email assistant that monitors a Gmail inbox, classifies incoming meeting requests and drafts contextually appropriate responses - built with LangGraph, Openrouter, and a custom MCP server.


## Current Features
- monitor emails from specific senders to identify meeting requests
- draft suitable response, mirroring language and tone of original email
- send response via gmail api from custom mcp server


## Architecture Diagram
![alt_text](/architecture-diagram.svg "Architecture Diagram")


## Planned
- add calendar integration:
    - check google calendar for availability
    - propose available time in response
    - attach calendar link

