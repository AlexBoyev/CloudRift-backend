import subprocess
import os
import time
import sys
import json
import base64

# --- Path Setup to import 'utils' from parent directory ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from utils.logger import Logger

# --- Configuration ---
PROJECT_ROOT = parent_dir
K8S_DIR = os.path.join(PROJECT_ROOT, "k8s")
TERRAFORM_DIR = os.path.join(PROJECT_ROOT, "terraform", "local")
CONFIG_FILE = os.path.join(PROJECT_ROOT, "driver", "config.json")


class InfrastructureManager:
    def __init__(self):
        self.env = os.environ.copy()
        self.config = self.load_config()
        self.services = self.discover_services()
        self.minikube_ip = None

    def load_config(self):
        """Loads configuration from config.json"""
        if not os.path.exists(CONFIG_FILE):
            Logger.error(f"Config file not found at: {CONFIG_FILE}")
            sys.exit(1)

        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            Logger.error(f"Failed to parse config.json: {e}")
            sys.exit(1)

    def discover_services(self):
        services = []
        for name in os.listdir(PROJECT_ROOT):
            path = os.path.join(PROJECT_ROOT, name)
            if os.path.isdir(path) and os.path.isfile(os.path.join(path, "Dockerfile")):
                services.append(name)
        return services

    def run_cmd(self, cmd, shell=False, capture=True, cwd_override=None, ignore_errors=False):
        """Helper to run shell commands."""
        cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
        Logger.debug(f"Exec: {cmd_str}")

        try:
            result = subprocess.run(
                cmd,
                shell=shell,
                check=True,
                stdout=subprocess.PIPE if capture else None,
                stderr=subprocess.PIPE if capture else None,
                env=self.env,
                cwd=cwd_override or PROJECT_ROOT,
                # --- FIX: Force UTF-8 to prevent Windows Crash ---
                encoding='utf-8',
                errors='replace',
                text=True,
            )
            return result.stdout.strip() if capture else ""
        except subprocess.CalledProcessError as e:
            if ignore_errors:
                return ""
            Logger.error(f"Command failed: {cmd_str}")
            if capture and e.stderr:
                print(e.stderr)
            sys.exit(1)

    # ---------------- Cleanup & Unlock Logic ---------------- #

    def force_unlock_terraform(self):
        """Removes the lock file if it exists."""
        lock_file = os.path.join(TERRAFORM_DIR, ".terraform.tfstate.lock.info")
        if os.path.exists(lock_file):
            Logger.warning(f"Found Terraform Lock File: {lock_file}")
            try:
                os.remove(lock_file)
                Logger.success("Removed Lock File. Terraform is now unlocked.")
            except Exception as e:
                Logger.error(f"Could not remove lock file: {e}")

    def cleanup_resources(self):
        Logger.header("Step 0: Cleaning Up Old Resources")
        Logger.info("Force deleting all deployments, services, and ingress...")

        self.run_cmd(["kubectl", "delete", "deployments,services,ingress,configmaps,secrets,pvc", "--all"],
                     ignore_errors=True)

        # Force delete namespace to reload permissions defined in yaml
        try:
            ns = self.config["ingress"]["namespace"]
            self.run_cmd(["kubectl", "delete", "namespace", ns], ignore_errors=True)
        except KeyError:
            pass

        Logger.info("Waiting 5 seconds for resources to terminate...")
        time.sleep(5)
        Logger.success("Cleanup complete.")

    # ---------------- Standard Logic ---------------- #

    def check_minikube(self):
        Logger.header("Step 1: Checking Infrastructure")
        try:
            result = subprocess.run(["minikube", "status"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0 and "Running" in result.stdout:
                Logger.success("Minikube is running.")
            else:
                Logger.warning("Starting Minikube...")
                subprocess.run(["minikube", "start", "--driver=docker"], check=True)
        except Exception as e:
            Logger.error(f"Minikube check failed: {e}")
            sys.exit(1)

        try:
            ip = subprocess.check_output(["minikube", "ip"], text=True).strip()
            self.minikube_ip = ip
            Logger.info(f"Minikube IP: {ip}")
        except:
            self.minikube_ip = "<minikube-ip>"

    def set_docker_env(self):
        Logger.header("Step 2: Configuring Docker Environment")
        try:
            cmd = ["minikube", "-p", "minikube", "docker-env"]
            if os.name == 'nt':  # Windows
                cmd.extend(["--shell", "powershell"])

            output = subprocess.check_output(cmd, text=True)

            for line in output.splitlines():
                if "export" in line or "$Env:" in line:
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        key = parts[0].replace("export ", "").replace("$Env:", "").strip()
                        val = parts[1].strip().strip('"')
                        self.env[key] = val

            Logger.info(f"Docker pointed to Minikube: {self.env.get('DOCKER_HOST')}")
        except:
            Logger.error("Failed to configure Docker env")

    # --- Generate AND APPLY Secret ---
    def generate_k8s_secret(self):
        Logger.header("Step 3: Generating & Syncing Secrets")
        env_path = os.path.join(PROJECT_ROOT, ".env")
        secret_path = os.path.join(K8S_DIR, "postgres-secret.yaml")

        if not os.path.exists(env_path):
            Logger.warning(f"No .env file found at {env_path}. Skipping Secret generation.")
            return

        Logger.info("Reading .env and generating Kubernetes Secret...")

        env_vars = {}
        try:
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        env_vars[key] = value.strip()
        except Exception as e:
            Logger.error(f"Failed to read .env: {e}")
            return

        # Map .env keys to what our YAML expects
        db_user = env_vars.get("DB_USER") or env_vars.get("POSTGRES_USER", "postgres")
        db_pass = env_vars.get("DB_PASSWORD") or env_vars.get("POSTGRES_PASSWORD", "password")
        db_name = env_vars.get("DB_NAME") or env_vars.get("POSTGRES_DB", "cloudrift")

        secret_yaml = f"""apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
type: Opaque
stringData:
  username: "{db_user}"
  password: "{db_pass}"
  dbname: "{db_name}"
"""
        with open(secret_path, "w") as f:
            f.write(secret_yaml)

        Logger.success(f"Generated {secret_path}")

        # Apply Immediately
        self.run_cmd(["kubectl", "apply", "-f", secret_path])
        Logger.success("Secret applied to Kubernetes cluster.")

    def build_images(self):
        Logger.header("Step 4: Building Service Images (Clean Build)")

        # Helper to delete image from Minikube first
        def clean_and_build(image_name, dockerfile_path, context_path):
            Logger.info(f"Purging old image: {image_name}...")

            # FIX: Use 'docker rmi -f' instead of 'minikube image rm'
            # Since we loaded docker-env, this talks directly to Minikube's daemon.
            self.run_cmd(["docker", "rmi", "-f", image_name], ignore_errors=True, capture=False)

            Logger.info(f"Building new image: {image_name}...")
            self.run_cmd([
                "docker", "build",
                "-t", image_name,
                "-f", dockerfile_path,
                context_path
            ])

        # 1. Build Standard Services
        for service in self.services:
            clean_and_build(
                f"{service}-service:latest",
                f"./{service}/Dockerfile",
                "."
            )

        # 2. Build Database
        if os.path.exists(os.path.join(PROJECT_ROOT, "database", "Dockerfile")):
            clean_and_build(
                "postgres-db:latest",
                "database/Dockerfile",
                "."
            )
        else:
            Logger.warning("database/Dockerfile not found. Skipping DB build.")

        Logger.success("Images built and cache updated.")

    def deploy_k8s(self):
        Logger.header("Step 5: Deploying via Terraform")
        self.run_cmd(["terraform", "init"], cwd_override=TERRAFORM_DIR, capture=False)
        self.run_cmd(["terraform", "apply", "-auto-approve"], cwd_override=TERRAFORM_DIR, capture=False)
        Logger.success("Terraform apply completed.")

    def wait_for_pods(self):
        Logger.header("Step 6: Health Check")
        retries = 0
        while retries < 40:
            output = self.run_cmd(["kubectl", "get", "pods"])
            if "Running" in output and "Error" not in output and "CrashLoop" not in output and "ContainerCreating" not in output:
                if "backend" in output and "postgres" in output:
                    Logger.success("All Pods are RUNNING!")
                    return
            time.sleep(3)
            retries += 1
            if retries % 5 == 0: Logger.debug("Waiting for pods...")
        Logger.warning("Timed out waiting for pods.")

    def open_tunnel(self):
        local_port = self.config["ingress"]["local_port"]
        container_port = self.config["ingress"]["container_port"]
        namespace = self.config["ingress"]["namespace"]
        service = self.config["ingress"]["service_name"]

        Logger.header("Step 8: Opening Access Tunnel")
        Logger.info(f"Starting port-forwarding to Ingress ({service})")
        Logger.info(f"Mapping: localhost:{local_port} -> Container:{container_port}")
        Logger.info(f"Access URL: http://localhost:{local_port}")
        Logger.info("Press Ctrl+C to stop.")

        try:
            subprocess.run([
                "kubectl", "port-forward",
                "-n", namespace,
                f"svc/{service}",
                f"{local_port}:{container_port}"
            ], check=True)
        except KeyboardInterrupt:
            Logger.info("\nGoodbye!")

    def main(self):
        self.force_unlock_terraform()
        self.cleanup_resources()
        self.check_minikube()
        self.set_docker_env()

        self.generate_k8s_secret()
        self.build_images()
        self.deploy_k8s()
        self.wait_for_pods()
        self.open_tunnel()

    def run_existing(self):
        """Starts the application assuming it is already deployed."""
        Logger.header("Quick Start: Connecting to Existing Infrastructure")

        # 1. Ensure minikube is up so we can get the IP/Env
        self.check_minikube()

        # 2. Verify pods are actually there before trying to tunnel
        Logger.info("Verifying cluster health...")
        output = self.run_cmd(["kubectl", "get", "pods"], ignore_errors=True)
        if "backend" not in output or "postgres" not in output:
            Logger.error("Resources not found. Please run a full deploy first.")
            return

        # 3. Open the tunnel
        self.open_tunnel()


if __name__ == "__main__":
    manager = InfrastructureManager()
    # OPTION A: Full Re-Deploy (Current behavior)
    manager.main()

    # OPTION B: Quick Start (Comment out manager.main() and use this to just open the tunnel)
    # manager.run_existing()