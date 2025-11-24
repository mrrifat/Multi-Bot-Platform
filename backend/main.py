import os
import shutil
import zipfile
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Request, Depends, HTTPException, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

import models
import schemas
from database import engine, get_db
from auth import (
    authenticate_user,
    create_default_admin_user,
    create_session_token,
    verify_session_token,
)
from docker_manager import (
    get_bot_status,
    build_bot_image,
    run_bot_container,
    stop_bot_container,
    restart_bot_container,
    get_bot_logs,
    clone_or_pull_repo,
)

# Create database tables
models.Base.metadata.create_all(bind=engine)

# Create default admin user
with next(get_db()) as db:
    create_default_admin_user(db)

# Initialize FastAPI app
app = FastAPI(title="Multi-Bot Platform")

# Add session middleware
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-to-a-random-secret-key-in-production")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Static files and templates
# Ensure static directory exists
static_dir = Path("static")
static_dir.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# Authentication dependency
def get_current_user(request: Request, db: Session = Depends(get_db)) -> models.User:
    """Get the current authenticated user from session."""
    session_token = request.session.get("session_token")
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session_data = verify_session_token(session_token)
    if not session_data:
        raise HTTPException(status_code=401, detail="Invalid session")

    user = db.query(models.User).filter(models.User.id == session_data["user_id"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


# Optional auth dependency for templates
def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[models.User]:
    """Get current user if authenticated, None otherwise."""
    try:
        return get_current_user(request, db)
    except HTTPException:
        return None


# ============================================
# AUTH ROUTES
# ============================================

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Display login page."""
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Handle login form submission."""
    user = authenticate_user(db, email, password)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid email or password"}
        )

    # Create session
    session_token = create_session_token(user.id)
    request.session["session_token"] = session_token

    return RedirectResponse(url="/bots", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    """Clear session and logout."""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


# ============================================
# BOT ROUTES
# ============================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Redirect to bots list."""
    return RedirectResponse(url="/bots")


@app.get("/bots", response_class=HTMLResponse)
async def list_bots(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """List all bots."""
    bots = db.query(models.BotApp).all()

    # Enrich with status and last deployment
    bots_data = []
    for bot in bots:
        status = get_bot_status(bot.id)
        last_deployment = (
            db.query(models.Deployment)
            .filter(models.Deployment.bot_id == bot.id)
            .order_by(models.Deployment.created_at.desc())
            .first()
        )
        bots_data.append({
            "bot": bot,
            "status": status,
            "last_deployment": last_deployment
        })

    return templates.TemplateResponse(
        "bots/list.html",
        {"request": request, "bots_data": bots_data, "user": current_user}
    )


@app.get("/bots/new", response_class=HTMLResponse)
async def new_bot_page(
    request: Request,
    current_user: models.User = Depends(get_current_user)
):
    """Display form to create a new bot."""
    return templates.TemplateResponse(
        "bots/new.html",
        {"request": request, "user": current_user}
    )


@app.post("/bots")
async def create_bot(
    request: Request,
    name: str = Form(...),
    runtime: str = Form("python"),
    start_command: str = Form("python bot.py"),
    repo_url: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Create a new bot."""
    # Check if name already exists
    existing = db.query(models.BotApp).filter(models.BotApp.name == name).first()
    if existing:
        return templates.TemplateResponse(
            "bots/new.html",
            {"request": request, "user": current_user, "error": f"Bot with name '{name}' already exists"}
        )

    # Create code path
    code_path = f"/srv/bots/{name}"
    os.makedirs(code_path, exist_ok=True)

    # Create bot record
    bot = models.BotApp(
        name=name,
        repo_url=repo_url.strip() if repo_url and repo_url.strip() else None,
        code_path=code_path,
        runtime=runtime,
        start_command=start_command
    )
    db.add(bot)
    db.commit()
    db.refresh(bot)

    return RedirectResponse(url=f"/bots/{bot.id}", status_code=303)


@app.get("/bots/{bot_id}", response_class=HTMLResponse)
async def bot_detail(
    request: Request,
    bot_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Display bot details."""
    bot = db.query(models.BotApp).filter(models.BotApp.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    status = get_bot_status(bot.id)
    deployments = (
        db.query(models.Deployment)
        .filter(models.Deployment.bot_id == bot_id)
        .order_by(models.Deployment.created_at.desc())
        .limit(10)
        .all()
    )

    return templates.TemplateResponse(
        "bots/detail.html",
        {
            "request": request,
            "bot": bot,
            "status": status,
            "deployments": deployments,
            "user": current_user
        }
    )


@app.post("/bots/{bot_id}/envvars")
async def update_env_vars(
    bot_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Update environment variables for a bot."""
    bot = db.query(models.BotApp).filter(models.BotApp.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    form_data = await request.form()

    # Clear existing env vars
    db.query(models.BotEnvVar).filter(models.BotEnvVar.bot_id == bot_id).delete()

    # Add new env vars from form
    for key, value in form_data.items():
        if key.startswith("env_key_"):
            index = key.replace("env_key_", "")
            value_key = f"env_value_{index}"
            if value and value.strip() and value_key in form_data:
                env_var = models.BotEnvVar(
                    bot_id=bot_id,
                    key=value.strip(),
                    value=form_data[value_key]
                )
                db.add(env_var)

    db.commit()

    return RedirectResponse(url=f"/bots/{bot_id}", status_code=303)


@app.post("/bots/{bot_id}/start")
async def start_bot(
    bot_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Start a bot container."""
    bot = db.query(models.BotApp).filter(models.BotApp.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    # Get env vars
    env_vars = {ev.key: ev.value for ev in bot.env_vars}

    # Run container
    success, message = run_bot_container(bot.id, env_vars, bot.start_command)

    if not success:
        raise HTTPException(status_code=500, detail=message)

    return RedirectResponse(url=f"/bots/{bot_id}", status_code=303)


@app.post("/bots/{bot_id}/stop")
async def stop_bot(
    bot_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Stop a bot container."""
    bot = db.query(models.BotApp).filter(models.BotApp.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    success, message = stop_bot_container(bot.id)

    if not success:
        raise HTTPException(status_code=500, detail=message)

    return RedirectResponse(url=f"/bots/{bot_id}", status_code=303)


@app.post("/bots/{bot_id}/restart")
async def restart_bot(
    bot_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Restart a bot container."""
    bot = db.query(models.BotApp).filter(models.BotApp.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    # Get env vars
    env_vars = {ev.key: ev.value for ev in bot.env_vars}

    success, message = restart_bot_container(bot.id, env_vars, bot.start_command)

    if not success:
        raise HTTPException(status_code=500, detail=message)

    return RedirectResponse(url=f"/bots/{bot_id}", status_code=303)


@app.post("/bots/{bot_id}/deploy")
async def deploy_bot(
    bot_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Deploy a bot from Git repository."""
    bot = db.query(models.BotApp).filter(models.BotApp.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    if not bot.repo_url:
        raise HTTPException(status_code=400, detail="No repository URL configured")

    # Create deployment record
    deployment = models.Deployment(bot_id=bot_id, status="pending")
    db.add(deployment)
    db.commit()
    db.refresh(deployment)

    logs = []

    # Clone or pull repository
    success, message = clone_or_pull_repo(bot.repo_url, bot.code_path)
    logs.append(message)

    if not success:
        deployment.status = "failed"
        deployment.log = "\n".join(logs)
        db.commit()
        raise HTTPException(status_code=500, detail=message)

    # Build image
    success, message = build_bot_image(bot.id, bot.code_path)
    logs.append(message)

    if not success:
        deployment.status = "failed"
        deployment.log = "\n".join(logs)
        db.commit()
        raise HTTPException(status_code=500, detail=message)

    # Get env vars and restart container
    env_vars = {ev.key: ev.value for ev in bot.env_vars}
    success, message = restart_bot_container(bot.id, env_vars, bot.start_command)
    logs.append(message)

    if success:
        deployment.status = "success"
    else:
        deployment.status = "failed"

    deployment.log = "\n".join(logs)
    db.commit()

    return RedirectResponse(url=f"/bots/{bot_id}", status_code=303)


@app.get("/bots/{bot_id}/upload", response_class=HTMLResponse)
async def upload_page(
    request: Request,
    bot_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Display upload form."""
    bot = db.query(models.BotApp).filter(models.BotApp.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    return templates.TemplateResponse(
        "bots/upload.html",
        {"request": request, "bot": bot, "user": current_user}
    )


@app.post("/bots/{bot_id}/upload")
async def upload_bot_code(
    bot_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Upload bot code as ZIP file."""
    bot = db.query(models.BotApp).filter(models.BotApp.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    # Create deployment record
    deployment = models.Deployment(bot_id=bot_id, status="pending")
    db.add(deployment)
    db.commit()
    db.refresh(deployment)

    logs = []

    try:
        # Save uploaded file temporarily
        temp_zip = f"/tmp/bot_{bot_id}_upload.zip"
        with open(temp_zip, "wb") as f:
            content = await file.read()
            f.write(content)

        logs.append(f"Uploaded file: {file.filename} ({len(content)} bytes)")

        # Clear existing code directory
        if os.path.exists(bot.code_path):
            shutil.rmtree(bot.code_path)
        os.makedirs(bot.code_path, exist_ok=True)

        # Extract ZIP
        with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
            zip_ref.extractall(bot.code_path)

        logs.append(f"Extracted to: {bot.code_path}")

        # Clean up temp file
        os.remove(temp_zip)

        # Build image
        success, message = build_bot_image(bot.id, bot.code_path)
        logs.append(message)

        if not success:
            deployment.status = "failed"
            deployment.log = "\n".join(logs)
            db.commit()
            raise HTTPException(status_code=500, detail=message)

        # Get env vars and restart container
        env_vars = {ev.key: ev.value for ev in bot.env_vars}
        success, message = restart_bot_container(bot.id, env_vars, bot.start_command)
        logs.append(message)

        if success:
            deployment.status = "success"
        else:
            deployment.status = "failed"

    except Exception as e:
        logs.append(f"Error: {str(e)}")
        deployment.status = "failed"

    deployment.log = "\n".join(logs)
    db.commit()

    return RedirectResponse(url=f"/bots/{bot_id}", status_code=303)


@app.get("/bots/{bot_id}/logs", response_class=HTMLResponse)
async def view_logs(
    request: Request,
    bot_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """View bot logs."""
    bot = db.query(models.BotApp).filter(models.BotApp.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    success, logs = get_bot_logs(bot.id, tail=200)

    if not success:
        logs = f"Error fetching logs: {logs}"

    return templates.TemplateResponse(
        "bots/logs.html",
        {"request": request, "bot": bot, "logs": logs, "user": current_user}
    )


# Health check endpoint
@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
