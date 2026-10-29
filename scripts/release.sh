#!/usr/bin/env bash
# Bump the version everywhere it lives, then tag. Usage: scripts/release.sh 1.2.0
# Write the CHANGELOG.md entry first; pushing the tag runs .github/workflows/release.yml.
set -euo pipefail
v="${1:?usage: scripts/release.sh X.Y.Z}"
cd "$(dirname "$0")/.."
grep -q "^## \[\?$v" CHANGELOG.md || { echo "add a '## $v' entry to CHANGELOG.md first" >&2; exit 1; }
sed -i.bak -E "s/(\"version\": )\"[^\"]+\"/\1\"$v\"/" .claude-plugin/plugin.json && rm .claude-plugin/plugin.json.bak
sed -i.bak -E "s/^(  version: )\"[^\"]+\"/\1\"$v\"/" skills/demo-presentation/SKILL.md && rm skills/demo-presentation/SKILL.md.bak
python3 scripts/check.py --tag "v$v"
git commit -qam "$v" && git tag -a "v$v" -m "v$v"
echo "tagged v$v: git push origin main v$v"
