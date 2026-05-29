"""
Jira MCP Server
Provides tools to read/search Jira issues (epics, stories, bugs)
and create detailed bug reports with attachments.
"""

import os
import base64
import json
import mimetypes
from pathlib import Path
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

# ── Config ────────────────────────────────────────────────────────────────────
JIRA_URL   = os.environ["JIRA_URL"].rstrip("/")          # e.g. https://myorg.atlassian.net
JIRA_EMAIL = os.environ["JIRA_EMAIL"]
JIRA_TOKEN = os.environ["JIRA_API_TOKEN"]

REST = f"{JIRA_URL}/rest/api/3"

AUTH    = (JIRA_EMAIL, JIRA_TOKEN)
HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}

mcp = FastMCP("Jira MCP")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get(path: str, params: dict | None = None) -> dict:
    r = httpx.get(f"{REST}{path}", auth=AUTH, headers=HEADERS, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict) -> dict:
    r = httpx.post(f"{REST}{path}", auth=AUTH, headers=HEADERS, json=body, timeout=30)
    r.raise_for_status()
    return r.json()


def _put(path: str, body: dict) -> dict:
    r = httpx.put(f"{REST}{path}", auth=AUTH, headers=HEADERS, json=body, timeout=30)
    r.raise_for_status()
    return r.json() if r.text else {"status": "ok"}


def _adf_doc(text: str) -> dict:
    """Wrap plain text into Atlassian Document Format (ADF)."""
    paragraphs = []
    for line in text.split("\n"):
        paragraphs.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": line or " "}],
        })
    return {"type": "doc", "version": 1, "content": paragraphs}


def _adf_section(heading: str, body: str) -> list[dict]:
    """Return ADF nodes for a labelled section."""
    return [
        {
            "type": "heading",
            "attrs": {"level": 3},
            "content": [{"type": "text", "text": heading}],
        },
        {
            "type": "paragraph",
            "content": [{"type": "text", "text": body or "N/A"}],
        },
    ]


def _fmt_issue(issue: dict) -> str:
    f = issue.get("fields", {})
    assignee = (f.get("assignee") or {}).get("displayName", "Unassigned")
    return (
        f"Key      : {issue['key']}\n"
        f"Type     : {f.get('issuetype', {}).get('name', '')}\n"
        f"Summary  : {f.get('summary', '')}\n"
        f"Status   : {f.get('status', {}).get('name', '')}\n"
        f"Priority : {(f.get('priority') or {}).get('name', 'None')}\n"
        f"Assignee : {assignee}\n"
        f"Reporter : {(f.get('reporter') or {}).get('displayName', '')}\n"
        f"Created  : {f.get('created', '')[:10]}\n"
        f"URL      : {JIRA_URL}/browse/{issue['key']}"
    )


# ── Tools: Read ───────────────────────────────────────────────────────────────

@mcp.tool()
def list_projects() -> str:
    """List all Jira projects accessible to the authenticated user."""
    data = _get("/project/search", {"maxResults": 100})
    projects = data.get("values", [])
    if not projects:
        return "No projects found."
    lines = [f"{p['key']:10} {p['name']}" for p in projects]
    return f"Found {len(projects)} project(s):\n\n" + "\n".join(lines)


@mcp.tool()
def search_issues(
    jql: str,
    max_results: int = 25,
    fields: str = "summary,status,issuetype,priority,assignee,reporter,created,labels,fixVersions",
) -> str:
    """
    Search Jira issues using JQL.

    Examples:
      project = MYPROJ AND issuetype = Bug AND status != Done
      issuetype = Epic AND project = MYPROJ ORDER BY created DESC
      assignee = currentUser() AND sprint in openSprints()
    """
    data = _get("/search", {"jql": jql, "maxResults": max_results, "fields": fields})
    issues = data.get("issues", [])
    total  = data.get("total", 0)
    if not issues:
        return f"No issues matched the JQL: {jql}"

    lines = [f"Showing {len(issues)} of {total} result(s) for: {jql}\n"]
    for i in issues:
        lines.append(_fmt_issue(i))
        lines.append("-" * 50)
    return "\n".join(lines)


@mcp.tool()
def get_issue(issue_key: str) -> str:
    """
    Get full details of a Jira issue including description, comments, and subtasks.
    issue_key: e.g. PROJ-123
    """
    issue = _get(f"/issue/{issue_key}")
    f = issue["fields"]

    # Description (ADF → plain text best-effort)
    desc_nodes = (f.get("description") or {}).get("content", [])
    desc_lines: list[str] = []
    for node in desc_nodes:
        for child in node.get("content", []):
            if child.get("type") == "text":
                desc_lines.append(child.get("text", ""))
    description = "\n".join(desc_lines).strip() or "No description"

    # Comments
    comments = f.get("comment", {}).get("comments", [])
    comment_section = ""
    if comments:
        parts = []
        for c in comments[-5:]:  # last 5
            author = (c.get("author") or {}).get("displayName", "?")
            body_nodes = (c.get("body") or {}).get("content", [])
            body_texts = []
            for n in body_nodes:
                for ch in n.get("content", []):
                    if ch.get("type") == "text":
                        body_texts.append(ch.get("text", ""))
            parts.append(f"  [{author}]: {''.join(body_texts)}")
        comment_section = "\nComments (last 5):\n" + "\n".join(parts)

    # Subtasks
    subtasks = f.get("subtasks", [])
    subtask_section = ""
    if subtasks:
        sub_lines = [f"  {s['key']} – {s['fields']['summary']}" for s in subtasks]
        subtask_section = "\nSubtasks:\n" + "\n".join(sub_lines)

    # Labels & Fix Versions
    labels   = ", ".join(f.get("labels", [])) or "None"
    versions = ", ".join(v["name"] for v in f.get("fixVersions", [])) or "None"

    return (
        f"{_fmt_issue(issue)}\n"
        f"Labels   : {labels}\n"
        f"Fix Ver  : {versions}\n\n"
        f"Description:\n{description}"
        f"{comment_section}"
        f"{subtask_section}"
    )


@mcp.tool()
def get_epic_issues(epic_key: str, max_results: int = 50) -> str:
    """
    List all child issues (stories, tasks, bugs) belonging to a given epic.
    epic_key: e.g. PROJ-10
    """
    jql = f'"Epic Link" = {epic_key} OR "Parent" = {epic_key}'
    return search_issues(jql, max_results=max_results)


@mcp.tool()
def get_sprint_issues(project_key: str, sprint_state: str = "active") -> str:
    """
    Get issues in the current sprint for a project.
    sprint_state: active | future | closed
    """
    jql = f"project = {project_key} AND sprint in {sprint_state}Sprints() ORDER BY updated DESC"
    return search_issues(jql, max_results=50)


@mcp.tool()
def get_issue_types(project_key: str) -> str:
    """List available issue types for a project (Bug, Story, Epic, Task, etc.)."""
    data = _get(f"/project/{project_key}")
    issue_types = data.get("issueTypes", [])
    lines = [f"  {it['name']:15} – {it.get('description','')}" for it in issue_types]
    return f"Issue types for {project_key}:\n" + "\n".join(lines)


@mcp.tool()
def get_transitions(issue_key: str) -> str:
    """
    List available workflow transitions for an issue (e.g. To Do → In Progress → Done).
    Use the returned IDs with transition_issue().
    """
    data = _get(f"/issue/{issue_key}/transitions")
    transitions = data.get("transitions", [])
    lines = [f"  ID {t['id']:5} → {t['name']}" for t in transitions]
    return f"Transitions for {issue_key}:\n" + "\n".join(lines)


# ── Tools: Write ──────────────────────────────────────────────────────────────

@mcp.tool()
def create_bug(
    project_key: str,
    summary: str,
    steps_to_reproduce: str,
    expected_result: str,
    actual_result: str,
    environment: str = "",
    priority: str = "Medium",
    labels: str = "",
    fix_version: str = "",
    assignee_account_id: str = "",
) -> str:
    """
    Create a detailed Bug report in Jira with structured sections.

    Args:
        project_key:          Jira project key (e.g. MYPROJ)
        summary:              One-line bug title
        steps_to_reproduce:   Numbered steps to reproduce the bug
        expected_result:      What should have happened
        actual_result:        What actually happened
        environment:          OS / browser / version info (optional)
        priority:             Highest | High | Medium | Low | Lowest
        labels:               Comma-separated labels (optional)
        fix_version:          Target fix version name (optional)
        assignee_account_id:  Jira account ID to assign to (optional)
    """
    # Build ADF description with clear sections
    content_nodes: list[dict] = []
    content_nodes += _adf_section("🔁 Steps to Reproduce", steps_to_reproduce)
    content_nodes += _adf_section("✅ Expected Result",    expected_result)
    content_nodes += _adf_section("❌ Actual Result",      actual_result)
    if environment:
        content_nodes += _adf_section("🖥️ Environment",   environment)

    description = {"type": "doc", "version": 1, "content": content_nodes}

    fields: dict = {
        "project":     {"key": project_key},
        "issuetype":   {"name": "Bug"},
        "summary":     summary,
        "description": description,
        "priority":    {"name": priority},
    }

    if labels:
        fields["labels"] = [l.strip() for l in labels.split(",") if l.strip()]

    if fix_version:
        fields["fixVersions"] = [{"name": fix_version}]

    if assignee_account_id:
        fields["assignee"] = {"accountId": assignee_account_id}

    result = _post("/issue", {"fields": fields})
    key = result.get("key", "?")
    return (
        f"✅ Bug created: {key}\n"
        f"URL : {JIRA_URL}/browse/{key}\n\n"
        f"Summary  : {summary}\n"
        f"Priority : {priority}\n"
        f"Project  : {project_key}\n\n"
        f"Tip: use add_attachment('{key}', '/path/to/screenshot.png') to attach files."
    )


@mcp.tool()
def add_attachment(issue_key: str, file_path: str) -> str:
    """
    Attach a local file (screenshot, log, etc.) to an existing Jira issue.

    Args:
        issue_key: e.g. PROJ-123
        file_path: Absolute path to the file on disk
    """
    path = Path(file_path)
    if not path.exists():
        return f"❌ File not found: {file_path}"

    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    url  = f"{REST}/issue/{issue_key}/attachments"

    with path.open("rb") as fh:
        r = httpx.post(
            url,
            auth=AUTH,
            headers={
                "X-Atlassian-Token": "no-check",
                "Accept": "application/json",
            },
            files={"file": (path.name, fh, mime)},
            timeout=60,
        )
    r.raise_for_status()
    attachments = r.json()
    names = [a.get("filename", "?") for a in attachments]
    return f"✅ Attached to {issue_key}: {', '.join(names)}"


@mcp.tool()
def add_comment(issue_key: str, comment: str) -> str:
    """Add a comment to an existing Jira issue."""
    body = {"body": _adf_doc(comment)}
    result = _post(f"/issue/{issue_key}/comment", body)
    return f"✅ Comment added to {issue_key} (id: {result.get('id')})"


@mcp.tool()
def transition_issue(issue_key: str, transition_id: str) -> str:
    """
    Move an issue to a new workflow status.
    Get valid transition IDs via get_transitions(issue_key).
    """
    _post(f"/issue/{issue_key}/transitions", {"transition": {"id": transition_id}})
    return f"✅ {issue_key} transitioned (id: {transition_id})"


@mcp.tool()
def update_issue(
    issue_key: str,
    summary: str = "",
    priority: str = "",
    assignee_account_id: str = "",
    labels: str = "",
) -> str:
    """
    Update fields on an existing issue.
    Only non-empty arguments are changed.
    """
    fields: dict = {}
    if summary:
        fields["summary"] = summary
    if priority:
        fields["priority"] = {"name": priority}
    if assignee_account_id:
        fields["assignee"] = {"accountId": assignee_account_id}
    if labels:
        fields["labels"] = [l.strip() for l in labels.split(",") if l.strip()]

    if not fields:
        return "⚠️ Nothing to update — all arguments were empty."

    _put(f"/issue/{issue_key}", {"fields": fields})
    return f"✅ {issue_key} updated: {list(fields.keys())}"


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
