"""
GitHub MCP Server
Provides tools to read/manage GitHub repositories, pull requests,
issues, commits, branches, and code reviews.
"""

import os
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

# ── Config ────────────────────────────────────────────────────────────────────
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]

BASE    = "https://api.github.com"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

mcp = FastMCP("GitHub MCP")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get(path: str, params: dict | None = None) -> dict | list:
    r = httpx.get(f"{BASE}{path}", headers=HEADERS, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict) -> dict:
    r = httpx.post(f"{BASE}{path}", headers=HEADERS, json=body, timeout=30)
    r.raise_for_status()
    return r.json()


def _patch(path: str, body: dict) -> dict:
    r = httpx.patch(f"{BASE}{path}", headers=HEADERS, json=body, timeout=30)
    r.raise_for_status()
    return r.json()


def _put(path: str, body: dict) -> dict:
    r = httpx.put(f"{BASE}{path}", headers=HEADERS, json=body, timeout=30)
    r.raise_for_status()
    return r.json()


def _fmt_pr(pr: dict) -> str:
    return (
        f"PR #{pr['number']:5}  [{pr['state'].upper():6}]  {pr['title']}\n"
        f"           Author : {pr['user']['login']} | "
        f"Base ← Head : {pr['base']['ref']} ← {pr['head']['ref']}\n"
        f"           Created: {pr['created_at'][:10]} | "
        f"Updated: {pr['updated_at'][:10]}\n"
        f"           URL    : {pr['html_url']}"
    )


def _fmt_issue(issue: dict) -> str:
    labels = ", ".join(l["name"] for l in issue.get("labels", [])) or "none"
    return (
        f"#{issue['number']:5}  [{issue['state'].upper():6}]  {issue['title']}\n"
        f"        Author : {issue['user']['login']} | Labels: {labels}\n"
        f"        Created: {issue['created_at'][:10]}\n"
        f"        URL    : {issue['html_url']}"
    )


# ── Tools: Repositories ───────────────────────────────────────────────────────

@mcp.tool()
def list_repositories(owner: str, repo_type: str = "all", max_results: int = 30) -> str:
    """
    List repositories for a user or organisation.

    Args:
        owner:       GitHub username or org name
        repo_type:   all | public | private | forks | sources | member
        max_results: max repos to return (default 30)
    """
    # Try org endpoint first, fall back to user
    try:
        data = _get(f"/orgs/{owner}/repos", {"type": repo_type, "per_page": max_results, "sort": "updated"})
    except httpx.HTTPStatusError:
        data = _get(f"/users/{owner}/repos", {"type": repo_type, "per_page": max_results, "sort": "updated"})

    if not data:
        return f"No repositories found for {owner}."

    lines = []
    for r in data:
        lang    = r.get("language") or "—"
        stars   = r.get("stargazers_count", 0)
        updated = r.get("updated_at", "")[:10]
        lines.append(f"  {r['name']:40} ⭐{stars:5}  {lang:15}  updated {updated}")
    return f"Repositories for {owner} ({len(data)}):\n\n" + "\n".join(lines)


@mcp.tool()
def get_repository(owner: str, repo: str) -> str:
    """Get detailed information about a specific repository."""
    r = _get(f"/repos/{owner}/{repo}")
    return (
        f"Repo    : {r['full_name']}\n"
        f"Desc    : {r.get('description') or 'No description'}\n"
        f"Language: {r.get('language') or '—'}\n"
        f"Stars   : {r.get('stargazers_count', 0)}  |  Forks: {r.get('forks_count', 0)}\n"
        f"Default : {r['default_branch']}\n"
        f"Private : {r['private']}\n"
        f"License : {(r.get('license') or {}).get('name', 'None')}\n"
        f"Topics  : {', '.join(r.get('topics', [])) or 'none'}\n"
        f"URL     : {r['html_url']}"
    )


@mcp.tool()
def list_branches(owner: str, repo: str) -> str:
    """List all branches of a repository."""
    data = _get(f"/repos/{owner}/{repo}/branches", {"per_page": 100})
    if not data:
        return "No branches found."
    lines = [f"  {'* ' if b.get('protected') else '  '}{b['name']}" for b in data]
    return f"Branches for {owner}/{repo} ({len(data)}):\n" + "\n".join(lines)


# ── Tools: Pull Requests ──────────────────────────────────────────────────────

@mcp.tool()
def list_pull_requests(
    owner: str,
    repo: str,
    state: str = "open",
    base_branch: str = "",
    max_results: int = 20,
) -> str:
    """
    List pull requests for a repository.

    Args:
        owner:       Repo owner / org
        repo:        Repository name
        state:       open | closed | all
        base_branch: Filter by target branch (optional)
        max_results: Max PRs to return
    """
    params: dict = {"state": state, "per_page": max_results, "sort": "updated", "direction": "desc"}
    if base_branch:
        params["base"] = base_branch
    data = _get(f"/repos/{owner}/{repo}/pulls", params)
    if not data:
        return f"No {state} pull requests found."
    lines = [_fmt_pr(pr) for pr in data]
    return f"Pull Requests — {owner}/{repo} [{state}] ({len(data)}):\n\n" + "\n\n".join(lines)


@mcp.tool()
def get_pull_request(owner: str, repo: str, pr_number: int) -> str:
    """
    Get full details of a pull request including diff stats and review status.
    """
    pr    = _get(f"/repos/{owner}/{repo}/pulls/{pr_number}")
    files = _get(f"/repos/{owner}/{repo}/pulls/{pr_number}/files")
    reviews = _get(f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews")

    # Changed files
    file_lines = []
    for f in files[:20]:  # cap at 20
        status = f.get("status", "")
        added  = f.get("additions", 0)
        removed = f.get("deletions", 0)
        file_lines.append(f"  [{status:8}]  +{added:4} -{removed:4}  {f['filename']}")

    # Reviews
    review_lines = []
    for rv in reviews:
        review_lines.append(f"  {rv['user']['login']:20} → {rv['state']}")

    body = pr.get("body") or "No description"
    if len(body) > 500:
        body = body[:497] + "..."

    return (
        f"{_fmt_pr(pr)}\n\n"
        f"Mergeable : {pr.get('mergeable')}\n"
        f"Commits   : {pr.get('commits')}  |  "
        f"+{pr.get('additions')} / -{pr.get('deletions')} in {pr.get('changed_files')} files\n\n"
        f"Description:\n{body}\n\n"
        f"Changed Files ({min(len(files), 20)}):\n" + "\n".join(file_lines) +
        (f"\n\nReviews:\n" + "\n".join(review_lines) if review_lines else "")
    )


@mcp.tool()
def create_pull_request(
    owner: str,
    repo: str,
    title: str,
    head_branch: str,
    base_branch: str,
    body: str = "",
    draft: bool = False,
) -> str:
    """
    Create a new pull request.

    Args:
        owner:       Repo owner / org
        repo:        Repository name
        title:       PR title
        head_branch: Branch with your changes (source)
        base_branch: Branch to merge into (target, e.g. main)
        body:        PR description / summary (optional)
        draft:       Create as draft PR (default False)
    """
    payload = {
        "title": title,
        "head": head_branch,
        "base": base_branch,
        "body": body,
        "draft": draft,
    }
    pr = _post(f"/repos/{owner}/{repo}/pulls", payload)
    return (
        f"✅ Pull Request created!\n\n"
        f"{_fmt_pr(pr)}\n\n"
        f"Draft  : {draft}\n"
        f"Status : {pr['state']}"
    )


@mcp.tool()
def review_pull_request(
    owner: str,
    repo: str,
    pr_number: int,
    body: str,
    event: str = "COMMENT",
) -> str:
    """
    Submit a review on a pull request.

    Args:
        owner:     Repo owner
        repo:      Repo name
        pr_number: PR number
        body:      Review comment text
        event:     APPROVE | REQUEST_CHANGES | COMMENT
    """
    payload = {"body": body, "event": event}
    result = _post(f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews", payload)
    return f"✅ Review submitted on PR #{pr_number}: {result.get('state')}"


@mcp.tool()
def merge_pull_request(
    owner: str,
    repo: str,
    pr_number: int,
    merge_method: str = "squash",
    commit_title: str = "",
    commit_message: str = "",
) -> str:
    """
    Merge a pull request.

    Args:
        merge_method: merge | squash | rebase
    """
    payload: dict = {"merge_method": merge_method}
    if commit_title:
        payload["commit_title"] = commit_title
    if commit_message:
        payload["commit_message"] = commit_message

    result = _put(f"/repos/{owner}/{repo}/pulls/{pr_number}/merge", payload)
    return f"✅ PR #{pr_number} merged: {result.get('message')}\nSHA: {result.get('sha')}"


# ── Tools: Issues ─────────────────────────────────────────────────────────────

@mcp.tool()
def list_issues(
    owner: str,
    repo: str,
    state: str = "open",
    labels: str = "",
    assignee: str = "",
    max_results: int = 20,
) -> str:
    """
    List GitHub issues (excludes pull requests).

    Args:
        state:     open | closed | all
        labels:    Comma-separated label names to filter by (optional)
        assignee:  GitHub username to filter by (optional)
    """
    params: dict = {"state": state, "per_page": max_results, "sort": "updated"}
    if labels:
        params["labels"] = labels
    if assignee:
        params["assignee"] = assignee

    data = _get(f"/repos/{owner}/{repo}/issues", params)
    # Filter out PRs
    issues = [i for i in data if not i.get("pull_request")]
    if not issues:
        return f"No {state} issues found."

    lines = [_fmt_issue(i) for i in issues]
    return f"Issues — {owner}/{repo} [{state}] ({len(issues)}):\n\n" + "\n\n".join(lines)


@mcp.tool()
def get_issue(owner: str, repo: str, issue_number: int) -> str:
    """Get full details of a GitHub issue including body and comments."""
    issue    = _get(f"/repos/{owner}/{repo}/issues/{issue_number}")
    comments = _get(f"/repos/{owner}/{repo}/issues/{issue_number}/comments")

    body = issue.get("body") or "No description"
    if len(body) > 800:
        body = body[:797] + "..."

    comment_section = ""
    if comments:
        parts = []
        for c in comments[-5:]:
            cb = (c.get("body") or "")[:300]
            parts.append(f"  [{c['user']['login']}]: {cb}")
        comment_section = "\nComments (last 5):\n" + "\n".join(parts)

    return (
        f"{_fmt_issue(issue)}\n\n"
        f"Body:\n{body}"
        f"{comment_section}"
    )


@mcp.tool()
def create_issue(
    owner: str,
    repo: str,
    title: str,
    body: str = "",
    labels: str = "",
    assignees: str = "",
    milestone: int = 0,
) -> str:
    """
    Create a new GitHub issue.

    Args:
        labels:    Comma-separated label names (optional)
        assignees: Comma-separated GitHub usernames (optional)
        milestone: Milestone number (optional)
    """
    payload: dict = {"title": title, "body": body}
    if labels:
        payload["labels"] = [l.strip() for l in labels.split(",") if l.strip()]
    if assignees:
        payload["assignees"] = [a.strip() for a in assignees.split(",") if a.strip()]
    if milestone:
        payload["milestone"] = milestone

    issue = _post(f"/repos/{owner}/{repo}/issues", payload)
    return f"✅ Issue created!\n\n{_fmt_issue(issue)}"


@mcp.tool()
def add_issue_comment(owner: str, repo: str, issue_number: int, comment: str) -> str:
    """Add a comment to a GitHub issue or pull request."""
    result = _post(f"/repos/{owner}/{repo}/issues/{issue_number}/comments", {"body": comment})
    return f"✅ Comment added to #{issue_number}: {result.get('html_url')}"


# ── Tools: Code & Commits ─────────────────────────────────────────────────────

@mcp.tool()
def list_commits(
    owner: str,
    repo: str,
    branch: str = "",
    author: str = "",
    max_results: int = 20,
) -> str:
    """
    List recent commits for a repository.

    Args:
        branch:  Branch name (defaults to repo default branch)
        author:  Filter by GitHub username or email
    """
    params: dict = {"per_page": max_results}
    if branch:
        params["sha"] = branch
    if author:
        params["author"] = author

    data = _get(f"/repos/{owner}/{repo}/commits", params)
    if not data:
        return "No commits found."

    lines = []
    for c in data:
        sha     = c["sha"][:8]
        msg     = c["commit"]["message"].split("\n")[0][:70]
        author_ = (c.get("author") or {}).get("login") or c["commit"]["author"]["name"]
        date    = c["commit"]["author"]["date"][:10]
        lines.append(f"  {sha}  {date}  [{author_:20}]  {msg}")

    return f"Commits — {owner}/{repo} ({len(data)}):\n\n" + "\n".join(lines)


@mcp.tool()
def get_file_contents(
    owner: str,
    repo: str,
    file_path: str,
    branch: str = "",
) -> str:
    """
    Read the contents of a file from a repository.

    Args:
        file_path: Path to file in repo, e.g. src/main.py
        branch:    Branch or tag (optional, defaults to default branch)
    """
    import base64
    params = {}
    if branch:
        params["ref"] = branch

    data = _get(f"/repos/{owner}/{repo}/contents/{file_path}", params)
    if isinstance(data, list):
        # It's a directory
        entries = [f"  {'[DIR] ' if e['type']=='dir' else '      '}{e['name']}" for e in data]
        return f"Directory listing for {file_path}:\n" + "\n".join(entries)

    content_b64 = data.get("content", "")
    try:
        content = base64.b64decode(content_b64).decode("utf-8", errors="replace")
    except Exception:
        return "⚠️ File appears to be binary and cannot be displayed as text."

    # Cap at 4 000 chars
    if len(content) > 4000:
        content = content[:4000] + f"\n\n... [truncated — full file is {data.get('size', '?')} bytes]"

    return (
        f"File : {data['path']}\n"
        f"SHA  : {data['sha'][:8]}\n"
        f"Size : {data.get('size', '?')} bytes\n\n"
        f"{content}"
    )


@mcp.tool()
def search_code(owner: str, repo: str, query: str, max_results: int = 10) -> str:
    """
    Search for code within a repository.

    Args:
        query: Search term, e.g. 'def authenticate' or 'TODO'
    """
    q = f"{query} repo:{owner}/{repo}"
    data = _get("/search/code", {"q": q, "per_page": max_results})
    items = data.get("items", [])
    if not items:
        return f"No code matches for '{query}' in {owner}/{repo}"

    lines = []
    for item in items:
        lines.append(f"  {item['path']}\n    {item.get('html_url')}")
    return f"Code search results for '{query}' ({len(items)}):\n\n" + "\n\n".join(lines)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
