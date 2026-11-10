# CodePulse

CodePulse is a local Flask application for connecting public GitHub repositories, statically scanning Python source files, reviewing technical debt, tracking project health and exporting scan reports.

## Features

- Responsive dark dashboard and project workspace
- GitHub HTTPS repository validation and clone/update integration
- Python AST-based static analysis; repository source is never executed
- Findings grouped into High, Medium and Low severity
- Distinct defected-file count, scanned Python-file count and heuristic health score
- Analysis history, issue workflow, CSV and JSON exports
- SQLite persistence with schema migration for existing databases
- Session-based login, secure cookie defaults, request size limit and security response headers

## Windows setup

1. Install Python 3.10+ and Git for Windows.
2. Extract the ZIP. Open the **CodePulse** folder in VS Code (the folder containing `app.py`).
3. Open Terminal → New Terminal and run:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

4. Open `http://127.0.0.1:5000`.

### First login

- Username: `admin`
- Password: `ChangeThisPassword123!`

Change the password before sharing the application or using it beyond a local demonstration. In PowerShell, set environment variables before starting the app:

```powershell
$env:CODEPULSE_ADMIN_USERNAME = "your-admin-name"
$env:CODEPULSE_ADMIN_PASSWORD = "use-a-long-unique-password"
$env:CODEPULSE_SECRET_KEY = "generate-a-long-random-secret"
python app.py
```

The app creates a persistent random secret key under `instance/` if `CODEPULSE_SECRET_KEY` is not supplied. Do not commit `instance/`, `.venv/`, credentials, or tokens.

## Connect and scan a GitHub repository

1. Click **New project**.
2. Enter a project name and a public repository URL, for example `https://github.com/owner/repository`.
3. Save the project.
4. Open **Projects** and click **Analyze**.
5. Review the health score, scanned Python files, defected files, severity breakdown and findings. Export CSV or JSON from the analysis page.

Git must be installed and available on PATH. This version scans public GitHub repositories. Private repository authentication is not enabled.

## Analyzer behavior

CodePulse uses Python's AST parser and source-text checks. It does not import or run code from the connected repository. It currently checks selected patterns including dynamic execution (`eval`/`exec`), unsafe pickle deserialization, subprocess `shell=True`, hardcoded credential-like assignments, weak hashes, YAML loading, bare exceptions, unused imports, long functions, estimated complexity, long lines and TODO/FIXME markers.

The health score is a heuristic indicator calculated from finding severity and the number of Python files scanned. It is not a guarantee of correctness, absence of vulnerabilities, or a formal security certification. Static checks can produce false positives and miss issues.

## Data and folders

- `database/`: SQLite access and schema setup
- `modules/`: GitHub integration, Python analyzer, debt classification and health score
- `templates/`: Flask/Jinja pages
- `static/`: CSS and JavaScript
- `tests/`: automated tests
- `instance/`: local database, cloned repositories and generated secret key (created at runtime; do not commit)
- `reports/`: reserved for report artifacts; downloadable reports are generated on demand

## Run tests

```powershell
python -m unittest discover -s tests -v
```

## Troubleshooting

- **`git` is not recognized:** install Git for Windows, restart VS Code and retry.
- **No Python files found:** confirm the repository has `.py` files on its default branch and that it is public.
- **Clone fails:** verify the repository URL, internet access and repository visibility.
- **Port 5000 is busy:** stop the other Flask process with `Ctrl+C` or set a different `PORT` environment variable.
