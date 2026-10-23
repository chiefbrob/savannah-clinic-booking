#!/usr/bin/env python3
"""One-time provisioning of the production host (Ubuntu 24.04).

Run as root on the server, from the deployed checkout:

    sudo /srv/clinic-booking/deploy/provision.py

It is idempotent: re-running it repairs rather than duplicates. It creates:

* a system user ``clinic`` (no login shell),
* a PostgreSQL role and database owned by that user,
* a virtualenv with the production requirements,
* the systemd unit.

It deliberately does *not* touch the other services on this host (muok,
grams, voice, clutchbagskenya) or their nginx server blocks.
"""

from __future__ import annotations

import os
import pathlib
import secrets
import shlex
import shutil
import subprocess
import sys

APP_DIR = pathlib.Path("/srv/clinic-booking")
SERVICE_USER = "clinic"
DB_NAME = "clinic"
DOMAIN = "clinic.dabotap.com"


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(shlex.quote(arg) for arg in args))
    return subprocess.run(args, check=check, text=True, capture_output=True)


def psql(sql: str) -> str:
    """Run a query as the postgres superuser, returning trimmed stdout."""
    result = run("su", "-", "postgres", "-c", f"psql -tAc {shlex.quote(sql)}", check=False)
    return result.stdout.strip()


def main() -> int:
    if os.geteuid() != 0:
        print("run this as root", file=sys.stderr)
        return 1

    if not APP_DIR.exists():
        print(f"{APP_DIR} does not exist; clone the repo there first", file=sys.stderr)
        return 1

    # 1. System user
    if run("id", "-u", SERVICE_USER, check=False).returncode != 0:
        run("useradd", "--system", "--create-home", "--shell", "/usr/sbin/nologin", SERVICE_USER)

    # 2. PostgreSQL role + database
    password_file = pathlib.Path(f"/root/{SERVICE_USER}-db-password.txt")
    if psql(f"SELECT 1 FROM pg_roles WHERE rolname='{SERVICE_USER}'") != "1":
        password = secrets.token_urlsafe(24)
        psql(f"CREATE ROLE {SERVICE_USER} LOGIN PASSWORD '{password}'")
        password_file.write_text(password + "\n")
        password_file.chmod(0o600)
        print(f"database password written to {password_file}")

    if psql(f"SELECT 1 FROM pg_database WHERE datname='{DB_NAME}'") != "1":
        psql(f"CREATE DATABASE {DB_NAME} OWNER {SERVICE_USER}")

    # 3. Virtualenv + dependencies
    venv = APP_DIR / ".venv"
    if not (venv / "bin" / "python").exists():
        run("python3", "-m", "venv", str(venv))
    run(str(venv / "bin" / "pip"), "install", "--upgrade", "pip", "-q")
    run(str(venv / "bin" / "pip"), "install", "-q", "-r", str(APP_DIR / "requirements.txt"))

    # 4. Environment file (never overwritten, so secrets survive re-provisioning)
    env_file = APP_DIR / ".env"
    if not env_file.exists():
        password = password_file.read_text().strip() if password_file.exists() else ""
        env_file.write_text(
            "ENVIRONMENT=production\n"
            f"DATABASE_URL=postgresql+asyncpg://{SERVICE_USER}:{password}"
            f"@127.0.0.1:5432/{DB_NAME}\n"
            "CLINIC_TIMEZONE=Africa/Nairobi\n"
            "SLOT_MINUTES=30\n"
            "MIN_BOOKING_LEAD_MINUTES=60\n"
            f"CORS_ORIGINS=https://{DOMAIN},https://chiefbrob.github.io\n"
        )
        env_file.chmod(0o600)
        print("wrote", env_file)

    run("chown", "-R", f"{SERVICE_USER}:{SERVICE_USER}", str(APP_DIR))

    # 5. systemd unit
    shutil.copy(APP_DIR / "deploy" / "clinic-booking.service", "/etc/systemd/system/")
    run("systemctl", "daemon-reload")
    run("systemctl", "enable", "clinic-booking.service", check=False)

    # 6. nginx server block
    nginx_site = pathlib.Path("/etc/nginx/sites-available/clinic-booking")
    shutil.copy(APP_DIR / "deploy" / "nginx.conf", nginx_site)
    link = pathlib.Path("/etc/nginx/sites-enabled/clinic-booking")
    if not link.exists():
        link.symlink_to(nginx_site)
    run("nginx", "-t")
    run("systemctl", "reload", "nginx")

    print(
        "\nprovisioned. Remaining steps:\n"
        f"  1. DNS A record for {DOMAIN} -> this host\n"
        f"  2. certbot --nginx -d {DOMAIN} --redirect\n"
        "  3. systemctl restart clinic-booking\n"
        f"  4. seed: sudo -u {SERVICE_USER} bash -c 'set -a; . {env_file}; set +a; "
        f"{venv}/bin/python -m app.seed'\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
