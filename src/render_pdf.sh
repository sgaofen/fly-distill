#!/usr/bin/env bash
# Render a markdown file to a typographically-clean PDF via pandoc → HTML →
# Chrome headless print. No LaTeX required.
#
# Usage:
#   bash src/render_pdf.sh output/qtl_findings_for_long.md
#   bash src/render_pdf.sh output/qtl_findings_for_long.md output/qtl_findings_for_long.pdf

set -euo pipefail

MD="${1:?usage: $0 <input.md> [output.pdf]}"
PDF="${2:-${MD%.md}.pdf}"
TMPHTML="${PDF%.pdf}.html"

CSS_FILE=$(mktemp -t flyatlas_pdf.XXXX.css)
cat > "${CSS_FILE}" <<'EOF'
@page {
  size: A4;
  margin: 1.6cm 1.6cm 1.6cm 1.6cm;
  @bottom-center {
    content: counter(page) " / " counter(pages);
    font-size: 10px;
    color: #888;
  }
}
* { box-sizing: border-box; }
body {
  font-family: -apple-system, "Helvetica Neue", "Helvetica", "Arial", "PingFang SC", "Microsoft YaHei", sans-serif;
  font-size: 10.5pt;
  line-height: 1.45;
  color: #222;
  max-width: 100%;
  margin: 0;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
h1 {
  font-size: 18pt; font-weight: 600; color: #1a1a1a;
  border-bottom: 2px solid #d9d9d9; padding-bottom: 0.3em;
  margin: 0 0 0.6em 0;
}
h2 {
  font-size: 13pt; font-weight: 600; color: #2c2c2c;
  margin-top: 1.6em; margin-bottom: 0.5em;
  border-bottom: 1px solid #e0e0e0; padding-bottom: 0.2em;
}
h3 {
  font-size: 11.5pt; font-weight: 600; color: #333;
  margin-top: 1.2em; margin-bottom: 0.4em;
}
p { margin: 0.4em 0 0.7em 0; }
strong { color: #111; font-weight: 600; }
em { color: #444; }
code, .num {
  font-family: "SF Mono", "Menlo", "Consolas", "Monaco", monospace;
  font-size: 9.5pt;
  background: #f3f3f3; padding: 0 0.25em; border-radius: 2px;
}
pre { background: #f5f5f5; padding: 0.6em; border-radius: 4px; font-size: 9pt; overflow-x: auto; }
hr { border: none; border-top: 1px solid #d9d9d9; margin: 1.6em 0; }
table {
  border-collapse: collapse; width: 100%;
  margin: 0.6em 0 1em 0;
  font-size: 9.5pt;
}
th, td {
  border-bottom: 1px solid #e0e0e0;
  padding: 0.32em 0.5em;
  text-align: left;
  vertical-align: top;
}
th {
  background: #f5f5f5;
  font-weight: 600;
  color: #2c2c2c;
  font-size: 9pt;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}
table tr:nth-child(even) td { background: #fafafa; }
td:has(+ td.num), th + th.num { text-align: right; }
ul, ol { margin: 0.4em 0 0.7em 1.2em; padding: 0; }
li { margin: 0.2em 0; }
a { color: #1a5fb4; text-decoration: none; border-bottom: 1px dotted #1a5fb4; }
blockquote { border-left: 3px solid #ccc; margin: 0.8em 0; padding: 0.1em 1em; color: #555; }
/* keep big section blocks together */
h2, h3 { page-break-after: avoid; }
table { page-break-inside: avoid; }

/* per-QTL section: hard horizontal divider + page break inside avoid */
.qtl-section {
  border-top: 3px solid #2c2c2c;
  padding-top: 1.2em;
  margin-top: 2em;
}
.qtl-section:first-of-type {
  border-top: none;
  padding-top: 0;
  margin-top: 0;
}

/* query-block: paired old/new highlights */
.query-block {
  background: #f7f7f7;
  border-left: 4px solid #9ca3af;
  padding: 0.5em 0.9em;
  margin: 0.8em 0;
  font-size: 9.8pt;
}
.query-block blockquote {
  margin: 0.2em 0 0.5em 0;
  padding: 0;
  border: none;
  font-style: italic;
  color: #333;
}

/* rising-gene list: each gene gets its own breathable block */
.rise-list {
  margin: 0.4em 0;
}
.gene-entry {
  margin: 0.5em 0;
  padding: 0.5em 0.7em;
  background: #f0fdf4;
  border-left: 3px solid #16a34a;
  border-radius: 0 4px 4px 0;
  page-break-inside: avoid;
}
.gene-head {
  font-size: 10pt;
  margin-bottom: 0.25em;
}
.gene-head strong {
  color: #15803d;
  font-size: 10.5pt;
}
.gene-head code {
  font-size: 8.5pt;
  background: transparent;
  color: #6b7280;
}
.gene-bio {
  font-size: 9.5pt;
  color: #1f2937;
  line-height: 1.4;
}
EOF

echo "▸ pandoc → HTML"
pandoc "${MD}" \
  -f markdown+pipe_tables+yaml_metadata_block+raw_html \
  -t html5 \
  --standalone \
  --css="${CSS_FILE}" \
  --metadata title="fly-distill × QTL atlas — findings" \
  -o "${TMPHTML}"

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
if [ ! -x "${CHROME}" ]; then
  echo "Chrome not found at ${CHROME}; PDF step skipped, HTML at ${TMPHTML}"
  exit 0
fi

echo "▸ Chrome headless → PDF"
# Resolve to absolute path so file:// URL works
ABS_HTML="$(cd "$(dirname "${TMPHTML}")" && pwd)/$(basename "${TMPHTML}")"
USER_DIR=$(mktemp -d -t chrome-pdf.XXXX)
"${CHROME}" \
  --headless=new \
  --disable-gpu \
  --no-sandbox \
  --user-data-dir="${USER_DIR}" \
  --no-pdf-header-footer \
  --virtual-time-budget=20000 \
  --print-to-pdf="${PDF}" \
  "file://${ABS_HTML}" 2>&1 | grep -v "DevTools listening\|GPU\|FontConfig\|Network\|^$" || true
rm -rf "${USER_DIR}"

rm -f "${CSS_FILE}"
ls -lh "${PDF}"
echo "done."
