#!/bin/zsh
set -euo pipefail

INSTALLER_DIR="${0:A:h}"
REPORT_PATH="${INSTALLER_DIR}/environment-macos.json"
HELPER_PATH="${INSTALLER_DIR}/check_r_environment.py"
if [[ ! -f "${HELPER_PATH}" ]]; then
  SKILL_ROOT="${INSTALLER_DIR:h:h}"
  HELPER_PATH="${SKILL_ROOT}/scripts/check_r_environment.py"
fi

python3 "${HELPER_PATH}" \
  --profiles "${R_FIGURE_PROFILES:-core,publication}" \
  --install-r \
  --install-missing \
  --report "${REPORT_PATH}"

print "R environment check complete: ${REPORT_PATH}"
