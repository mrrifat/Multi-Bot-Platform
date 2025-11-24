# 🤖 Multi-Bot Platform

A minimal Heroku/Render-style platform for running multiple Telegram bots on a single Ubuntu VPS. Built with Docker, Python FastAPI, and a simple web dashboard.

## 📋 Overview

This platform allows you to:
- **Create and manage** multiple bot applications
- **Configure environment variables** per bot
- **Deploy bots** via Git repository or ZIP upload
- **Start, stop, and restart** bot containers
- **View real-time logs** for each bot
- **Track deployment history**

## 🏗️ Architecture

- **Backend**: Python FastAPI with SQLAlchemy (SQLite database)
- **Frontend**: Server-rendered HTML with Jinja2 templates
- **Container Runtime**: Docker for bot isolation
- **Authentication**: Session-based login with bcrypt password hashing
- **Bot Runtime**: Each bot runs in its own Docker container (Python 3.11)

## 🚀 Quick Start

### Prerequisites

- Ubuntu VPS (tested on Ubuntu 20.04+)
- Docker and Docker Compose installed
- At least 2GB RAM recommended
- Root or sudo access

### Installation

1. **Clone this repository**:
   ```bash
   git clone https://github.com/mrrifat/Multi-Bot-Platform.git
   cd Multi-Bot-Platform
   ```

2. **Set up the environment** (Optional but recommended):
   ```bash
   # Generate a random secret key
   export SECRET_KEY=$(openssl rand -hex 32)
   # Or edit docker-compose.yml to set a permanent SECRET_KEY
   ```

3. **Build and start the platform**:
   ```bash
   docker-compose up -d --build
   ```

4. **Access the dashboard**:
   - Open your browser to: `http://your-vps-ip:8000`
   - Default credentials:
     - Email: `admin@example.com`
     - Password: `admin123`
   - **⚠️ Change the default password immediately after first login!**

### Verify Installation

Check that the container is running:
```bash
docker ps
```

You should see `bot-platform-api` running.

Check logs:
```bash
docker-compose logs -f
```

## 📖 Usage Guide

### Creating Your First Bot

1. **Login** to the dashboard
2. Click **"+ Create New Bot"**
3. Fill in the form:
   - **Bot Name**: e.g., `my-telegram-bot` (lowercase, hyphens allowed)
   - **Runtime**: Python (currently only option)
   - **Start Command**: e.g., `python bot.py`
   - **Git Repository URL**: Optional - provide your bot's Git repo URL

4. Click **"Create Bot"**

### Configuring Environment Variables

1. Navigate to your bot's detail page
2. Scroll to **"Environment Variables"** section
3. Add your bot's required env vars (e.g., `BOT_TOKEN`, `ADMIN_ID`, etc.)
4. Click **"💾 Save Environment Variables"**
5. **Important**: Restart the bot after updating env vars

### Deploying Bot Code

You have two deployment options:

#### Option 1: Deploy from Git

1. Ensure your bot has a `repo_url` configured
2. Click **"🚀 Deploy from Git"**
3. The platform will:
   - Clone or pull the latest code
   - Build a Docker image
   - Restart the bot container

#### Option 2: Upload ZIP

1. Click **"📦 Upload Code (ZIP)"**
2. Select your ZIP file containing:
   - `bot.py` (or your main bot file)
   - `requirements.txt` (optional)
   - Any other required files
3. Click **"Upload & Deploy"**

### Managing Bots

- **▶️ Start**: Start a stopped bot
- **⏹ Stop**: Stop a running bot
- **🔄 Restart**: Restart a running bot (useful after env var changes)
- **📋 View Logs**: See the last 200 lines of container logs

### Bot Code Requirements

Your bot repository or ZIP should contain:

1. **bot.py** (or your specified start file):
   ```python
   # Example Telegram bot
   import os
   from telegram.ext import ApplicationBuilder

   BOT_TOKEN = os.getenv("BOT_TOKEN")

   app = ApplicationBuilder().token(BOT_TOKEN).build()

   # Add your handlers here

   app.run_polling()
   ```

2. **requirements.txt** (optional but recommended):
   ```
   python-telegram-bot==20.7
   # Add other dependencies
   ```

3. Your bot should use **polling mode** (not webhooks in MVP)

## 🔧 Advanced Configuration

### Changing the Secret Key

Edit `docker-compose.yml`:
```yaml
environment:
  - SECRET_KEY=your-super-secret-random-key-here
```

Then restart:
```bash
docker-compose down
docker-compose up -d
```

### Custom Bot Start Commands

When creating a bot, you can specify custom start commands:
- `python main.py`
- `python src/bot.py`
- `python3 app.py`

### Accessing the Database

The SQLite database is stored at `./data/bot_platform.db`. You can access it with:
```bash
sqlite3 data/bot_platform.db
```

### Viewing Platform Logs

```bash
# Follow all logs
docker-compose logs -f

# View specific service
docker-compose logs -f bot-platform-api

# Last 100 lines
docker-compose logs --tail=100
```

## 🐳 Docker Management

### View All Bot Containers

```bash
docker ps -a --filter "name=bot_"
```

### Stop All Bots

```bash
docker stop $(docker ps -q --filter "name=bot_")
```

### Clean Up Unused Images

```bash
docker image prune -a
```

## 📁 Project Structure

```
VPS-Manager/
├── docker-compose.yml          # Main orchestration file
├── data/                        # SQLite database storage
│   └── bot_platform.db         # Created automatically
├── bots-data/                   # Bot code storage (created automatically)
│   └── <bot-name>/             # Each bot has its own directory
├── backend/
│   ├── Dockerfile              # Platform API container
│   ├── main.py                 # FastAPI application
│   ├── models.py               # Database models
│   ├── database.py             # Database configuration
│   ├── schemas.py              # Pydantic schemas
│   ├── auth.py                 # Authentication logic
│   ├── docker_manager.py       # Docker operations
│   ├── requirements.txt        # Python dependencies
│   ├── BotDockerfile.template  # Template for bot images
│   ├── templates/              # Jinja2 HTML templates
│   │   ├── base.html
│   │   ├── login.html
│   │   └── bots/
│   │       ├── list.html
│   │       ├── new.html
│   │       ├── detail.html
│   │       ├── upload.html
│   │       └── logs.html
│   └── static/                 # Static files (CSS/JS if needed)
```

## 🔒 Security Considerations

**⚠️ Important**: This platform is designed for **single-tenant, personal use**.

Security measures to implement:

1. **Change default password** immediately after first login
2. **Use a strong SECRET_KEY** in production
3. **Enable firewall** and restrict port 8000 access:
   ```bash
   sudo ufw allow from your-ip to any port 8000
   ```
4. **Use HTTPS** with a reverse proxy (Nginx/Caddy):
   - Set up SSL certificates (Let's Encrypt)
   - Proxy `https://yourdomain.com` to `http://localhost:8000`

5. **Regular backups** of `./data/bot_platform.db` and `./bots-data/`

## 🛠️ Troubleshooting

### Bot won't start

1. Check if image was built:
   ```bash
   docker images | grep bot_
   ```

2. Check deployment logs in the dashboard

3. Verify env vars are set correctly

4. Check bot logs for errors

### Platform API won't start

```bash
# Check logs
docker-compose logs bot-platform-api

# Rebuild
docker-compose down
docker-compose up -d --build
```

### Permission issues with bot storage

```bash
# Ensure correct ownership of bot storage directory
sudo chown -R $USER:$USER ./bots-data
sudo chmod -R 755 ./bots-data
```

### Docker socket permission denied

Add your user to the docker group:
```bash
sudo usermod -aG docker $USER
# Log out and back in
```

## 📝 TODO / Future Enhancements

- [ ] Support for Node.js runtime
- [ ] Webhook support for bots
- [ ] Resource limits (CPU/memory) per bot
- [ ] User management (multiple users)
- [ ] Email notifications for failed deployments
- [ ] Metrics and monitoring dashboard
- [ ] Automatic SSL with Caddy
- [ ] Bot scheduling (cron jobs)
- [ ] Database encryption for env vars

## 🤝 Contributing

This is a personal project, but feel free to fork and customize for your needs!

## 📄 License

MIT License - feel free to use and modify as needed.

## 🆘 Support

For issues or questions:
1. Check the logs: `docker-compose logs -f`
2. Verify Docker is running: `docker ps`
3. Check bot container logs via the dashboard
4. Review the troubleshooting section above

---

**Built with ❤️ for managing Telegram bots efficiently**
