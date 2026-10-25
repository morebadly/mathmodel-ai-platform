#!/usr/bin/env python3
"""Read-only existing-host inventory. Do not print environment or credentials."""
import glob
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import socket
import ssl
import subprocess


def command(argv, timeout=10, limit=10000):
    try:
        result = subprocess.run(argv, text=True, capture_output=True, timeout=timeout)
        return {"exit_code": result.returncode, "stdout": result.stdout[:limit]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"error": type(exc).__name__}


def main():
    report = {"mode": "read-only", "schema": 1}
    release = {}
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            key, _, value = line.partition("=")
            if key in {"NAME", "VERSION", "ID", "VERSION_ID"}:
                release[key] = value.strip('"')
    except OSError:
        pass
    report["os"] = release
    report["architecture"] = command(["uname", "-m"])
    report["uptime"] = command(["uptime"])
    report["memory_mib"] = command(["free", "-m"])
    report["swap"] = command(["swapon", "--show", "--bytes"])
    report["disks"] = {}
    for directory in ["/", "/www", "/opt", "/var/lib/docker"]:
        if os.path.exists(directory):
            total, used, free = shutil.disk_usage(directory)
            report["disks"][directory] = {"total": total, "used": used, "free": free}
    # comm deliberately excludes arguments and environment that could contain secrets.
    report["top_processes"] = command(
        ["ps", "-eo", "comm,rss,pcpu", "--sort=-rss"], limit=3500)
    report["tcp_listeners"] = command(["ss", "-lntp"], limit=10000)
    report["running_services"] = command(
        ["systemctl", "list-units", "--type=service", "--state=running", "--no-pager", "--plain"],
        limit=10000)
    report["selinux"] = command(["getenforce"])
    report["docker_installed"] = bool(shutil.which("docker"))
    if report["docker_installed"]:
        report["docker_version"] = command(["docker", "version", "--format", "{{.Server.Version}}"])
        report["docker_compose"] = command(["docker", "compose", "version"])
        report["containers"] = command(
            ["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}"])
        report["docker_space"] = command(["docker", "system", "df"])
    report["site_summaries"] = []
    directive = re.compile(r"^\s*(server_name|listen|root|ServerName|DocumentRoot)\s+(.+?);?\s*$")
    paths = glob.glob("/www/server/panel/vhost/nginx/*.conf")
    paths += glob.glob("/www/server/panel/vhost/apache/*.conf")
    for name in sorted(paths)[:100]:
        try:
            settings = []
            for line in Path(name).read_text(errors="replace").splitlines():
                match = directive.match(line)
                if match:
                    settings.append({"directive": match[1], "value": match[2][:300]})
            report["site_summaries"].append({"file": name, "settings": settings})
        except OSError:
            report["site_summaries"].append({"file": name, "error": "unreadable"})
    report["webroot_directories"] = []
    try:
        for child in Path("/www/wwwroot").iterdir():
            report["webroot_directories"].append({"name": child.name, "directory": child.is_dir()})
    except OSError:
        pass
    report["https_connectivity"] = {}
    for host, path in [("registry-1.docker.io", "/v2/"), ("deb.debian.org", "/debian/"), ("pypi.org", "/simple/")]:
        connection = http.client.HTTPSConnection(host, timeout=7, context=ssl.create_default_context())
        try:
            connection.request("HEAD", path)
            response = connection.getresponse()
            report["https_connectivity"][host] = {"status": response.status}
        except (OSError, http.client.HTTPException) as exc:
            report["https_connectivity"][host] = {"error": type(exc).__name__}
        finally:
            connection.close()
    report["smtp_connectivity"] = {}
    for port in [465, 587]:
        try:
            with socket.create_connection(("smtp.gmail.com", port), timeout=5):
                report["smtp_connectivity"][str(port)] = "tcp_connected_only_no_auth"
        except OSError as exc:
            report["smtp_connectivity"][str(port)] = type(exc).__name__
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
