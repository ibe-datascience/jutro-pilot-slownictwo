#!/bin/bash
# Plain-text Polish corpus -> TermoPL term list (C-value), capped at MAX_LEN words per term.
#
#   ./run_termopl.sh TXT_DIR WORK_DIR OUT_TSV [MAX_LEN=4] [CONTRAST(.trm or exported .txt)]
#
# 1. Stanza tags every TXT_DIR/*.txt into WORK_DIR/conllu/*.conllu (lemmas checked against Morfeusz2).
# 2. TermoPL 8.1.1 runs in batch mode on WORK_DIR/conllu (grammar-template method, NPMI3, default
#    stop words / compound prepositions / common terms) -> WORK_DIR/terms_all.tsv and WORK_DIR/terms.trm
# 3. TermoPL has no batch option for maximum term length, so rows with length > MAX_LEN are dropped
#    here and a header line is added -> OUT_TSV
#
# TermoPL must be started from its own directory (libjmorfeusz.dylib -> libmorfeusz2.dylib is resolved
# relative to the current directory); it exits with status 0 even when that fails, so stderr is checked.
set -euo pipefail

TXT_DIR=$(cd "$1" && pwd)
mkdir -p "$2"
WORK_DIR=$(cd "$2" && pwd)
mkdir -p "$(dirname "$3")"
OUT_TSV=$(cd "$(dirname "$3")" && pwd)/$(basename "$3")
MAX_LEN=${4:-4}
CONTRAST=${5:-}

HERE=$(cd "$(dirname "$0")" && pwd)
PROJECT=$(cd "$HERE/../../.." && pwd)
PYTHON="$PROJECT/.venv/bin/python"
APP="$HERE/TermoPL_Mac_OS_X"

rm -rf "$WORK_DIR/conllu"
"$PYTHON" "$HERE/txt2conllu.py" --no-depparse --morfeusz-lemmas "$TXT_DIR" "$WORK_DIR/conllu" 2> "$WORK_DIR/tagging.log"

if [ -n "$CONTRAST" ]; then
  CONTRAST=$(cd "$(dirname "$CONTRAST")" && pwd)/$(basename "$CONTRAST")
  COMP=(-comp "$CONTRAST" -cc ll)
  SAVE="# rank sf bf cvalue comp length freq_s freq_in context"
  HEADER="nr\trank\tsimplified_form\tbase_form\tcvalue\tcomp_ll\tlength\tfreq_s\tfreq_in\tcontexts"
  LEN_COL=7
else
  COMP=()
  SAVE="# rank sf bf cvalue length freq_s freq_in context"
  HEADER="nr\trank\tsimplified_form\tbase_form\tcvalue\tlength\tfreq_s\tfreq_in\tcontexts"
  LEN_COL=6
fi

rm -f "$WORK_DIR/terms_all.tsv"
(
  cd "$APP"
  java -Djava.awt.headless=true -Xmx1500M -jar TermoPL.jar \
    -SW -CP -CT -method gt -srch npmi3 -cntx 1 ${COMP[@]+"${COMP[@]}"} \
    -save "$SAVE" \
    -out "$WORK_DIR/terms.trm" -exp "$WORK_DIR/terms_all.tsv" \
    "$WORK_DIR/conllu"
) > "$WORK_DIR/termopl.log" 2>&1

if grep -q -E "Exception|Error|not selected|does not exist" "$WORK_DIR/termopl.log" || [ ! -s "$WORK_DIR/terms_all.tsv" ]; then
  echo "TermoPL failed, see $WORK_DIR/termopl.log" >&2
  exit 1
fi

{
  printf "$HEADER\n"
  awk -F'\t' -v OFS='\t' -v c="$LEN_COL" -v m="$MAX_LEN" \
    '$c <= m { sub(/^\[/, "", $4); sub(/\]$/, "", $4); print }' "$WORK_DIR/terms_all.tsv"
} > "$OUT_TSV"

echo "all terms: $(wc -l < "$WORK_DIR/terms_all.tsv" | tr -d ' ')  kept (length <= $MAX_LEN): $(($(wc -l < "$OUT_TSV") - 1))  -> $OUT_TSV"
