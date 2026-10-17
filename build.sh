#!/usr/bin/env sh
set -eu

# Build the React client before Vercel packages main.py as the FastAPI function.
cd frontend
pnpm install --frozen-lockfile
pnpm run build
