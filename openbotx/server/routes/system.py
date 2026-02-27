import json
import os
import platform
import shutil
import subprocess

from fastapi import APIRouter

from openbotx.version import __version__

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "version": __version__}


@router.get("/version")
async def version():
    return {"version": __version__}


@router.get("/system/info")
async def system_info():
    return {
        "os": _get_os_info(),
        "cpu": _get_cpu_info(),
        "memory": _get_memory_info(),
        "disk": _get_disk_info(),
        "gpu": _get_gpu_info(),
        "python": platform.python_version(),
        "version": __version__,
    }


def _get_os_info() -> dict:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
    }


def _get_cpu_info() -> dict:
    processor = _read_cpu_name() or platform.processor() or "Unknown"
    return {
        "processor": processor,
        "cores": os.cpu_count() or 0,
    }


def _read_cpu_name() -> str | None:
    system = platform.system()
    try:
        if system == "Linux":
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name"):
                        return line.split(":", 1)[1].strip()
        elif system == "Darwin":
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
    except Exception:
        pass
    return None


def _get_memory_info() -> dict:
    total_bytes = _read_total_memory()
    return {
        "total_gb": round(total_bytes / (1024**3), 1) if total_bytes else None,
    }


def _read_total_memory() -> int | None:
    system = platform.system()
    try:
        if system == "Darwin":
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
        elif system == "Linux":
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal"):
                        kb = int(line.split()[1])
                        return kb * 1024
        elif system == "Windows":
            result = subprocess.run(
                ["wmic", "ComputerSystem", "get", "TotalPhysicalMemory", "/value"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if "TotalPhysicalMemory" in line:
                        return int(line.split("=")[1])
    except Exception:
        pass
    return None


def _get_disk_info() -> dict:
    try:
        usage = shutil.disk_usage("/")
        total_gb = usage.total / (1024**3)
        used_gb = usage.used / (1024**3)
        free_gb = usage.free / (1024**3)
        percent = (usage.used / usage.total) * 100 if usage.total else 0
        return {
            "total_gb": round(total_gb, 1),
            "used_gb": round(used_gb, 1),
            "free_gb": round(free_gb, 1),
            "percent": round(percent, 1),
        }
    except Exception:
        return {"total_gb": None, "used_gb": None, "free_gb": None, "percent": None}


def _get_gpu_info() -> list[dict]:
    system = platform.system()
    gpus = []
    try:
        if system == "Darwin":
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType", "-json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                for gpu in data.get("SPDisplaysDataType", []):
                    entry = {"name": gpu.get("sppci_model", "Unknown")}
                    if gpu.get("sppci_cores"):
                        entry["cores"] = int(gpu["sppci_cores"])
                    vendor_raw = gpu.get("spdisplays_vendor", "")
                    if vendor_raw:
                        entry["vendor"] = vendor_raw.replace("sppci_vendor_", "")
                    metal = gpu.get("spdisplays_mtlgpufamilysupport", "")
                    if metal:
                        entry["metal"] = metal.replace("spdisplays_", "").capitalize()
                    gpus.append(entry)
        elif system == "Linux":
            result = subprocess.run(
                ["lspci"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    lower = line.lower()
                    if "vga" in lower or "3d" in lower or "display" in lower:
                        parts = line.split(": ", 1)
                        name = parts[1] if len(parts) > 1 else line
                        gpus.append({"name": name})
        elif system == "Windows":
            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "Name", "/value"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if "Name=" in line:
                        gpus.append({"name": line.split("=", 1)[1].strip()})
    except Exception:
        pass
    return gpus
