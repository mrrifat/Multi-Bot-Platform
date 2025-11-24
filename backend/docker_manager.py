import os
import shutil
import subprocess
from typing import Dict, Tuple, Optional
import docker
from docker.errors import DockerException, NotFound, APIError


# Initialize Docker client
try:
    # Try to connect to Docker socket directly
    docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
    # Test connection
    docker_client.ping()
    print("✓ Successfully connected to Docker daemon")
except DockerException as e:
    print(f"Warning: Could not connect to Docker: {e}")
    docker_client = None
except Exception as e:
    print(f"Warning: Unexpected error connecting to Docker: {e}")
    docker_client = None


def get_container_name(bot_id: int) -> str:
    """Get the standardized container name for a bot."""
    return f"bot_{bot_id}"


def get_image_name(bot_id: int) -> str:
    """Get the standardized image name for a bot."""
    return f"bot_{bot_id}:latest"


def get_bot_status(bot_id: int) -> str:
    """Check if a bot container is running."""
    if not docker_client:
        return "Unknown"

    container_name = get_container_name(bot_id)
    try:
        container = docker_client.containers.get(container_name)
        if container.status == "running":
            return "Running"
        else:
            return f"Stopped ({container.status})"
    except NotFound:
        return "Stopped"
    except Exception as e:
        return f"Error: {str(e)}"


def build_bot_image(bot_id: int, code_path: str) -> Tuple[bool, str]:
    """Build a Docker image for a bot."""
    if not docker_client:
        return False, "Docker client not available"

    image_name = get_image_name(bot_id)

    try:
        # Create Dockerfile in the bot's code directory
        dockerfile_path = os.path.join(code_path, "Dockerfile")

        # Copy the template Dockerfile
        template_path = "/app/BotDockerfile.template"
        if not os.path.exists(template_path):
            # Fallback to current directory
            template_path = "BotDockerfile.template"

        if os.path.exists(template_path):
            shutil.copy(template_path, dockerfile_path)
        else:
            # Create a basic Dockerfile if template doesn't exist
            with open(dockerfile_path, 'w') as f:
                f.write("""FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install if exists
COPY requirements.txt* ./
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

# Copy bot source code
COPY . .

# Default command (will be overridden)
CMD ["python", "bot.py"]
""")

        # Build the image
        output = []
        image, build_logs = docker_client.images.build(
            path=code_path,
            tag=image_name,
            rm=True,
            forcerm=True
        )

        for log in build_logs:
            if 'stream' in log:
                output.append(log['stream'].strip())

        log_text = "\n".join(output)
        return True, f"Image built successfully: {image_name}\n{log_text}"

    except Exception as e:
        return False, f"Failed to build image: {str(e)}"


def run_bot_container(bot_id: int, env_vars: Dict[str, str], start_command: str) -> Tuple[bool, str]:
    """Run a bot container with the given environment variables."""
    if not docker_client:
        return False, "Docker client not available"

    container_name = get_container_name(bot_id)
    image_name = get_image_name(bot_id)

    try:
        # Stop and remove existing container if it exists
        try:
            existing = docker_client.containers.get(container_name)
            existing.stop(timeout=10)
            existing.remove()
        except NotFound:
            pass

        # Parse start command
        command_parts = start_command.split() if start_command else ["python", "bot.py"]

        # Run new container
        container = docker_client.containers.run(
            image_name,
            name=container_name,
            environment=env_vars,
            command=command_parts,
            detach=True,
            restart_policy={"Name": "always"},
            network_mode="bridge"
        )

        return True, f"Container {container_name} started successfully (ID: {container.short_id})"

    except Exception as e:
        return False, f"Failed to run container: {str(e)}"


def stop_bot_container(bot_id: int) -> Tuple[bool, str]:
    """Stop a bot container."""
    if not docker_client:
        return False, "Docker client not available"

    container_name = get_container_name(bot_id)

    try:
        container = docker_client.containers.get(container_name)
        container.stop(timeout=10)
        container.remove()
        return True, f"Container {container_name} stopped successfully"
    except NotFound:
        return True, f"Container {container_name} is not running"
    except Exception as e:
        return False, f"Failed to stop container: {str(e)}"


def restart_bot_container(bot_id: int, env_vars: Dict[str, str], start_command: str) -> Tuple[bool, str]:
    """Restart a bot container."""
    stop_success, stop_msg = stop_bot_container(bot_id)
    if not stop_success:
        return False, f"Failed to stop container: {stop_msg}"

    run_success, run_msg = run_bot_container(bot_id, env_vars, start_command)
    return run_success, f"Restarted: {run_msg}"


def get_bot_logs(bot_id: int, tail: int = 200) -> Tuple[bool, str]:
    """Get logs from a bot container."""
    if not docker_client:
        return False, "Docker client not available"

    container_name = get_container_name(bot_id)

    try:
        container = docker_client.containers.get(container_name)
        logs = container.logs(tail=tail, timestamps=True).decode('utf-8')
        return True, logs
    except NotFound:
        return False, f"Container {container_name} not found"
    except Exception as e:
        return False, f"Failed to get logs: {str(e)}"


def clone_or_pull_repo(repo_url: str, code_path: str) -> Tuple[bool, str]:
    """Clone a Git repository or pull if it already exists."""
    try:
        if os.path.exists(code_path) and os.path.isdir(os.path.join(code_path, ".git")):
            # Pull latest changes
            result = subprocess.run(
                ["git", "pull"],
                cwd=code_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                return True, f"Successfully pulled latest changes:\n{result.stdout}"
            else:
                return False, f"Git pull failed:\n{result.stderr}"
        else:
            # Clone repository
            # Create parent directory if needed
            os.makedirs(os.path.dirname(code_path), exist_ok=True)

            result = subprocess.run(
                ["git", "clone", repo_url, code_path],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                return True, f"Successfully cloned repository:\n{result.stdout}"
            else:
                return False, f"Git clone failed:\n{result.stderr}"

    except subprocess.TimeoutExpired:
        return False, "Git operation timed out"
    except Exception as e:
        return False, f"Git operation failed: {str(e)}"
