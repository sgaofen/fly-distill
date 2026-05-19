#!/usr/bin/env bash
# Cut a fly-distill release: build 3 tarballs + push to GitHub release.
#
# Usage:
#   bash src/cut_release.sh v1.4  "fly-distill v1.4 — r5/r6 dual coords + dedup + QTL workflow"
#
# Requires: gh CLI authenticated, atlas.db + embeddings.npz + output/genes/ present.

set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "usage: $0 <version-tag> [<release-title>]" >&2
  exit 2
fi

TAG="$1"
TITLE="${2:-fly-distill ${TAG}}"
REPO="sgaofen/fly-distill"

# Sanity: must be at repo root
[ -f "tools/atlas.db" ] || { echo "no tools/atlas.db; cd to repo root first" >&2; exit 1; }
[ -f "tools/embeddings.npz" ] || { echo "no tools/embeddings.npz" >&2; exit 1; }
[ -d "output/genes" ] || { echo "no output/genes/ dir" >&2; exit 1; }

# Verify gene count is the expected 14019 (catch a partial build)
N=$(ls output/genes/FBgn*.json 2>/dev/null | wc -l | xargs)
if [ "$N" -lt 14000 ]; then
  echo "WARNING: only $N canonical JSONs found (expected ~14019). Continue? [y/N]"
  read -r ans
  [ "$ans" = "y" ] || exit 1
fi

mkdir -p release
ATLAS_TGZ="release/fly-distill-atlas-db-${TAG}.tar.gz"
CANON_TGZ="release/fly-distill-canonicals-${TAG}.tar.gz"
EMBED_TGZ="release/fly-distill-embeddings-${TAG}.tar.gz"

echo "=== building tarballs ==="
echo "  atlas-db..."
( cd tools && tar -czf "../${ATLAS_TGZ}" atlas.db )
echo "    $(du -h "${ATLAS_TGZ}" | cut -f1)"

echo "  canonicals (${N} files)..."
( cd output && tar -czf "../${CANON_TGZ}" genes )
echo "    $(du -h "${CANON_TGZ}" | cut -f1)"

echo "  embeddings..."
( cd tools && tar -czf "../${EMBED_TGZ}" embeddings.npz )
echo "    $(du -h "${EMBED_TGZ}" | cut -f1)"

echo ""
echo "=== creating GitHub release ${TAG} on ${REPO} ==="

# Notes body — concise; full details in commit log
NOTES_FILE=$(mktemp)
cat > "${NOTES_FILE}" <<EOF
fly-distill **${TAG}** release.

What's in this release:

- **\`fly-distill-atlas-db-${TAG}.tar.gz\`** — SQLite atlas with all 14,019 fly canonical entries, bullets, refs, orthologs, diseases, FTS5 index, **r5 AND r6 chromosome coordinates** (FB2014_01 + FB2026_01 gene_map_table) for QTL fine-mapping workflows.

- **\`fly-distill-canonicals-${TAG}.tar.gz\`** — Raw per-gene JSON ("output/genes/FBgn*.json"). Source-cited evidence with verbatim FlyBase + paper-abstract spans, cross-species MGI mouse + HPO human phenotype context (deduped).

- **\`fly-distill-embeddings-${TAG}.tar.gz\`** — Dense Gemini gemini-embedding-2 vectors (N × 3072 float32), L2-normalized, with cross-species ortholog context **guaranteed-present** in every vector (cs-block reordered ahead of bullet tail-truncation per Codex re-audit feedback).

Quick start:

\`\`\`bash
gh release download ${TAG} -R ${REPO} -p '*.tar.gz' --dir release
tar -xzf release/fly-distill-atlas-db-${TAG}.tar.gz     -C tools/
tar -xzf release/fly-distill-embeddings-${TAG}.tar.gz   -C tools/
tar -xzf release/fly-distill-canonicals-${TAG}.tar.gz   -C output/
echo "GEMINI_EMBEDDING_API_KEY=AIza..." > .env
cd tools && python -m flyatlas.cli serve
\`\`\`

Bug fixes / cleanups since v1.3:
- 121 duplicate ortholog rows removed (NULL entrez_id no longer fools dedup)
- 188 duplicate disease links removed
- 4 looped duplicate bullets in FBgn0036274 removed
- 14 ortholog_inference bullet prefixes repaired (mouse|human → mouse or human based on cited term ID)
- Cross-species context block reordered in embed text so it's never truncated
- FBgn lookup case-insensitive
- FTS5 malformed-query handler (no more 500s)
- Web UI tissue filter now works in semantic mode
- search.html XSS via FlyBase text closed
- .env parser handles BOM/quotes/export/comments + os.environ fallback

New (QTL workflow): per-FBgn r5 + r6 coordinates from FlyBase authoritative
gene_map_table, \`qtl-rank\` CLI subcommand, \`qtl-overlap\` cross-QTL
detector, auto-generated \`output/qtl_report.md\` covering Long's 24-QTL
candidate scoring.
EOF

# Check if release exists; if so, upload new assets; if not, create
if gh release view "${TAG}" -R "${REPO}" >/dev/null 2>&1; then
  echo "release ${TAG} exists, uploading assets..."
  gh release upload "${TAG}" -R "${REPO}" --clobber \
    "${ATLAS_TGZ}" "${CANON_TGZ}" "${EMBED_TGZ}"
else
  echo "creating new release..."
  gh release create "${TAG}" -R "${REPO}" \
    --title "${TITLE}" \
    --notes-file "${NOTES_FILE}" \
    "${ATLAS_TGZ}" "${CANON_TGZ}" "${EMBED_TGZ}"
fi

rm -f "${NOTES_FILE}"

echo ""
echo "=== done ==="
gh release view "${TAG}" -R "${REPO}" | head -10
echo ""
echo "Release URL: https://github.com/${REPO}/releases/tag/${TAG}"
