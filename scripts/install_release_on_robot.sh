#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 <archive.tar.gz> <release_name> <commit> <expected_sha256>" >&2
}

if [ "$#" -ne 4 ]; then
  usage
  exit 2
fi

archive_path="$1"
release_name="$2"
release_commit="$3"
expected_sha256="${4,,}"
base_ws="${DG_BASE_WS:-/home/nvidia/ros2_DL}"

[[ "${release_name}" =~ ^dg202611_ws_[A-Za-z0-9._-]+$ ]] || {
  echo "Invalid release name: ${release_name}" >&2
  exit 2
}
[[ "${release_commit}" =~ ^[0-9a-f]{7,40}$ ]] || {
  echo "Invalid commit id: ${release_commit}" >&2
  exit 2
}
[[ "${expected_sha256}" =~ ^[0-9a-f]{64}$ ]] || {
  echo "Invalid SHA256: ${expected_sha256}" >&2
  exit 2
}

archive_path="$(readlink -f "${archive_path}")"
release_dir="/home/nvidia/${release_name}"

if [ ! -f "${archive_path}" ]; then
  echo "Release archive is missing: ${archive_path}" >&2
  exit 2
fi
if [ -e "${release_dir}" ]; then
  echo "Refusing to overwrite existing release directory: ${release_dir}" >&2
  exit 3
fi
if [ ! -f "${base_ws}/install/setup.bash" ]; then
  echo "Robot base workspace is not built: ${base_ws}" >&2
  exit 2
fi

actual_sha256="$(sha256sum "${archive_path}" | awk '{print tolower($1)}')"
if [ "${actual_sha256}" != "${expected_sha256}" ]; then
  echo "Archive SHA256 mismatch" >&2
  echo "expected=${expected_sha256}" >&2
  echo "actual=${actual_sha256}" >&2
  exit 4
fi

mkdir "${release_dir}"
tar -xzf "${archive_path}" -C "${release_dir}"
for required in \
  scripts/run_dg202611_preflight.sh \
  scripts/activate_dg_release.sh \
  scripts/run_dg_integration.sh \
  scripts/run_dg_inspection.sh \
  scripts/run_dg_models_service.sh \
  scripts/install_dg_models_service.sh \
  scripts/run_real_robot_capture.sh \
  src/ylhb_base/CMakeLists.txt; do
  if [ ! -f "${release_dir}/${required}" ]; then
    echo "Release is incomplete; missing ${required}" >&2
    exit 5
  fi
done

cd "${release_dir}"
export DG_BASE_WS="${base_ws}"
set -o pipefail
./scripts/run_dg202611_preflight.sh 2>&1 | tee deploy_preflight.log

deployed_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 - "${release_dir}" "${release_commit}" "${actual_sha256}" "${deployed_utc}" "${base_ws}" <<'PY'
import json
from pathlib import Path
import sys

release_dir, commit, archive_sha256, deployed_utc, base_workspace = sys.argv[1:]
payload = {
    "schema_version": 1,
    "release_dir": release_dir,
    "commit": commit,
    "archive_sha256": archive_sha256,
    "deployed_utc": deployed_utc,
    "base_workspace": base_workspace,
    "base_workspace_modified": False,
    "motion_test_executed": False,
    "preflight_log": "deploy_preflight.log",
}
(Path(release_dir) / "DEPLOYMENT_RECORD.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY

find . -type f \
  -not -path './build/*' \
  -not -path './install/*' \
  -not -path './log/*' \
  -not -name 'DEPLOYED_SOURCE_MANIFEST.sha256' \
  -print0 | sort -z | xargs -0 sha256sum > DEPLOYED_SOURCE_MANIFEST.sha256

echo "DEPLOY_READY=${release_dir}"
echo "COMMIT=${release_commit}"
echo "ARCHIVE_SHA256=${actual_sha256}"
echo "No motion test was executed."
