# Jira + GitHub MCP Servers

Two Model Context Protocol (MCP) servers that let Claude interact with **Jira** and **GitHub** directly from chat.

---

## Directory Structure

```
mcp-servers/
├── jira_mcp/
│   ├── server.py          ← Jira MCP server
│   ├── requirements.txt
│   └── .env.example
├── github_mcp/
│   ├── server.py          ← GitHub MCP server
│   ├── requirements.txt
│   └── .env.example
└── README.md
```

---

## Prerequisites

- Python 3.11+
- [Claude Desktop](https://claude.ai/download) (or any MCP-compatible client)
- Jira Cloud account with API access
- GitHub account with a Personal Access Token

---

## 1 — Install Dependencies

```bash
# Jira server
cd jira_mcp
pip install -r requirements.txt

# GitHub server
cd ../github_mcp
pip install -r requirements.txt
```

---

## 2 — Get Your Credentials

### Jira API Token
1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click **Create API token**, give it a label, copy the value
3. You'll need: your Jira domain, email address, and the token

### GitHub Personal Access Token
1. Go to https://github.com/settings/tokens
2. Generate a **Classic** token with scopes: `repo`, `read:org`, `read:user`
   _(or use a Fine-Grained Token scoped to specific repos)_
3. Copy the `ghp_...` value

---

## 3 — Configure Claude Desktop

Open your Claude Desktop config file:

| Platform | Path |
|----------|------|
| macOS    | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows  | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux    | `~/.config/Claude/claude_desktop_config.json` |

GitHub Copilot setup/configuration in the same style, you can use:

Platform	GitHub Copilot Configuration / Extension Location
macOS	~/.vscode/extensions/github.copilot-*
Windows	%USERPROFILE%\.vscode\extensions\github.copilot-*
Linux	~/.vscode/extensions/github.copilot-*

Add both servers under `"mcpServers"`:

```json
{
  "mcpServers": {
    "jira": {
      "command": "python",
      "args": ["/ABSOLUTE/PATH/TO/jira_mcp/server.py"],
      "env": {
        "JIRA_URL":       "https://yourorg.atlassian.net",
        "JIRA_EMAIL":     "you@yourcompany.com",
        "JIRA_API_TOKEN": "your_jira_api_token"
      }
    },
    "github": {
      "command": "python",
      "args": ["/ABSOLUTE/PATH/TO/github_mcp/server.py"],
      "env": {
        "GITHUB_TOKEN": "ghp_your_github_personal_access_token"
      }
    }
  }
}
```

> **Tip:** Use `which python` (macOS/Linux) or `where python` (Windows) to get the correct Python path if you're using a virtual environment.

**Restart Claude Desktop** after saving the config.

---

## 4 — Available Tools

### 🟦 Jira MCP — 10 Tools

| Tool | Description |
|------|-------------|
| `list_projects` | List all accessible Jira projects |
| `search_issues` | Search issues with any JQL query |
| `get_issue` | Full details of a single issue (description, comments, subtasks) |
| `get_epic_issues` | All child issues of an epic |
| `get_sprint_issues` | Issues in the active/future/closed sprint |
| `get_issue_types` | Available issue types for a project |
| `get_transitions` | Workflow transitions available for an issue |
| **`create_bug`** | **Create a structured bug report** with sections for steps to reproduce, expected result, actual result, environment, priority, labels |
| `add_attachment` | Attach a local file (screenshot, log) to an issue |
| `add_comment` | Add a comment to an issue |
| `transition_issue` | Move an issue to a new status |
| `update_issue` | Update summary, priority, assignee, or labels |

### 🟩 GitHub MCP — 12 Tools

| Tool | Description |
|------|-------------|
| `list_repositories` | List repos for a user or org |
| `get_repository` | Detailed info about a repo |
| `list_branches` | List all branches |
| `list_pull_requests` | List PRs (open/closed/all, filterable by base branch) |
| `get_pull_request` | Full PR details with file diffs and review status |
| `create_pull_request` | Create a new PR |
| `review_pull_request` | Submit APPROVE / REQUEST_CHANGES / COMMENT review |
| `merge_pull_request` | Merge a PR (squash/merge/rebase) |
| `list_issues` | List issues with filtering by state, labels, assignee |
| `get_issue` | Full issue details with comments |
| `create_issue` | Create a new issue |
| `add_issue_comment` | Add comment to an issue or PR |
| `list_commits` | Recent commits with author and message |
| `get_file_contents` | Read a file or list a directory from the repo |
| `search_code` | Search for code within a repository |

---

## 5 — Example Prompts

### Jira
```
List all open bugs in project MYAPP assigned to me

Search for epics in MYAPP that are in progress

Get details for MYAPP-423

Create a bug in MYAPP:
  Summary: Login button not responding on iOS 17
  Steps: 1. Open app 2. Tap Login 3. Nothing happens
  Expected: Login screen opens
  Actual: Button freezes, no navigation occurs
  Priority: High

Attach /Users/me/screenshots/bug_screenshot.png to MYAPP-423

Move MYAPP-423 to "In Progress"
```

### GitHub
```
List open PRs in myorg/backend targeting the main branch

Show me PR #42 in myorg/backend

Create a PR from feature/user-auth to main in myorg/backend
  titled "Add JWT authentication"

List all open issues labelled "bug" in myorg/frontend

Show me the last 20 commits on the develop branch of myorg/backend

Read the file src/auth/login.py in myorg/backend

Search for TODO in myorg/backend
```

---

## 6 — Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: mcp` | Run `pip install mcp[cli]` in the correct Python environment |
| `401 Unauthorized` (Jira) | Check JIRA_EMAIL and JIRA_API_TOKEN are correct |
| `403 Forbidden` (GitHub) | Token lacks required scopes — regenerate with `repo` scope |
| Server not appearing in Claude | Use absolute paths in config; restart Claude Desktop |
| `JIRA_URL` errors | Ensure no trailing slash: `https://org.atlassian.net` ✅ |

---

## 7 — Security Notes

- **Never commit credentials** to version control — use environment variables or a `.env` file (already `.gitignore`'d)
- Use the **minimum required scopes** for your tokens
- For production, consider rotating tokens regularly and using short-lived tokens where possible


Major use case:
Utilized GitHub MCP within an Agentic AI framework to analyze source code associated with new user stories, bug fixes, and pull requests. The AI agents review code changes, identify potential coding loopholes, detect defect-prone areas, analyze historical bug patterns, and provide early feedback to development teams without modifying the source code. This enables faster bug detection, improved code quality, and proactive risk identification during the development lifecycle.

Using Jira MCP, the Agentic AI workflow can interact directly with Jira to retrieve user stories, epics, bugs, and other work items. It can also create new bug tickets automatically based on predefined rules, validations, or execution results, enabling end-to-end automated defect management within the AI-driven process flow
