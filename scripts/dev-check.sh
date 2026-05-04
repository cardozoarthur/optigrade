#!/usr/bin/env bash
set -euo pipefail

printf "Node: "
node -v
printf "pnpm: "
pnpm -v
printf "Python: "
python3.11 --version
printf "uv: "
uv --version
printf "Rust: "
rustc --version
printf "Cargo: "
cargo --version

