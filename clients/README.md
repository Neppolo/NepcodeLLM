# Connecting a coding client

The model is served by `scripts/windows/serve.ps1` as an **OpenAI-compatible** API:

| Setting  | Value                        |
|----------|------------------------------|
| Base URL | `http://127.0.0.1:8080/v1`   |
| Model    | `nepcode`                    |
| API key  | any non-empty string         |

The research tools are an **MCP server** (`nepcode serve`, stdio). `mcp-servers.json` is the standard
`mcpServers` block used by Cline, Roo Code, Claude Desktop-style configs and others; fix the path and paste it
into your client's MCP settings. Paste `prompts/system.md` as the custom system prompt / rules.

Recommended clients for agentic coding with a local model (all support OpenAI-compatible endpoints + MCP):
- **Cline / Roo Code** (VS Code) - agent that edits files and runs commands.
- **Continue** (VS Code / IntelliJ) - chat + agent; good if you live in IntelliJ for Java.
- **OpenCode** / **Aider** (terminal).

Client settings that matter for a local model:
- Set the context window to the value you pass to `serve.ps1 -Ctx` (default 65536).
- Keep the client's tool/MCP list small: every tool description costs prompt tokens and prompt processing time.
