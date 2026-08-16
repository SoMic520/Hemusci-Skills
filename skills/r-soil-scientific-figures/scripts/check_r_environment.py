#!/usr/bin/env python3
"""Check or install cross-platform R and profile-scoped plotting dependencies."""

from __future__ import annotations

import argparse
import glob
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


CRAN_REPO = "https://cloud.r-project.org"
CRAN_R_MAC = "https://cran.r-project.org/bin/macosx/"
CRAN_R_WINDOWS = "https://cran.r-project.org/bin/windows/base/"

PROFILES: dict[str, dict[str, list[str]]] = {
    "core": {
        "cran": [
            "ggplot2",
            "ggtext",
            "jsonlite",
            "openxlsx",
            "ragg",
            "readxl",
            "scales",
            "systemfonts",
            "sysfonts",
            "showtext",
            "svglite",
        ],
        "bioc": [],
    },
    "publication": {
        "cran": ["colorspace", "viridisLite", "patchwork", "dplyr", "tidyr", "broom"],
        "bioc": [],
    },
    "soil": {
        "cran": ["aqp", "soiltexture", "soilDB", "sharpshootR", "mpspline2"],
        "bioc": [],
    },
    "ecology": {"cran": ["vegan", "permute"], "bioc": []},
    "spatial": {"cran": ["sf", "terra", "stars", "gstat", "tmap"], "bioc": []},
    "microbiome": {
        "cran": [],
        "bioc": ["phyloseq", "microViz", "ComplexHeatmap", "ggtree"],
    },
}


def command_for_r_install(
    system: str, *, allow_unresolved_executable: bool = False
) -> tuple[list[str] | None, str]:
    if system == "Darwin":
        brew = shutil.which("brew")
        if brew or allow_unresolved_executable:
            return [brew or "brew", "install", "r"], "Homebrew formula (official Homebrew registry)"
        return None, f"Install the signed CRAN package from {CRAN_R_MAC}"
    if system == "Windows":
        winget = shutil.which("winget")
        if winget or allow_unresolved_executable:
            return [
                winget or "winget",
                "install",
                "--id",
                "RProject.R",
                "--exact",
                "--accept-source-agreements",
                "--accept-package-agreements",
            ], "Windows Package Manager manifest RProject.R"
        return None, f"Install the signed CRAN executable from {CRAN_R_WINDOWS}"
    return None, "Automatic R installation is limited to macOS/Homebrew and Windows/winget"


def find_rscript(system: str | None = None) -> str | None:
    system = system or platform.system()
    if system != platform.system():
        return None
    found = shutil.which("Rscript")
    if found:
        return found
    if system == "Windows":
        candidates = sorted(glob.glob(r"C:\Program Files\R\R-*\bin\Rscript.exe"), reverse=True)
        if candidates:
            return candidates[0]
    if system == "Darwin":
        candidates = [
            "/Library/Frameworks/R.framework/Resources/bin/Rscript",
            "/opt/homebrew/bin/Rscript",
            "/usr/local/bin/Rscript",
        ]
        for candidate in candidates:
            if Path(candidate).is_file():
                return candidate
    return None


def selected_packages(profile_names: list[str]) -> tuple[list[str], list[str]]:
    unknown = sorted(set(profile_names) - PROFILES.keys())
    if unknown:
        raise SystemExit(f"Unknown profiles: {', '.join(unknown)}")
    cran: list[str] = []
    bioc: list[str] = []
    for name in profile_names:
        cran.extend(PROFILES[name]["cran"])
        bioc.extend(PROFILES[name]["bioc"])
    return list(dict.fromkeys(cran)), list(dict.fromkeys(bioc))


def r_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def run_r(rscript: str, expression: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [rscript, "--vanilla", "-e", expression],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=1800,
        check=False,
    )


def install_packages(
    rscript: str, cran: list[str], bioc: list[str], env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    cran_vec = "c(" + ",".join(r_quote(pkg) for pkg in cran) + ")"
    bioc_vec = "c(" + ",".join(r_quote(pkg) for pkg in bioc) + ")"
    expression = f"""
options(repos=c(CRAN={r_quote(CRAN_REPO)}))
cran <- {cran_vec}
bioc <- {bioc_vec}
missing_cran <- cran[!vapply(cran, requireNamespace, logical(1), quietly=TRUE)]
if (length(missing_cran)) install.packages(missing_cran, dependencies=NA)
if (length(bioc)) {{
  if (!requireNamespace("BiocManager", quietly=TRUE)) install.packages("BiocManager", dependencies=NA)
  missing_bioc <- bioc[!vapply(bioc, requireNamespace, logical(1), quietly=TRUE)]
  if (length(missing_bioc)) BiocManager::install(missing_bioc, ask=FALSE, update=FALSE)
}}
"""
    return run_r(rscript, expression, env)


def inspect_r(rscript: str, packages: list[str], env: dict[str, str]) -> dict[str, object]:
    package_vec = "c(" + ",".join(r_quote(pkg) for pkg in packages) + ")"
    expression = f"""
pkgs <- {package_vec}
cat("R_VERSION\\t", R.version.string, "\\n", sep="")
cat("R_PLATFORM\\t", R.version$platform, "\\n", sep="")
for (pkg in pkgs) {{
  ok <- requireNamespace(pkg, quietly=TRUE)
  version <- if (ok) as.character(utils::packageVersion(pkg)) else ""
  cat("PACKAGE\\t", pkg, "\\t", ok, "\\t", version, "\\n", sep="")
}}
if (requireNamespace("systemfonts", quietly=TRUE)) {{
  families <- unique(systemfonts::system_fonts()$family)
  for (font in c("Times New Roman", "Songti SC", "STSong", "SimSun", "宋体"))
    cat("FONT\\t", font, "\\t", font %in% families, "\\n", sep="")
}}
"""
    proc = run_r(rscript, expression, env)
    packages_out: dict[str, dict[str, object]] = {}
    fonts: dict[str, bool] = {}
    version = ""
    r_platform = ""
    for line in proc.stdout.splitlines():
        fields = line.split("\t")
        if fields[0] == "R_VERSION" and len(fields) > 1:
            version = fields[1]
        elif fields[0] == "R_PLATFORM" and len(fields) > 1:
            r_platform = fields[1]
        elif fields[0] == "PACKAGE" and len(fields) >= 4:
            packages_out[fields[1]] = {
                "installed": fields[2] == "TRUE",
                "version": fields[3] or None,
            }
        elif fields[0] == "FONT" and len(fields) >= 3:
            fonts[fields[1]] = fields[2] == "TRUE"
    return {
        "command_ok": proc.returncode == 0,
        "version": version,
        "platform": r_platform,
        "packages": packages_out,
        "fonts": fonts,
        "stderr": proc.stderr.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profiles",
        default="core,publication",
        help=f"Comma-separated profiles: {','.join(PROFILES)}",
    )
    parser.add_argument("--install-missing", action="store_true")
    parser.add_argument("--install-r", action="store_true")
    parser.add_argument("--library", type=Path, help="Optional user package library")
    parser.add_argument("--report", type=Path, help="Write JSON report")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--target-system",
        choices=["auto", "Darwin", "Windows", "Linux"],
        default="auto",
        help="Target platform for planning; a non-host platform requires --dry-run",
    )
    args = parser.parse_args()

    profiles = [item.strip() for item in args.profiles.split(",") if item.strip()]
    cran, bioc = selected_packages(profiles)
    host_system = platform.system()
    system = host_system if args.target_system == "auto" else args.target_system
    if system != host_system and not args.dry_run:
        parser.error("A non-host --target-system may only be used with --dry-run")
    rscript = find_rscript(system)
    install_command, install_source = command_for_r_install(
        system, allow_unresolved_executable=args.dry_run
    )
    report: dict[str, object] = {
        "host_system": host_system,
        "target_system": system,
        "machine": platform.machine(),
        "profiles": profiles,
        "rscript": rscript,
        "r_install_source": install_source,
        "r_install_command": install_command,
        "official_r_pages": {"macOS": CRAN_R_MAC, "Windows": CRAN_R_WINDOWS},
        "requested_cran_packages": cran,
        "requested_bioconductor_packages": bioc,
        "actions": [],
    }

    if not rscript and args.install_r:
        if not install_command:
            report["error"] = install_source
        elif args.dry_run:
            report["actions"].append({"dry_run": install_command})
        else:
            proc = subprocess.run(install_command, text=True, timeout=3600, check=False)
            report["actions"].append({"install_r_exit_code": proc.returncode})
            rscript = find_rscript(system)
            report["rscript"] = rscript

    if not rscript and args.dry_run:
        report["status"] = "PLAN"
        report["runtime_certified"] = False
        report["note"] = "Dry-run validates command and package planning only."
        rendered = json.dumps(report, ensure_ascii=False, indent=2)
        print(rendered)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(rendered + "\n", encoding="utf-8")
        return 0

    if not rscript:
        report.setdefault("error", "Rscript was not found")
        rendered = json.dumps(report, ensure_ascii=False, indent=2)
        print(rendered)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(rendered + "\n", encoding="utf-8")
        return 2

    env = os.environ.copy()
    if args.library:
        library = args.library.expanduser().resolve()
        library.mkdir(parents=True, exist_ok=True)
        env["R_LIBS_USER"] = str(library)
        report["library"] = str(library)

    before = inspect_r(rscript, cran + bioc, env)
    missing_before = [pkg for pkg, info in before["packages"].items() if not info["installed"]]
    report["before"] = before
    report["missing_before"] = missing_before

    if missing_before and args.install_missing:
        if args.dry_run:
            report["actions"].append({"dry_run_install_packages": missing_before})
        else:
            proc = install_packages(rscript, cran, bioc, env)
            report["actions"].append(
                {
                    "install_packages_exit_code": proc.returncode,
                    "stdout_tail": proc.stdout[-4000:],
                    "stderr_tail": proc.stderr[-4000:],
                }
            )

    after = inspect_r(rscript, cran + bioc, env)
    missing_after = [pkg for pkg, info in after["packages"].items() if not info["installed"]]
    report["after"] = after
    report["missing_after"] = missing_after
    report["status"] = "PASS" if after["command_ok"] and not missing_after else "FAIL"
    report["windows_note"] = "Command construction is tested cross-platform; execute on a real Windows host for runtime certification."

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
