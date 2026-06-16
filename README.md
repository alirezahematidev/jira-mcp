# jira-mcp

A [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server for
**Atlassian Jira** (self-hosted Server / Data Center), written in Python. It
lets MCP-compatible clients (Claude Desktop, Claude Code, Cursor, etc.) search,
read, and manage Jira issues, projects, comments, workflow transitions,
worklogs, and agile boards.

Targets the company's self-hosted Jira at `https://works.digikala.com` over the
REST API v2 with HTTP basic auth — you only supply your email and API token.

## Features

| Tool | Description |
| --- | --- |
| `get_current_user` | Who am I? (connectivity check) |
| `search_issues` | Search issues with JQL |
| `get_issue` | Fetch one issue (optionally with comments) |
| `get_comments` | List an issue's comments |
| `list_transitions` | Available workflow transitions for an issue |
| `list_projects` | List accessible projects |
| `get_project` | Fetch one project |
| `search_users` | Find users (returns account ids for assignment) |
| `list_boards` | List agile boards |
| `list_sprints` | List sprints on a board |
| `create_issue` | Create an issue |
| `update_issue` | Update fields on an issue |
| `add_comment` | Comment on an issue |
| `transition_issue` | Move an issue through its workflow |
| `assign_issue` | Assign / unassign an issue |
| `add_worklog` | Log time against an issue |
| `link_issues` | Link two issues |
| `delete_issue` | Delete an issue (guarded) |

Write tools can be disabled entirely with `JIRA_READ_ONLY=true`.

## Installation

Requires Python 3.10+. The package is distributed via GitHub.

### Install as a tool (recommended)

Install once into an isolated environment — fast to launch afterwards (no
re-download or rebuild per run), which matters when an MCP client spawns the
server repeatedly:

```bash
uv tool install git+https://github.com/alirezahematidev/jira-mcp
# or:
pipx install git+https://github.com/alirezahematidev/jira-mcp
```

This puts a `jira-mcp` executable on your `PATH`. Find it with `which jira-mcp`.

To update later: `uv tool upgrade jira-mcp` (or `pipx upgrade jira-mcp`).

### From source (development)

```bash
git clone https://github.com/alirezahematidev/jira-mcp
cd jira-mcp
uv pip install -e ".[dev]"   # or: pip install -e ".[dev]"
```

> **Tip:** avoid `uvx --from git+...jira-mcp` in an MCP client config — it
> re-resolves the package on every launch and is noticeably slow. Install once
> (above) and point the client at the installed executable instead.

## Configuration

The Jira host (`https://works.digikala.com`) and basic authentication are
built in — you only need to provide your credentials via environment variables
(or a `.env` file; copy `.env.example` to `.env`):

```bash
JIRA_EMAIL=you@digikala.com
JIRA_API_TOKEN=your-api-token
```

Use the login (email or username) and password / API token you use for the
self-hosted Jira.

### Optional settings

| Variable | Default | Meaning |
| --- | --- | --- |
| `JIRA_URL` | `https://works.digikala.com` | Override the host only if it moves |
| `JIRA_TIMEOUT` | `30` | HTTP timeout (seconds) |
| `JIRA_VERIFY_SSL` | `true` | Verify TLS certificates |
| `JIRA_READ_ONLY` | `false` | Disable all write/delete tools |

## Running

```bash
jira-mcp          # console script (stdio transport)
python -m jira_mcp # equivalent
```

The server speaks MCP over stdio, so it's normally launched by an MCP client
rather than run by hand.

### Claude Desktop / Claude Code

Add to your MCP config (e.g. `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "jira": {
      "command": "jira-mcp",
      "env": {
        "JIRA_EMAIL": "you@digikala.com",
        "JIRA_API_TOKEN": "your-api-token"
      }
    }
  }
}
```

If the client can't find `jira-mcp` on its `PATH`, use the absolute path from
`which jira-mcp` (e.g. `/Users/you/.local/bin/jira-mcp`) as `"command"`.

## Usage notes

- **JQL** is the most powerful entry point, e.g.
  `project = PROJ AND assignee = currentUser() AND status != Done ORDER BY updated DESC`.
- **Assigning users**: `assignee` is a username — call `search_users` first to
  find it.
- **Transitions**: status names aren't passed directly. Call `list_transitions`
  to get a valid `transition_id`, then `transition_issue`.
- **Rich text**: descriptions and comments are plain text (Jira wiki markup is
  accepted).

## Development

```bash
uv pip install -e ".[dev]"
pytest          # run the test suite
ruff check .    # lint
```

The tests mock the Jira HTTP API with `respx`, so no live Jira instance is
needed.

### Building & publishing

```bash
uv build              # produces dist/*.whl and dist/*.tar.gz
uvx twine check dist/* # validate package metadata
```

Releases are automated: pushing a `vX.Y.Z` tag triggers
[`.github/workflows/publish.yml`](.github/workflows/publish.yml), which builds
the package and publishes it to PyPI via
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC, no API
token stored). Bump `__version__` in
[`src/jira_mcp/__init__.py`](src/jira_mcp/__init__.py), update
[`CHANGELOG.md`](CHANGELOG.md), then tag.

## License

MIT
