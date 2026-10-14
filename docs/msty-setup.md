# Msty Studio as the mouth of the knowledge base

Msty Studio is where you ask questions. It does not build the knowledge base; `ingest.py` and the Thursday session do that. Msty reads what they produce.

Verified against Msty Studio 2.8.3 and docs.msty.ai on 2026-10-14. Steps marked "verify" could not be confirmed from the docs and need one click to test.

## 1. Connect your models

Your eight models live in the system Ollama on port 11434. Msty's own Local AI service (port 11964) holds only `qwen3:0.6b` and was not responding at the time of writing. Connect Msty to the system Ollama instead of downloading twice.

Path A, try first:

1. Open Model Hub, then Model Providers, then Add Provider.
2. Select Msty Remote.
3. In Inference Endpoint enter `http://127.0.0.1:11434`.
4. Save. Open a conversation and check that `granite4.2:8b` appears in the model list.

Msty Remote speaks the Ollama API, which is exactly what the system Ollama serves. The docs only show it used against another machine's Msty Local AI, so this is a verify step. If the model list stays empty, use path B.

Path B, fallback:

1. Settings, then Local AI, then Models Path.
2. Set it to `/Users/hirenbudhrani/.ollama/models`.
3. Save Changes and Restart Service.

Msty's Local AI is an Ollama fork with the same on-disk layout, so it will list the same models. Both services then read one folder. Do not run a download in both at the same time.

## 2. Enable tools and embedding on the models

Models have Tools disabled as a purpose by default.

1. In a conversation, open the model dropdown and select the edit icon next to `granite4.2:8b`.
2. Turn on Tools as a purpose. Repeat for `qwen3:4b`.
3. For `nomic-embed-text`, turn on Embedding as a purpose.

`qwen2.5-coder:7b` has no tool support in its chat template. Use it for plain questions only.

## 3. Build the Knowledge Stack

1. Open Knowledge Stacks. In the bottom-left dropdown select Switch to Next Gen Knowledge Stack. Next Gen adds folder watching.
2. Create a new stack. Title: `Portal KB`. Keep one stack per topic; this one is the portal.
3. Add two Folders:
   - `/Users/hirenbudhrani/Herd/RAGgamuffin/vault/concepts`
   - `/Users/hirenbudhrani/Herd/documentation`
4. On each folder, enable the watch mode that composes changes automatically. Then Thursday's output appears in Msty without you touching it.
5. Compose Settings: Embedding Model `nomic-embed-text` (needs step 2). Chunking Method: Sentence. Leave Chunk Size at the default for the first run.
6. Select Compose.

Attach it in any chat with the Knowledge Stack icon in the conversation toolbar. Select Portal KB. Expand Configure to raise the number of chunks retrieved if answers feel thin.

## 4. Give it hands: the portal tools

The Toolbox is Msty's MCP implementation. Reuse the two servers you already have.

Toolbox, then Add New Tool, then STDIO / JSON, then paste one of these as Tool Configuration.

Code graph of the portal (already indexed for Claude Code):

```json
{ "command": "/Users/hirenbudhrani/.local/bin/codebase-memory-mcp", "args": [], "env": {} }
```

Read-only file access to the portal and the vault:

```json
{ "command": "/opt/homebrew/bin/npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem",
           "/Users/hirenbudhrani/Herd/portal.mogelijk.nl",
           "/Users/hirenbudhrani/Herd/RAGgamuffin/vault"],
  "env": {} }
```

Test each in the Tool Console. Then Add New Toolset, name it `Portal tools`, enable both, Add. In a chat, select the Toolset icon and pick Portal tools. A warning about tool support means step 2 was skipped for that model.

## 5. The persona that teaches

Persona Studio, Assistant Persona. Name: `Portal Guide`. Attach the Portal KB stack under add-ons. System prompt, with System Prompt Attach Mode set to Replace:

```
You explain the portal.mogelijk.nl codebase to a developer who learns visually and is new to this code.
Answer in this order: one plain sentence, then a Mermaid diagram when the question is about a flow, then where it lives in code with exact file paths, then what to read next.
Search the knowledge stack first. Use the tools to confirm a file or class exists before you name it. If you cannot confirm, say so.
Short sentences. No jargon without a one-line explanation.
```

Start chats from New, then New Persona Conversation, or type `@` in any chat to pick it.

## 6. Compare models: Split Chat

New, then Split Chat. Add two or three panes, pick a different model per pane, turn on duplication mode so one message goes to all. Save as a preset named `Model bake-off`. Use it when a new model lands.

## 7. Thursday inside Msty

Settings, then Agent Mode. Claude Code is one of the three supported agents and uses your subscription. Once detected, start a session from New targeting the RAGgamuffin workspace and run the ingest skill from there. Same session, same window, no terminal needed.

## What Msty does not do

Msty does not run on a schedule and does not watch git. That is Msty Claw's job, later, under roadmap item n7. Msty also cannot run a local script as a Live Context; Live Contexts are HTTP only.
