# Connecting a client

Primary setup: **OpenCode** in the terminal (standalone, or inside VS Code's integrated terminal).
It is open source, works with any OpenAI-compatible server, supports MCP tools, and edits files / runs
commands as an agent, so no IDE extension is needed.

## OpenCode (recommended)

1. Install: `npm install -g opencode-ai` (needs Node.js), or see the OpenCode docs for other installers.
2. Copy `opencode.json` from this folder to `%USERPROFILE%\.config\opencode\opencode.json` (global) or into
   a Java project's root (per project). Replace `C:/path/to/NepcodeLLM` with your clone path (forward slashes are fine).
3. Start the model (`scripts\windows\serve.ps1`), then run `opencode` in your project folder. (SearXNG in Docker is
   optional; without it web search uses the built-in ddgs backend.)

What the config does:
- `provider.nepcode`: points OpenCode at llama-server (`http://127.0.0.1:8080/v1`, model `nepcode`).
  Keep `limit.context` equal to `serve.ps1 -Ctx`.
- `instructions`: loads `prompts/system.md` (Java specialist + research policy) in every session.
- `mcp.nepcode`: the research tools (`web_search`, `fetch_url`, `kb_search`, `kb_save_note`).

Per-project rules: put an `AGENTS.md` in a Java project's root (build command, Java version, conventions);
OpenCode reads it automatically. `/init` inside OpenCode can generate a first version.

## Other clients

Any client with OpenAI-compatible endpoints + MCP works with the same two pieces:

| Setting  | Value                        |
|----------|------------------------------|
| Base URL | `http://127.0.0.1:8080/v1`   |
| Model    | `nepcode`                    |
| API key  | any non-empty string         |

`mcp-servers.json` is the standard `mcpServers` block (Cline, Roo Code and others).
Alternatives: Qwen Code (terminal, tuned for Qwen models), Cline or Continue (VS Code extensions).

Tip for local models: keep the number of enabled MCP tools small. Every tool description costs prompt tokens,
and prompt processing is the slowest part when experts live in RAM.
