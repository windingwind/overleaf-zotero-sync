#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Copyright (c) 2025, GitHub User @windingwind

This script provides a command-line interface to sync Zotero libraries with Overleaf projects.
The code should be distributed under the GNU Affero General Public License (AGPL) v3.0.
"""
import os
import sys
import json
import tempfile
import shutil
import time
import requests
import webbrowser
import threading
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from git import Repo
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from requests_oauthlib import OAuth1Session

# Rich imports for enhanced UI
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
)
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
import inquirer
from inquirer.themes import GreenPassion
import logging

# Initialize Rich console
console = Console()

# Setup enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)],
)
logger = logging.getLogger("zotero_sync")

# OAuth credentials for Zotero
ZOTERO_CLIENT_KEY = "a794e237f0ed3ee439b3"
ZOTERO_CLIENT_SECRET = "454dee43d7e3b8240f62"
REQUEST_TOKEN_URL = "https://www.zotero.org/oauth/request"
AUTHORIZE_URL = "https://www.zotero.org/oauth/authorize"
ACCESS_TOKEN_URL = "https://www.zotero.org/oauth/access"

# Maximum items per request (Zotero API default is 25, max 100)
ZOTERO_PAGE_LIMIT = 100

CONFIG_PATH = Path.home() / ".config" / "zotero_overleaf" / "config.json"


def load_configs(config_path: Path) -> dict:
    """Load configuration from JSON file with enhanced error handling."""
    if config_path.exists():
        console.print("[bold blue]Loading configuration...")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                logger.info(f"✅ Configuration loaded from {config_path}")
                return config
        except json.JSONDecodeError as e:
            logger.error(f"❌ Error reading config file {config_path}: {e}")
            logger.warning("Using default configuration")
    else:
        logger.info("📋 No existing configuration found, starting fresh")
    return {"zotero_credentials": [], "overleaf_tokens": [], "overleaf_projects": []}


def save_configs(config_path: Path, configs: dict) -> None:
    """Save configuration to JSON file."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(configs, f, indent=2)
    logger.info(f"💾 Configuration saved to {config_path}")


def _parse_iso(dt_str: str):
    """Parse ISO datetime string."""
    try:
        return datetime.fromisoformat(dt_str)
    except:
        return None


def _desktop_available() -> bool:
    """Check if desktop environment is available for OAuth."""
    if sys.platform.startswith("linux"):
        return "DISPLAY" in os.environ
    if sys.platform == "darwin":
        return True
    if sys.platform.startswith("win"):
        return True
    return False


def get_zotero_oauth_token(callback_port=8080) -> dict:
    """Get Zotero OAuth token with enhanced UI feedback."""
    console.print("[bold blue]Setting up OAuth session...")
    oauth = OAuth1Session(
        ZOTERO_CLIENT_KEY,
        client_secret=ZOTERO_CLIENT_SECRET,
        callback_uri=f"http://localhost:{callback_port}/callback",
    )
    fetch_response = oauth.fetch_request_token(REQUEST_TOKEN_URL)
    resource_owner_key = fetch_response.get("oauth_token")
    resource_owner_secret = fetch_response.get("oauth_token_secret")
    auth_url = oauth.authorization_url(AUTHORIZE_URL)

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            qs = parse_qs(self.path.split("?", 1)[1])
            self.server.verifier = qs.get("oauth_verifier")[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Authorization complete. You can close this window.")
            logger.info("🔐 OAuth authorization received")

        def log_message(self, format, *args):
            pass  # Suppress HTTP server logs

    server = HTTPServer(("localhost", callback_port), CallbackHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    console.print(f"🌐 Opening browser for Zotero authorization...")
    console.print(f"📍 Callback URL: http://localhost:{callback_port}/callback")
    webbrowser.open(auth_url)

    console.print("[bold yellow]Waiting for authorization...")
    while not hasattr(server, "verifier"):
        time.sleep(0.1)

    server.shutdown()
    verifier = server.verifier

    console.print("[bold blue]Fetching access token...")
    oauth = OAuth1Session(
        ZOTERO_CLIENT_KEY,
        client_secret=ZOTERO_CLIENT_SECRET,
        resource_owner_key=resource_owner_key,
        resource_owner_secret=resource_owner_secret,
        verifier=verifier,
    )
    tokens = oauth.fetch_access_token(ACCESS_TOKEN_URL)

    logger.info("✅ OAuth token obtained successfully")
    return {
        "user_id": tokens.get("userID") or tokens.get("user_id"),
        "api_key": tokens["oauth_token"],
        "api_secret": tokens["oauth_token_secret"],
        "user_name": tokens.get("username", ""),
    }


def _add_zotero_api_cred(configs: dict) -> dict:
    """Add Zotero API credentials manually."""
    console.print("\n[bold cyan]Adding Zotero API Credentials[/bold cyan]")
    user_id = Prompt.ask("Enter Zotero user/group ID")
    api_key = Prompt.ask("Enter Zotero API key", password=True)

    cred = {
        "user_id": user_id,
        "api_key": api_key,
        "api_secret": "",
        "user_name": "",
        "created": datetime.now().isoformat(),
        "last_used": datetime.now().isoformat(),
    }
    configs.setdefault("zotero_credentials", []).append(cred)
    logger.info("✅ Zotero credentials added successfully")
    return cred


def choose_zotero_cred(configs: dict) -> dict:
    """Choose Zotero credentials with enhanced UI."""
    creds = configs.get("zotero_credentials", [])

    if not creds:
        console.print("\n[yellow]No Zotero credentials found.[/yellow]")

        choices = ["Add via API key"]
        if _desktop_available():
            choices.insert(0, "Add via OAuth (desktop flow)")

        questions = [
            inquirer.List(
                "method",
                message="How would you like to add Zotero credentials?",
                choices=choices,
                default=choices[0],
            )
        ]

        answers = inquirer.prompt(questions, theme=GreenPassion())

        if answers["method"].startswith("Add via OAuth"):
            return _add_oauth_cred(configs)
        else:
            return _add_zotero_api_cred(configs)

    # Display existing credentials in a table
    table = Table(title="Zotero Credentials", box=box.ROUNDED)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("User Info", style="magenta")
    table.add_column("Created", style="green")
    table.add_column("Last Used", style="yellow")
    table.add_column("Status", style="bold")

    sorted_creds = sorted(
        creds,
        key=lambda c: _parse_iso(c.get("last_used") or c["created"]),
        reverse=True,
    )

    choices = []
    for i, c in enumerate(sorted_creds):
        created = c.get("created", "Unknown")[:10]  # Just date part
        last_used = c.get("last_used", "Never")[:10] if c.get("last_used") else "Never"
        user_name = c.get("user_name", "")
        if not user_name:
            user_id = c.get("user_id", "")
            if user_id:
                user_name = user_id
            else:
                api_key = c.get("api_key", "")
                if api_key:
                    user_name = f"API Key ({api_key[:8]}...)"
        if not user_name:
            user_name = "Unknown User"
        
        user_info = f"{user_name} ({c['user_id']})" if user_name else c["user_id"]
        status = "🌟 Default" if i == 0 else ""

        table.add_row(str(i + 1), user_info, created, last_used, status)
        choices.append(f"{i + 1}. {user_info} (Last: {last_used})")

    console.print(table)

    # Add options for new credentials
    choices.append("➕ Add new via API key")
    if _desktop_available():
        choices.append("🔐 Add new via OAuth (desktop)")

    questions = [
        inquirer.List(
            "credential",
            message="Select Zotero credential:",
            choices=choices,
            default=choices[0],
        )
    ]

    answers = inquirer.prompt(questions, theme=GreenPassion())
    selected = answers["credential"]

    if selected.startswith("➕"):
        return _add_zotero_api_cred(configs)
    elif selected.startswith("🔐"):
        return _add_oauth_cred(configs)
    else:
        # Extract index from selection
        idx = int(selected.split(".")[0]) - 1
        cred = sorted_creds[idx]
        cred["last_used"] = datetime.now().isoformat()
        logger.info(
            f"✅ Selected credential for user: {cred.get('user_name', cred['user_id'])}"
        )
        return cred


def _add_oauth_cred(configs: dict) -> dict:
    """Add OAuth credentials."""
    tokens = get_zotero_oauth_token()
    cred = {
        "user_id": tokens["user_id"],
        "api_key": tokens["api_key"],
        "api_secret": tokens["api_secret"],
        "user_name": tokens.get("user_name", ""),
        "created": datetime.now().isoformat(),
        "last_used": datetime.now().isoformat(),
    }
    configs.setdefault("zotero_credentials", []).append(cred)
    return cred


def parse_zotero_url(url: str):
    """Parse Zotero URL to extract user/group and collection info."""
    path = urlparse(url).path.strip("/")
    parts = path.split("/")
    if parts[0] == "groups":
        is_group = True
        user_id = parts[1]
        if len(parts) >= 5 and parts[3] == "collections":
            collection = parts[4]
        else:
            collection = None
    else:
        is_group = False
        user_id = parts[0]
        if len(parts) >= 3 and parts[1] == "collections":
            collection = parts[2]
        else:
            collection = None
    return is_group, user_id, collection


def _add_overleaf_token(configs: dict) -> dict:
    """Add Overleaf auth token manually."""
    console.print("\n[bold cyan]Adding Overleaf Auth Token[/bold cyan]")
    token = Prompt.ask("Enter Overleaf auth token", password=True)
    entry = {
        "token": token,
        "created": datetime.now().isoformat(),
        "last_used": datetime.now().isoformat(),
    }
    configs.setdefault("overleaf_tokens", []).append(entry)
    logger.info("✅ Overleaf auth token added successfully")
    return entry


def choose_overleaf_token(configs: dict) -> dict:
    """Choose Overleaf auth token with enhanced UI."""
    tokens = configs.get("overleaf_tokens", [])
    if not tokens:
        console.print("\n[yellow]No Overleaf tokens found.[/yellow]")
        questions = [
            inquirer.List(
                "method",
                message="How would you like to add Overleaf token?",
                choices=["Add new token"],
                default="Add new token",
            )
        ]
        inquirer.prompt(questions, theme=GreenPassion())
        return _add_overleaf_token(configs)

    # Display existing tokens
    table = Table(title="Overleaf Tokens", box=box.ROUNDED)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Token", style="magenta", no_wrap=True)
    table.add_column("Created", style="green")
    table.add_column("Last Used", style="yellow")
    table.add_column("Status", style="bold")

    sorted_toks = sorted(
        tokens,
        key=lambda t: datetime.fromisoformat(t.get("last_used")),
        reverse=True,
    )
    choices = []
    for i, t in enumerate(sorted_toks):
        token_display = t["token"][:8] + "..." if len(t["token"]) > 8 else t["token"]
        created = t.get("created", "Unknown")[:10]
        last_used = t.get("last_used", "Never")[:10]
        status = "🌟 Default" if i == 0 else ""
        table.add_row(str(i + 1), token_display, created, last_used, status)
        choices.append(f"{i+1}. Token added {created}")

    console.print(table)
    choices.append("➕ Add new token")

    questions = [
        inquirer.List(
            "selection",
            message="Select Overleaf auth token:",
            choices=choices,
            default=choices[0],
        )
    ]
    answer = inquirer.prompt(questions, theme=GreenPassion())["selection"]
    if answer.startswith("➕"):
        return _add_overleaf_token(configs)
    idx = int(answer.split(".")[0]) - 1
    tok = sorted_toks[idx]
    tok["last_used"] = datetime.now().isoformat()
    logger.info("✅ Selected Overleaf token")
    return tok


def choose_overleaf_proj(configs: dict, token_entry: dict) -> dict:
    """Choose Overleaf project with enhanced UI."""
    projs = configs.get("overleaf_projects", [])

    if projs:
        # Display existing projects in a table
        table = Table(title="Overleaf Projects", box=box.ROUNDED)
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Project Name", style="magenta")
        table.add_column("Created", style="green")
        table.add_column("Last Run", style="yellow")
        table.add_column("Status", style="bold")

        sorted_projs = sorted(
            projs,
            key=lambda p: _parse_iso(p.get("last_run") or p["created"]),
            reverse=True,
        )

        choices = []
        for i, p in enumerate(sorted_projs):
            created = p.get("created", "Unknown")[:10]
            last_run = p.get("last_run", "Never")[:10] if p.get("last_run") else "Never"
            status = "🌟 Default" if i == 0 else ""

            table.add_row(str(i + 1), p["name"], created, last_run, status)
            choices.append(f"{i + 1}. {p['name']} (Last: {last_run})")

        console.print(table)
        choices.append("➕ Add new Overleaf project")

        questions = [
            inquirer.List(
                "project",
                message="Select Overleaf project:",
                choices=choices,
                default=choices[0],
            )
        ]

        answers = inquirer.prompt(questions, theme=GreenPassion())

        if not answers["project"].startswith("➕"):
            idx = int(answers["project"].split(".")[0]) - 1
            selected_proj = sorted_projs[idx]
            logger.info(f"✅ Selected project: {selected_proj['name']}")
            return selected_proj

    # Add new project
    console.print("\n[bold cyan]Adding New Overleaf Project[/bold cyan]")
    name = Prompt.ask("📝 Project name")
    git_url = Prompt.ask("🔗 Overleaf Git URL")
    # Remove token prompt

    use_temp = Confirm.ask(
        "💾 Use temporary directory? (No = specify custom path)", default=True
    )
    local_dir = None if use_temp else Prompt.ask("📁 Local directory path")

    has_zotero_url = Confirm.ask(
        "🔗 Do you have a specific Zotero collection URL?", default=False
    )
    zot_url = None
    if has_zotero_url:
        zot_url = Prompt.ask("🔗 Zotero library/collection URL")

    if zot_url:
        is_group, zot_user_id, collection = parse_zotero_url(zot_url)
    else:
        is_group, zot_user_id, collection = False, "", None

    proj = {
        "name": name,
        "git_url": git_url,
        "auth_token": token_entry["token"],
        "local_dir": local_dir,
        "zotero_is_group": is_group,
        "zotero_user_id": zot_user_id,
        "zotero_collection_id": collection,
        "created": datetime.now().isoformat(),
        "last_run": None,
    }
    configs.setdefault("overleaf_projects", []).append(proj)
    logger.info(f"✅ Project '{name}' added successfully")
    return proj


def clone_or_update_repo(git_url: str, token: str, local_dir: str = None) -> tuple:
    """Clone or update Git repository with progress indication."""
    if local_dir:
        path = Path(local_dir).expanduser()
        is_temp = False
    else:
        tmp = tempfile.mkdtemp(prefix="overleaf-zotero-sync_build_")
        path = Path(tmp)
        is_temp = True

    parsed = urlparse(git_url)
    domain = parsed.netloc.split("@")[-1]
    domain_and_path = domain + parsed.path
    auth_url = f"{parsed.scheme}://git:{token}@{domain_and_path}"

    if (path / ".git").exists():
        console.print(f"[bold blue]Pulling latest changes in {path}...")
        repo = Repo(path)
        repo.remotes.origin.pull()
        logger.info(f"📥 Repository updated: {path}")
    else:
        console.print(f"[bold blue]Cloning repository to {path}...")
        repo = Repo.clone_from(auth_url, path)
        logger.info(f"📦 Repository cloned: {path}")

    return repo, str(path), is_temp


def _get_all_subcollections(cred: dict, proj: dict, parent_id: str) -> list[str]:
    """
    Recursively retrieve all subcollection IDs under `parent_id`.
    """
    base = "groups" if proj.get("zotero_is_group") else "users"
    user_id = proj.get("zotero_user_id") or cred["user_id"]
    url = f"https://api.zotero.org/{base}/{user_id}/collections/{parent_id}/collections"
    params = {"key": cred["api_key"], "limit": ZOTERO_PAGE_LIMIT}
    sub_ids = []
    next_url = url

    while next_url:
        resp = requests.get(next_url, params=params)
        resp.raise_for_status()
        data = resp.json()
        # collect this page’s collection keys
        for c in data:
            sub_ids.append(c["key"])
        # follow rel=next if present
        link = resp.headers.get("Link", "")
        next_url = None
        for link_part in requests.utils.parse_header_links(link.rstrip(">")):
            if link_part.get("rel") == "next":
                next_url = link_part["url"]
                break

    # recurse into each found subcollection
    all_desc = []
    for cid in sub_ids:
        all_desc.append(cid)
        all_desc.extend(_get_all_subcollections(cred, proj, cid))
    return all_desc


def fetch_zotero_bib(cred: dict, proj: dict) -> str:
    """Fetch BibTeX entries from Zotero, recursing into subcollections."""
    base = "groups" if proj.get("zotero_is_group") else "users"
    user_id = proj.get("zotero_user_id") or cred["user_id"]

    # determine which collections to fetch
    if proj.get("zotero_collection_id"):
        parent = proj["zotero_collection_id"]
        coll_ids = [parent] + _get_all_subcollections(cred, proj, parent)
    else:
        # no collection => fetch all items in library
        coll_ids = [None]

    bib_parts = []
    total_entries = 0
    page_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("entries"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:

        # we don't always know the total up front when multiple collections;
        # so use an indeterminate spinner
        fetch_task = progress.add_task("[cyan]Fetching BibTeX entries...", total=None)

        for coll in coll_ids:
            # build URL for this collection (or for library if coll is None)
            if coll:
                url = f"https://api.zotero.org/{base}/{user_id}/collections/{coll}/items/top"
            else:
                url = f"https://api.zotero.org/{base}/{user_id}/items/top"

            next_url = url
            while next_url:
                params = construct_zotero_params(next_url, cred, proj)
                resp = requests.get(next_url, params=params)
                resp.raise_for_status()

                text = resp.text
                if text:
                    bib_parts.append(text.rstrip() + "\n")
                    batch = text.count("\n@")
                    total_entries += batch
                    progress.update(fetch_task, advance=batch)

                # parse for next page
                link_hdr = resp.headers.get("Link", "")
                next_url = None
                for link_part in requests.utils.parse_header_links(
                    link_hdr.rstrip(">")
                ):
                    if link_part.get("rel") == "next":
                        next_url = link_part["url"]
                        break

                page_count += 1
                time.sleep(0.1)  # rate‐limiting

    # header
    zotero_path = f"{base}/{user_id}"
    if proj.get("zotero_collection_id"):
        zotero_path += "/collections/" + proj["zotero_collection_id"]
    info = (
        "% Generated by Zotero Overleaf Sync\n"
        f"% Updated on {datetime.now().isoformat()}\n"
        f"% Zotero path: {zotero_path}\n"
        f"% Collections fetched: {len(coll_ids)}\n"
        f"% Total entries: {total_entries}\n\n"
    )

    logger.info(
        f"✅ Fetched {total_entries} entries in {page_count} pages from {len(coll_ids)} collections"
    )
    return info + "".join(bib_parts)


def construct_zotero_params(url: str, cred: dict, proj: dict) -> dict:
    """Construct parameters for Zotero API request."""
    params = {}
    if "format" not in url:
        params["format"] = "bibtex"
    if "key" not in url:
        params["key"] = cred["api_key"]
    if "limit" not in url:
        params["limit"] = ZOTERO_PAGE_LIMIT
    return params


def update_bib_and_push(
    repo: Repo, repo_path: str, zotero_cred: dict, proj: dict
) -> None:
    """Update bibliography file and push to repository."""
    console.print("[bold blue]Generating bibliography...")
    bib = fetch_zotero_bib(zotero_cred, proj)

    bib_file = Path(repo_path) / "references.bib"

    console.print("[bold blue]Writing bibliography file...")
    bib_file.write_text(bib, encoding="utf-8")
    repo.git.add("references.bib")

    if repo.is_dirty():
        with console.status("[bold blue]Committing and pushing changes..."):
            repo.index.commit("Sync Zotero .bib")
            repo.remotes.origin.push()
        logger.info("🚀 Changes pushed to Overleaf successfully")
    else:
        logger.info("💡 No changes detected, nothing to push")


def display_welcome():
    """Display welcome message."""
    welcome_panel = Panel.fit(
        Text.from_markup(
            "[bold blue]Overleaf Zotero Sync Tool[/bold blue]\n"
            "[dim]Sync your Overleaf bibliography with Zotero[/dim]\n"
            "[dim]Version __OZS_VERSION__ - Copyright (c) 2025, GitHub User @windingwind[/dim]\n"
            "[dim]This tool is distributed under the GNU Affero General Public License (AGPL) v3.0[/dim]\n"
            "[dim]For more information, visit: https://github.com/windingwind/overleaf-zotero-sync[/dim]\n"
            "[dim]Press Ctrl+C to exit at any time[/dim]"
        ),
        border_style="blue",
    )
    console.print(welcome_panel)


def main():
    """Main function with enhanced UI and error handling."""
    try:
        display_welcome()

        # Load configurations
        configs = load_configs(CONFIG_PATH)

        # Choose Zotero credentials
        console.print("\n[bold yellow]Step 1: Select Zotero Credentials[/bold yellow]")
        zotero_cred = choose_zotero_cred(configs)

        # Choose Overleaf auth token
        console.print("\n[bold yellow]Step 2: Select Overleaf Auth Token[/bold yellow]")
        token_entry = choose_overleaf_token(configs)
        if not token_entry:
            console.print("\n[yellow]No Overleaf token selected, exiting...[/yellow]")
            sys.exit(0)

        # Choose Overleaf project
        console.print("\n[bold yellow]Step 3: Select Overleaf Project[/bold yellow]")
        overleaf_proj = choose_overleaf_proj(configs, token_entry)

        # Save configurations
        save_configs(CONFIG_PATH, configs)

        # Sync process
        console.print("\n[bold yellow]Step 4: Synchronization[/bold yellow]")

        repo, path, is_temp = clone_or_update_repo(
            overleaf_proj["git_url"],
            overleaf_proj["auth_token"],
            overleaf_proj.get("local_dir"),
        )

        try:
            update_bib_and_push(repo, path, zotero_cred, overleaf_proj)
            overleaf_proj["last_run"] = datetime.now().isoformat()

            # Success message
            success_panel = Panel.fit(
                Text.from_markup(
                    "[bold green]✅ Synchronization Complete![/bold green]\n"
                    f"[dim]Project: {overleaf_proj['name']}[/dim]\n"
                    f"[dim]Bibliography updated successfully[/dim]"
                ),
                border_style="green",
            )
            console.print(success_panel)
        except requests.RequestException as e:
            console.print(
                f"\n[bold red]❌ Network error during synchronization: {e}[/bold red]"
            )
            logger.exception("Network error during synchronization")
        except Exception as e:
            console.print(
                f"\n[bold red]❌ Error during synchronization: {e}[/bold red]"
            )
            logger.exception("Error during synchronization")
            raise
        finally:
            if is_temp:
                console.print("[dim]Cleaning up temporary files...")
                shutil.rmtree(path, ignore_errors=True)

        # Save final configuration
        save_configs(CONFIG_PATH, configs)

    except KeyboardInterrupt:
        console.print("\n[yellow]❌ Operation cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[bold red]❌ Error: {e}[/bold red]")
        logger.exception("Detailed error information:")
        sys.exit(1)


if __name__ == "__main__":
    main()
