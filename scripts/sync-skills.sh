#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="${ROOT_DIR}/.codex/skills"
TARGET_DIR="${ROOT_DIR}/skills"

if [[ ! -d "${ROOT_DIR}/.codex" ]]; then
  echo "错误：项目根目录未找到 .codex：${ROOT_DIR}" >&2
  exit 1
fi

if [[ ! -d "${SOURCE_DIR}" ]]; then
  echo "错误：未找到源 skill 目录：${SOURCE_DIR}" >&2
  exit 1
fi

mkdir -p "${TARGET_DIR}"

rsync -a --delete \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  "${SOURCE_DIR}/" \
  "${TARGET_DIR}/"

echo "已同步 ${SOURCE_DIR} -> ${TARGET_DIR}"
