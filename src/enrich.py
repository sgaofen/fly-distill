"""Post-process enrichers — purely deterministic, no LLM calls. Each takes a raw
bullet/bundle and returns structured fields.

Reads (all already on disk):
  - bundle.json (per-gene fetched data)
  - data/flybase_bulk/genes/fbgn_annotation_ID_*.tsv.gz (full synonyms)
  - data/flybase_bulk/orthologs/dmel_human_orthologs_disease_*.tsv.gz (disease OMIM IDs)
"""
import gzip
import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BULK = ROOT / "data" / "flybase_bulk"


# ---- Citation parsing ------------------------------------------------------

FBRF_RE = re.compile(r"FBrf\d{7}")
SECTION_RE = re.compile(
    r"\b(phenotypes_sub|alleles_main_sub|hdm_sub|other_comments_sub|"
    r"summary_genetic_interactions_sub|summary_physical_interactions_sub|"
    r"pathways_sub|gene_class_sub|human_orthologs_sub|mod_orthologs_sub|"
    r"function|auto_summary|CURATOR NOTES)\b"
)
# Curator notes is the model's rephrasing of other_comments_sub
SECTION_ALIAS = {"CURATOR NOTES": "other_comments_sub"}
# Ortholog mention pattern: capitalized human gene symbols inline in evidence
ORTHO_HUMAN_RE = re.compile(r"\b([A-Z][A-Z0-9]{2,9})\b")  # ALL-CAPS human-like
ORTHO_MOUSE_RE = re.compile(r"\b([A-Z][a-z]+[0-9a-zA-Z]*)\b")  # capitalized-mouse-like


def parse_citations(evidence_text: str) -> list:
    """Return ordered list of unified-shape citations {type, value, [label, quote, section_enum]}.
    Every citation has type + value; SQLite ingester writes (cite_type, cite_value) verbatim.
    """
    out = []
    seen = set()
    for m in FBRF_RE.finditer(evidence_text):
        key = ("fbrf", m.group(0))
        if key not in seen:
            out.append({"type": "fbrf", "value": m.group(0), "label": f"{m.group(0)} abstract"})
            seen.add(key)
    for m in SECTION_RE.finditer(evidence_text):
        s = SECTION_ALIAS.get(m.group(1), m.group(1))
        key = ("flybase_section", s)
        if key not in seen:
            out.append({
                "type": "flybase_section",
                "value": s,
                "section_enum": s,
                "label": f"FlyBase {s} curator annotation",
            })
            seen.add(key)
    return out


# ---- Tissue / life-stage / allele parsing ---------------------------------
# Source: FlyBase phenotypes_sub pipe-format. E.g.:
#   "abnormal locomotor rhythm | adult stage | conditional"
#   "decreased fecundity | female | conditional"
#   "abnormal mitotic cell cycle | third instar larval stage"
# Plus allele names like per01, perL, perS, shi[ts1], w1118.

LIFE_STAGE_TERMS = {
    "embryonic stage", "larval stage", "first instar larval stage",
    "second instar larval stage", "third instar larval stage",
    "pupal stage", "adult stage", "aged adult", "late pupal stage",
}
LIFE_STAGE_PATTERNS = [
    re.compile(r"\b(embryo|embryonic)\b"),
    re.compile(r"\b(larv|larval)\b"),
    re.compile(r"\b(pupal|pupae|pupa)\b"),
    re.compile(r"\b(adult|adulthood)\b"),
    re.compile(r"\b(third[- ]?instar)\b"),
]
LIFE_STAGE_MAP = [
    (re.compile(r"\bembryon", re.I), "embryonic"),
    (re.compile(r"\b(third[- ]?instar|larv)", re.I), "larval"),
    (re.compile(r"\bpup", re.I), "pupal"),
    (re.compile(r"\badult", re.I), "adult"),
]

# Common Drosophila tissues / anatomy
TISSUE_LIST = [
    "Malpighian tubule", "Malpighian tubules", "wing", "wings", "eye", "eyes",
    "ommatidi", "leg", "legs", "mushroom body", "mushroom bodies",
    "central nervous system", "CNS", "brain", "ventral nerve cord",
    "neuron", "neurons", "glia", "glial",
    "ovary", "ovaries", "ovariole", "germline", "germ cell",
    "testis", "testes",
    "midgut", "hindgut", "foregut", "intestine", "gut",
    "trachea", "tracheal", "fat body",
    "muscle", "musculature", "myoblast",
    "cuticle", "epidermis",
    "heart", "dorsal vessel", "cardioblast", "pericardial",
    "salivary gland", "salivary glands",
    "imaginal disc",
    "bristle", "sensory bristle", "macrochaeta", "macrochaetae",
    "olfactory", "antenna", "antennal", "chemosens",
    "photoreceptor", "retina", "lamina", "optic lobe",
    "prothoracic gland",
]
TISSUE_NORMALIZE = {
    "Malpighian tubules": "Malpighian tubule",
    "wings": "wing", "eyes": "eye", "legs": "leg",
    "mushroom bodies": "mushroom body",
    "Malpighian tubule": "Malpighian tubule",
    "CNS": "central nervous system", "brain": "brain",
    "neurons": "neuron", "glial": "glia",
    "ovaries": "ovary",
    "intestine": "gut", "midgut": "gut", "hindgut": "gut", "foregut": "gut",
    "tracheal": "trachea",
    "musculature": "muscle", "myoblast": "muscle",
    "macrochaetae": "macrochaeta", "macrochaeta": "macrochaeta",
    "antennal": "antenna", "chemosens": "chemosensory",
    "salivary glands": "salivary gland", "testes": "testis",
    "ommatidi": "ommatidium",
    "germ cell": "germline",
}


def parse_tissues(text: str) -> list:
    found = set()
    low = text.lower()
    for t in TISSUE_LIST:
        # whole-word-ish
        if re.search(r"\b" + re.escape(t.lower()) + r"\b", low):
            found.add(TISSUE_NORMALIZE.get(t, t.lower()))
    return sorted(found)


def parse_life_stages(text: str) -> list:
    stages = set()
    for pat, label in LIFE_STAGE_MAP:
        if pat.search(text):
            stages.add(label)
    return sorted(stages)


ALLELE_RE = re.compile(
    r"\b("
    r"per0?1?[A-Za-z]*|"
    r"perL|perS|perLvar|persvar|"
    r"shi(?:\[?ts1?\]?|fl54|1|2|7|21|hms[0-9]+|jf[0-9]+|nig[0-9.]+|gd[0-9]+)|"
    r"w(?:1118|1|2|3|m4|sp|a|co|cf|hsbj|118)\b|"
    r"FBal\d{7}|"
    r"N\d+|"
    r"e[12]|"
    r"hry?\d+|"
    r"Dl[0-9A-Za-z]+"
    r")",
)


def parse_alleles(text: str) -> list:
    """Find FlyBase allele names. Conservative — matches well-known patterns."""
    found = set()
    for m in re.finditer(r"\b(FBal\d{7})\b", text):
        found.add(m.group(0))
    # gene-specific allele patterns: SYMBOL + digit/letter trailer
    # Examples we want: per01, perL, perS, shi[ts1], shi1, w1118, etc.
    for m in re.finditer(
        r"\b([a-z]{1,5})(\[[a-zA-Z0-9.]+\]|[0-9][0-9a-zA-Z]*)",
        text,
    ):
        sym, suffix = m.group(1), m.group(2)
        if sym in {"per", "shi", "w", "Dl", "e", "h", "hry", "N", "wg", "en", "Egfr",
                   "Notch", "ebony", "hairy", "white", "shibire", "period",
                   "Per", "Per1", "Per2", "Per3"}:
            # normalize bracket form
            s = suffix.strip("[]")
            found.add(f"{sym}{s}")
    return sorted(found)


# ---- Specificity scoring --------------------------------------------------

NUMBER_RE = re.compile(r"\b\d[\d.,]*(?:%|[xX]|-fold| times| hr| h)?\b")
ENTITY_RE = re.compile(r"\b(FBrf\d+|FBgn\d+|FBal\d+|OMIM:|HP:|MIM:|S\d+[AGRC]|"
                       r"per[01LS]|w[01-9]+|shi\[[^\]]+\])\b")
QUANTIFIER_RE = re.compile(
    r"\b(approximately|about|roughly|completely|partially|fully|nearly|"
    r"significantly|severely|mildly|specifically|exclusively)\b",
    re.I,
)


def score_specificity(phenotype: str, evidence_text: str) -> str:
    """Heuristic — counts numbers, named entities, and length cues to bucket."""
    text = phenotype + " " + evidence_text
    n_numbers = len(NUMBER_RE.findall(text))
    n_entities = len(ENTITY_RE.findall(text))
    n_quant = len(QUANTIFIER_RE.findall(phenotype))
    length_factor = len(phenotype) >= 80
    score = n_numbers * 2 + n_entities * 2 + n_quant + (1 if length_factor else 0)
    if score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


# ---- GO terms from bundle (lossless transfer) -----------------------------

def extract_go(bundle: dict) -> dict:
    """Return {bp:[],mf:[],cc:[]} from FlyBase GO ribbon. ribbon[GO_ID]={'name','num_annotations',...}."""
    out = {"biological_process": [], "molecular_function": [], "cellular_component": []}
    go_block = bundle.get("go", {}) or {}
    for dom_key in out.keys():
        ribbon = go_block.get(dom_key) or {}
        rib = ribbon.get("ribbon") or {}
        kept = []
        seen = set()
        for go_id, rec in rib.items():
            n_anno = rec.get("num_annotations")
            try:
                n = int(n_anno) if n_anno is not None else 0
            except (TypeError, ValueError):
                n = 0
            if n > 0:
                name = (rec.get("name") or "").strip()
                if name and name not in seen:
                    kept.append(name)
                    seen.add(name)
        out[dom_key] = kept
    return out


# ---- Disease IDs from FlyBase bulk ----------------------------------------

@lru_cache(maxsize=1)
def _load_dmel_human_orthologs_disease() -> dict:
    """fbgn → list of {name, omim_id, do_id, human_symbol, diopt_score} from
    orthologs/dmel_human_orthologs_disease_*.tsv.gz.

    File format (FB2026_01):
      ##Dmel_gene_ID  Dmel_gene_symbol  Human_gene_HGNC_ID  Human_gene_OMIM_ID
        Human_gene_symbol  DIOPT_score  OMIM_Phenotype_IDs  OMIM_Phenotype_IDs[name]
    """
    path = next((BULK / "orthologs").glob("dmel_human_orthologs_disease_*.tsv.gz"), None)
    out: dict = {}
    if not path or not path.exists():
        return out
    parsed_re = re.compile(r"(\d+)\[([^\]]+)\]")
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        header = None
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            if line.startswith("##"):
                # column header line begins with '##' (two hashes)
                if "\t" in line and header is None:
                    header = [c.lstrip("#").strip() for c in line.split("\t")]
                continue
            cols = line.split("\t")
            if not header or len(cols) < 5:
                continue
            row = dict(zip(header, cols + [""] * (len(header) - len(cols))))
            fbgn = row.get("Dmel_gene_ID")
            if not fbgn or not fbgn.startswith("FBgn"):
                continue
            human_sym = row.get("Human_gene_symbol", "").strip()
            diopt = row.get("DIOPT_score", "").strip()
            named = row.get("OMIM_Phenotype_IDs[name]", "")
            # parse 'ID[NAME],ID[NAME]' → list of (id, name)
            for m in parsed_re.finditer(named):
                omim_id, disease_name = m.group(1), m.group(2).strip()
                out.setdefault(fbgn, []).append({
                    "name": disease_name,
                    "omim_id": omim_id,
                    "do_id": None,
                    "human_symbol": human_sym,
                    "diopt_score": int(diopt) if diopt.isdigit() else None,
                })
    return out


def disease_links_for(fbgn: str, llm_provided: list) -> list:
    """Merge LLM-extracted disease names with FlyBase bulk OMIM IDs.

    Strategy: bulk is canonical (OMIM IDs + names). LLM names are kept only when they
    don't already appear in bulk — and matched to bulk via *exact short-token* (FASPS3,
    CADASIL1, etc.) rather than fuzzy substring (which gets FASPS1 vs FASPS3 wrong).
    """
    bulk = _load_dmel_human_orthologs_disease().get(fbgn, [])
    out = []
    for d in bulk:
        if d["omim_id"]:
            out.append({
                "name": d["name"],
                "omim_id": d["omim_id"],
                "do_id": d.get("do_id"),
                "source": "flybase_bulk",
            })

    def _short_tokens(s: str) -> set:
        # SHORT_TOKEN_RE matches things like FASPS3, CADASIL1, CMT2T, MIM-numbers
        return {m.group(0).upper() for m in re.finditer(
            r"\b(?:[A-Z]{3,10}\d+[A-Z]*|\d{6})\b", s
        )}

    bulk_tokens = set()
    for d in bulk:
        bulk_tokens.update(_short_tokens(d["name"]))

    for entry in llm_provided or []:
        if not entry:
            continue
        name = entry if isinstance(entry, str) else entry.get("name")
        if not name:
            continue
        ll_tokens = _short_tokens(name)
        if ll_tokens & bulk_tokens:
            # already covered by bulk entry — skip LLM duplicate
            continue
        out.append({
            "name": name,
            "omim_id": None,
            "do_id": None,
            "source": "llm_inferred",
        })
    return out


# ---- Full synonyms from FlyBase bulk --------------------------------------

@lru_cache(maxsize=1)
def _load_fbgn_annotation_index() -> dict:
    """Build fbgn → set(synonyms) from fbgn_annotation_ID bulk file."""
    path = next((BULK / "genes").glob("fbgn_annotation_ID_*.tsv.gz"), None)
    out: dict = {}
    if not path or not path.exists():
        return out
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            if len(cols) < 4:
                continue
            # Columns (FB2026_01 layout):
            #   gene_symbol  organism_abbreviation  primary_FBgn  secondary_FBgn  annotation_ID  secondary_annotation_ID
            sym = cols[0]
            fbgn = cols[2]
            secondary_fbgn = cols[3] if len(cols) > 3 else ""
            ann_id = cols[4] if len(cols) > 4 else ""
            sec_ann = cols[5] if len(cols) > 5 else ""
            syns = {sym}
            if ann_id: syns.add(ann_id)
            if secondary_fbgn:
                for x in secondary_fbgn.split(","):
                    if x: syns.add(x.strip())
            if sec_ann:
                for x in sec_ann.split(","):
                    if x: syns.add(x.strip())
            out[fbgn] = sorted(s for s in syns if s)
    return out


def synonyms_for(fbgn: str, fallback: list = None) -> list:
    bulk = _load_fbgn_annotation_index().get(fbgn, [])
    if bulk:
        return bulk
    return fallback or []


@lru_cache(maxsize=1)
def _load_fbgn_annotation_typed() -> dict:
    """fbgn → list of {synonym, type, is_current} from fbgn_annotation_ID."""
    path = next((BULK / "genes").glob("fbgn_annotation_ID_*.tsv.gz"), None)
    out: dict = {}
    if not path or not path.exists():
        return out
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            if len(cols) < 5:
                continue
            sym = cols[0]
            fbgn_primary = cols[2]
            secondary_fbgn = cols[3] if len(cols) > 3 else ""
            ann_id = cols[4] if len(cols) > 4 else ""
            sec_ann = cols[5] if len(cols) > 5 else ""
            entries = []
            if sym:
                entries.append({"synonym": sym, "type": "current_symbol", "is_current": True})
            if ann_id:
                entries.append({"synonym": ann_id, "type": "annotation_id", "is_current": True})
            if secondary_fbgn:
                for x in secondary_fbgn.split(","):
                    x = x.strip()
                    if x:
                        entries.append({"synonym": x, "type": "secondary_fbgn", "is_current": False})
            if sec_ann:
                for x in sec_ann.split(","):
                    x = x.strip()
                    if x:
                        entries.append({"synonym": x, "type": "secondary_annotation_id", "is_current": False})
            out[fbgn_primary] = entries
    return out


def synonyms_typed_for(fbgn: str, fallback_symbol: str = None) -> list:
    bulk = _load_fbgn_annotation_typed().get(fbgn, [])
    if bulk:
        return bulk
    return [{"synonym": fallback_symbol, "type": "current_symbol", "is_current": True}] if fallback_symbol else []


def disease_links_with_ortholog(fbgn: str, llm_provided: list) -> list:
    """Like disease_links_for() but threads in `via_ortholog` field — which human gene
    is the source of the OMIM phenotype association (GPT review #15)."""
    bulk = _load_dmel_human_orthologs_disease().get(fbgn, [])
    out = []
    for d in bulk:
        if d["omim_id"]:
            out.append({
                "name": d["name"],
                "omim_id": d["omim_id"],
                "do_id": d.get("do_id"),
                "source": "flybase_bulk",
                "via_ortholog": {
                    "species": "human",
                    "symbol": d.get("human_symbol"),
                    "diopt_score": d.get("diopt_score"),
                },
            })

    def _short_tokens(s: str) -> set:
        return {m.group(0).upper() for m in re.finditer(
            r"\b(?:[A-Z]{3,10}\d+[A-Z]*|\d{6})\b", s
        )}
    bulk_tokens = set()
    for d in bulk:
        bulk_tokens.update(_short_tokens(d["name"]))
    for entry in llm_provided or []:
        if not entry:
            continue
        name = entry if isinstance(entry, str) else entry.get("name")
        if not name:
            continue
        ll_tokens = _short_tokens(name)
        if ll_tokens & bulk_tokens:
            continue
        out.append({
            "name": name,
            "omim_id": None,
            "do_id": None,
            "source": "llm_inferred",
            "via_ortholog": None,
        })
    return out
