from pathlib import Path
import re, subprocess, shutil
from urllib.parse import urlparse


def validate_github_url(url):
    parsed = urlparse((url or "").strip())
    if parsed.scheme != "https" or parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        raise ValueError("Use a public HTTPS URL from github.com.")
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) != 2 or not all(re.fullmatch(r"[A-Za-z0-9_.-]+", p) for p in parts):
        raise ValueError("Repository URL must look like https://github.com/owner/repository.")
    owner, repo = parts
    if repo.endswith(".git"):
        repo = repo[:-4]
    if owner in {".", ".."} or repo in {"", ".", ".."}:
        raise ValueError("Invalid GitHub repository URL.")
    return f"https://github.com/{owner}/{repo}.git"


def clone_or_update_repo(repo_url, destination):
    url = validate_github_url(repo_url)
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if (destination / ".git").exists():
        result = subprocess.run(["git", "-C", str(destination), "pull", "--ff-only"], capture_output=True, text=True, timeout=180)
    else:
        if destination.exists():
            shutil.rmtree(destination)
        result = subprocess.run(["git", "clone", "--depth", "1", url, str(destination)], capture_output=True, text=True, timeout=240)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Git operation failed").strip()
        raise RuntimeError(detail[-700:])
    return destination
