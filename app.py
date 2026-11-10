from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, current_app, session
from pathlib import Path
from database.db import init_db, get_db, close_db
from modules.github_integration import clone_or_update_repo
from modules.code_analyzer import analyze_repository
from modules.debt_detector import classify_findings, debt_summary
from modules.health_score import calculate_health_score
from config import Config
import json, io, csv, os, hmac
from datetime import datetime
from urllib.parse import urlparse


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["REPOSITORY_DIR"]).mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()

    @app.before_request
    def require_login():
        if app.config.get("AUTH_DISABLED") or request.endpoint in {"login", "static"}:
            return None
        if not session.get("authenticated"):
            return redirect(url_for("login", next=request.path))

    @app.before_request
    def protect_post_requests():
        if app.config.get("AUTH_DISABLED") or request.method != "POST":
            return None
        expected = session.get("csrf_token", "")
        supplied = request.form.get("csrf_token", "")
        if not expected or not supplied or not hmac.compare_digest(expected, supplied):
            return "Invalid or missing form security token. Refresh the page and try again.", 400

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:; form-action 'self'; frame-ancestors 'none'")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.context_processor
    def inject_globals():
        if "csrf_token" not in session:
            session["csrf_token"] = os.urandom(24).hex()
        return {"current_year": datetime.now().year, "logged_in": bool(session.get("authenticated")), "csrf_token": session["csrf_token"]}

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            valid_user = hmac.compare_digest(username, str(app.config["ADMIN_USERNAME"]))
            valid_pass = hmac.compare_digest(password, str(app.config["ADMIN_PASSWORD"]))
            if valid_user and valid_pass:
                session.clear()
                session["authenticated"] = True
                session.permanent = True
                target = request.args.get("next", "")
                if not target.startswith("/") or target.startswith("//"):
                    target = url_for("dashboard")
                return redirect(target)
            flash("Invalid username or password.", "error")
        return render_template("login.html")

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/")
    def dashboard():
        db = get_db()
        projects = db.execute("SELECT * FROM projects ORDER BY id DESC").fetchall()
        total = len(projects)
        analysis_count = db.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        latest = db.execute("SELECT * FROM analyses ORDER BY id DESC LIMIT 1").fetchone()
        totals = db.execute("SELECT COALESCE(SUM(files_scanned),0), COALESCE(SUM(defected_files),0) FROM (SELECT a.files_scanned,a.defected_files FROM analyses a JOIN (SELECT project_id,MAX(id) id FROM analyses GROUP BY project_id) x ON a.id=x.id)").fetchone()
        recent = db.execute("SELECT a.*, p.name AS project_name FROM analyses a JOIN projects p ON p.id=a.project_id ORDER BY a.id DESC LIMIT 6").fetchall()
        latest_scores = db.execute("SELECT p.name, (SELECT health_score FROM analyses a WHERE a.project_id=p.id ORDER BY a.id DESC LIMIT 1) AS score FROM projects p ORDER BY p.id DESC LIMIT 8").fetchall()
        return render_template("dashboard.html", projects=projects, total=total, analysis_count=analysis_count,
                               recent=recent, latest_scores=latest_scores, latest=latest,
                               total_scanned=totals[0], total_defected=totals[1])

    @app.route("/projects")
    def projects():
        rows = get_db().execute("SELECT p.*, (SELECT health_score FROM analyses a WHERE a.project_id=p.id ORDER BY a.id DESC LIMIT 1) AS health_score, (SELECT files_scanned FROM analyses a WHERE a.project_id=p.id ORDER BY a.id DESC LIMIT 1) AS files_scanned, (SELECT defected_files FROM analyses a WHERE a.project_id=p.id ORDER BY a.id DESC LIMIT 1) AS defected_files FROM projects p ORDER BY p.id DESC").fetchall()
        return render_template("projects.html", projects=rows)

    def valid_repo_url(value):
        if not value:
            return ""
        parsed = urlparse(value)
        if parsed.scheme != "https" or parsed.netloc.lower() not in {"github.com", "www.github.com"}:
            raise ValueError("Repository URL must be an HTTPS GitHub URL.")
        return value.strip()

    @app.route("/projects/new", methods=["GET", "POST"])
    def create_project():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            if not name or len(name) > 120:
                flash("Project name is required and must be 120 characters or fewer.", "error")
                return render_template("edit_project.html", project=None)
            try:
                repo_url = valid_repo_url(request.form.get("repo_url", "").strip())
            except ValueError as exc:
                flash(str(exc), "error")
                return render_template("edit_project.html", project=None)
            db = get_db()
            db.execute("INSERT INTO projects(name, description, repo_url, language) VALUES(?,?,?,?)",
                       (name, request.form.get("description", "").strip()[:2000], repo_url,
                        request.form.get("language", "Python").strip()[:40] or "Unknown"))
            db.commit()
            flash("Project created. Connect a repository and run Analyze.", "success")
            return redirect(url_for("projects"))
        return render_template("edit_project.html", project=None)

    @app.route("/projects/<int:project_id>/edit", methods=["GET", "POST"])
    def edit_project(project_id):
        db = get_db()
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            flash("Project not found.", "error"); return redirect(url_for("projects"))
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            try:
                repo_url = valid_repo_url(request.form.get("repo_url", "").strip())
            except ValueError as exc:
                flash(str(exc), "error"); return render_template("edit_project.html", project=project)
            if not name or len(name) > 120:
                flash("Project name is required and must be 120 characters or fewer.", "error")
                return render_template("edit_project.html", project=project)
            db.execute("UPDATE projects SET name=?,description=?,repo_url=?,language=? WHERE id=?",
                       (name, request.form.get("description", "").strip()[:2000], repo_url,
                        request.form.get("language", "Python").strip()[:40] or "Unknown", project_id))
            db.commit(); flash("Project updated.", "success"); return redirect(url_for("projects"))
        return render_template("edit_project.html", project=project)

    @app.post("/projects/<int:project_id>/delete")
    def delete_project(project_id):
        db = get_db()
        db.execute("DELETE FROM issues WHERE project_id=?", (project_id,))
        db.execute("DELETE FROM analyses WHERE project_id=?", (project_id,))
        db.execute("DELETE FROM projects WHERE id=?", (project_id,))
        db.commit(); flash("Project and related history deleted.", "success"); return redirect(url_for("projects"))

    @app.post("/projects/<int:project_id>/analyze")
    def analyze_project(project_id):
        db = get_db()
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            flash("Project not found.", "error"); return redirect(url_for("projects"))
        if not project["repo_url"]:
            flash("Add a valid public GitHub HTTPS URL before analysis.", "error")
            return redirect(url_for("edit_project", project_id=project_id))
        try:
            destination = Path(current_app.config["REPOSITORY_DIR"]) / f"project_{project_id}"
            repo_path = clone_or_update_repo(project["repo_url"], destination)
            raw = analyze_repository(repo_path)
            findings = classify_findings(raw["findings"])
            score = calculate_health_score(findings, raw["files_scanned"])
            summary = debt_summary(findings)
            if raw["files_scanned"] == 0:
                flash("Repository cloned, but no Python files were found. Check the repository branch and contents.", "error")
                return redirect(url_for("projects"))
            cur = db.execute("INSERT INTO analyses(project_id,health_score,files_scanned,issue_count,findings_json,summary_json,defected_files) VALUES(?,?,?,?,?,?,?)",
                (project_id, score, raw["files_scanned"], len(findings), json.dumps(findings), json.dumps(summary), raw["defected_files"]))
            analysis_id = cur.lastrowid
            for item in findings:
                db.execute("INSERT INTO issues(project_id,analysis_id,title,severity,category,file_path,line_number,description,status) VALUES(?,?,?,?,?,?,?,?, 'Open')",
                    (project_id, analysis_id, f'{item["category"]}: {item["message"][:150]}', item["severity"], item["category"], item["file"], item["line"], item["message"]))
            db.commit()
            flash(f'Analysis complete: {raw["files_scanned"]} Python files scanned; {raw["defected_files"]} defected files; {len(findings)} findings.', "success")
            return redirect(url_for("analysis_detail", project_id=project_id, analysis_id=analysis_id))
        except Exception as exc:
            current_app.logger.exception("Project analysis failed for project_id=%s", project_id)
            flash(f"Analysis failed: {str(exc)[:240]}. Verify Git is installed and the repository is public.", "error")
            return redirect(url_for("projects"))

    @app.route("/projects/<int:project_id>/analysis")
    def analysis_history(project_id):
        db = get_db(); project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            flash("Project not found.", "error"); return redirect(url_for("projects"))
        analyses = db.execute("SELECT * FROM analyses WHERE project_id=? ORDER BY id DESC", (project_id,)).fetchall()
        latest = analyses[0] if analyses else None
        return redirect(url_for("analysis_detail", project_id=project_id, analysis_id=latest["id"])) if latest else render_template("analysis.html", project=project, analyses=[], latest=None, findings=[], summary={})

    @app.route("/projects/<int:project_id>/analysis/<int:analysis_id>")
    def analysis_detail(project_id, analysis_id):
        db = get_db(); project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        analysis = db.execute("SELECT * FROM analyses WHERE id=? AND project_id=?", (analysis_id, project_id)).fetchone()
        if not project or not analysis:
            flash("Analysis report not found.", "error"); return redirect(url_for("projects"))
        analyses = db.execute("SELECT * FROM analyses WHERE project_id=? ORDER BY id DESC", (project_id,)).fetchall()
        findings = json.loads(analysis["findings_json"]); summary = json.loads(analysis["summary_json"])
        return render_template("analysis.html", project=project, analyses=analyses, latest=analysis, findings=findings, summary=summary)

    @app.route("/technical-debt")
    def technical_debt():
        rows = get_db().execute("SELECT i.*, p.name AS project_name FROM issues i JOIN projects p ON p.id=i.project_id ORDER BY CASE i.severity WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END, i.id DESC").fetchall()
        return render_template("technical_debt.html", issues=rows)

    @app.route("/issues")
    def issues():
        db = get_db(); rows = db.execute("SELECT i.*, p.name AS project_name FROM issues i JOIN projects p ON p.id=i.project_id ORDER BY i.id DESC").fetchall()
        projects = db.execute("SELECT id,name FROM projects ORDER BY name").fetchall()
        return render_template("issues.html", issues=rows, projects=projects)

    @app.post("/issues/<int:issue_id>/status")
    def update_issue_status(issue_id):
        status = request.form.get("status", "Open")
        if status not in {"Open", "In Progress", "Resolved"}:
            flash("Invalid issue status.", "error")
        else:
            db = get_db(); db.execute("UPDATE issues SET status=? WHERE id=?", (status, issue_id)); db.commit()
            flash("Issue status updated.", "success")
        return redirect(request.referrer or url_for("issues"))

    @app.route("/reports/<int:analysis_id>.json")
    def download_json_report(analysis_id):
        row = get_db().execute("SELECT * FROM analyses WHERE id=?", (analysis_id,)).fetchone()
        if not row: flash("Report not found.", "error"); return redirect(url_for("projects"))
        payload = {k: row[k] for k in row.keys() if k not in ("findings_json", "summary_json")}
        payload["findings"] = json.loads(row["findings_json"]); payload["technical_debt_summary"] = json.loads(row["summary_json"])
        return jsonify(payload)

    @app.route("/reports/<int:analysis_id>.csv")
    def download_csv_report(analysis_id):
        row = get_db().execute("SELECT * FROM analyses WHERE id=?", (analysis_id,)).fetchone()
        if not row: flash("Report not found.", "error"); return redirect(url_for("projects"))
        findings = json.loads(row["findings_json"]); output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["severity", "category", "file", "line", "message"]); writer.writeheader()
        for item in findings: writer.writerow({k: item.get(k, "") for k in writer.fieldnames})
        return send_file(io.BytesIO(output.getvalue().encode("utf-8-sig")), mimetype="text/csv", as_attachment=True, download_name=f"codepulse-analysis-{analysis_id}.csv")

    return app

app = create_app()
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=False)
