"""In-memory index of all downloaded FlyBase bulk TSVs.

Loads once at module import (~5-10s, ~500 MB RAM). After that, every per-gene
lookup is microseconds. NO HTTP calls to FlyBase. Replaces fetch_gene.py's
HTML scrape + API fetch path entirely.

Usage:
    from bulk_index import BULK
    auto = BULK.summaries["FBgn0003068"]
    phenotypes = BULK.phenotypes_by_gene["FBgn0003068"]
    pmids = [pmid for fbrf, pmid in BULK.gene_pubs["FBgn0003068"] if pmid]
"""
import gzip
import re
import threading
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BULK_DIR = ROOT / "data" / "flybase_bulk"
ALLIANCE_DIR = ROOT / "data" / "alliance"


def _open(rel_path: str):
    """Open a gzip'd TSV from data/flybase_bulk/, yields decoded lines."""
    p = next((BULK_DIR / rel_path.split("/")[0]).glob(rel_path.split("/")[1] + "_*.tsv.gz"), None)
    if not p:
        raise FileNotFoundError(f"no bulk file matching {rel_path}_*.tsv.gz")
    return gzip.open(p, "rt", encoding="utf-8", errors="replace")


def _iter_data_rows(rel_path: str):
    """Yield non-comment, non-empty rows split by tab."""
    with _open(rel_path) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            yield line.split("\t")


class BulkIndex:
    def __init__(self):
        print("[bulk_index] loading FlyBase bulk TSVs...", flush=True)
        import time
        t0 = time.time()

        # FBgn → primary symbol + typed synonyms
        self.symbols = {}                       # fbgn → symbol
        self.synonyms = defaultdict(list)       # fbgn → [{synonym, type, is_current}]
        self.fbal_to_fbgn = {}                  # fbal → fbgn (for resolving allele → gene)
        self._load_fbgn_annotation_id()

        # gene-level text
        self.summaries = {}                     # fbgn → auto summary text
        self.snapshots = {}                     # fbgn → curator snapshot text (mostly empty)
        self._load_automated_gene_summaries()
        self._load_gene_snapshots()

        # phenotype annotations (per-allele rows, indexed by parent gene)
        self.phenotypes_by_gene = defaultdict(list)
        self._load_genotype_phenotype()

        # allele descriptions
        self.allele_descriptions_by_gene = defaultdict(list)
        self._load_allele_descriptions()

        # cross-species + disease
        self.orthologs_disease = defaultdict(list)   # fbgn → [{human_symbol, hgnc, mim, diopt, omim_pheno_ids, omim_pheno_names}]
        self._load_orthologs_disease()
        self.disease_models = defaultdict(list)      # fbgn → [{do_qualifier, do_id, do_term, allele, evidence, ref}]
        self._load_disease_model_annotations()

        # publications — initialize all dicts first since rep_pubs loader
        # opportunistically populates fbrf_to_pmid from its 'FBrfNNN|PMID:NNN' tokens
        self.fbrf_to_pmid = {}                  # fbrf → pmid (or empty if no PMID)
        self.fbrf_meta = {}                     # fbrf → {miniref, pub_type, year, doi}
        self.rep_pubs = {}                      # fbgn → [fbrf] (FlyBase curator-picked representatives)
        self.gene_pubs = defaultdict(list)      # fbgn → [(fbrf, pmid)]
        self._load_representative_publications()
        self._load_entity_publication()
        self._load_fbrf_pmid_doi()

        # interactions
        self.genetic_interactions = defaultdict(list)   # fbgn → [{partner_fbgn, partner_symbol, type, ref}]
        self._load_genetic_interactions()
        self.physical_interactions = defaultdict(list)  # fbgn → [{partner, assay, ref}]
        self._load_physical_interactions()

        # cross-species orthologs (Alliance)
        self.human_orthologs = defaultdict(list)        # fbgn → [{symbol, hgnc, methods, score}]
        self.mouse_orthologs = defaultdict(list)        # fbgn → [{symbol, mgi, methods, score}]
        self._load_alliance_orthologs()

        dt = time.time() - t0
        print(f"[bulk_index] loaded {len(self.symbols)} genes in {dt:.1f}s; "
              f"{sum(len(v) for v in self.phenotypes_by_gene.values())} phenotype rows; "
              f"{sum(len(v) for v in self.gene_pubs.values())} gene-pub edges; "
              f"{len(self.fbrf_to_pmid)} FBrf↔PMID maps", flush=True)

    # ---- loaders ----------------------------------------------------------

    def _load_fbgn_annotation_id(self):
        # cols: gene_symbol, organism, primary_FBgn, secondary_FBgn, annotation_ID, secondary_annotation_ID
        for cols in _iter_data_rows("genes/fbgn_annotation_ID"):
            if len(cols) < 5:
                continue
            sym, _, fbgn = cols[0], cols[1], cols[2]
            self.symbols[fbgn] = sym
            secondary_fbgn = cols[3] if len(cols) > 3 else ""
            ann_id = cols[4] if len(cols) > 4 else ""
            sec_ann = cols[5] if len(cols) > 5 else ""
            self.synonyms[fbgn].append({"synonym": sym, "type": "current_symbol", "is_current": True})
            if ann_id:
                self.synonyms[fbgn].append({"synonym": ann_id, "type": "annotation_id", "is_current": True})
            if secondary_fbgn:
                for x in secondary_fbgn.split(","):
                    x = x.strip()
                    if x:
                        self.synonyms[fbgn].append({"synonym": x, "type": "secondary_fbgn", "is_current": False})
            if sec_ann:
                for x in sec_ann.split(","):
                    x = x.strip()
                    if x:
                        self.synonyms[fbgn].append({"synonym": x, "type": "secondary_annotation_id", "is_current": False})

    def _load_automated_gene_summaries(self):
        for cols in _iter_data_rows("genes/automated_gene_summaries"):
            if len(cols) < 2:
                continue
            self.summaries[cols[0]] = cols[1]

    def _load_gene_snapshots(self):
        # cols: FBgn, Symbol, Name, datestamp, snapshot_text
        for cols in _iter_data_rows("genes/gene_snapshots"):
            if len(cols) < 5:
                continue
            text = cols[4].strip()
            # skip placeholder text
            if text and not text.startswith("Contributions welcome"):
                self.snapshots[cols[0]] = text

    def _load_genotype_phenotype(self):
        """phenotypes are per-allele; resolve to parent gene via fbal_to_fbgn map.
        cols: genotype_symbols, genotype_FBids, phenotype_name, phenotype_id,
              qualifier_names, qualifier_ids, reference"""
        # First build fbal_to_fbgn from a different source file
        self._load_fbal_to_fbgn()

        for cols in _iter_data_rows("alleles/genotype_phenotype_data"):
            if len(cols) < 4:
                continue
            geno_ids = cols[1]      # "FBal0119724" OR "FBal0001/FBti0002"
            phen_name = cols[2]
            phen_id = cols[3]
            qualifier = cols[4] if len(cols) > 4 else ""
            ref = cols[6] if len(cols) > 6 else ""

            # extract any FBal IDs from genotype_FBids and resolve to FBgn
            resolved_fbgns = set()
            for m in re.finditer(r"FBal\d{7}", geno_ids):
                fbal = m.group(0)
                fbgn = self.fbal_to_fbgn.get(fbal)
                if fbgn:
                    resolved_fbgns.add(fbgn)

            for fbgn in resolved_fbgns:
                self.phenotypes_by_gene[fbgn].append({
                    "phenotype": phen_name,
                    "phenotype_id": phen_id,
                    "qualifier": qualifier,
                    "ref": ref,
                    "genotype": cols[0],
                })

    def _load_fbal_to_fbgn(self):
        # actual schema: FBal_ID, allele_symbol, FBgn_ID, gene_symbol
        for cols in _iter_data_rows("alleles/fbal_to_fbgn"):
            if len(cols) < 4:
                continue
            fbal = cols[0]
            fbgn = cols[2]
            if fbal.startswith("FBal") and fbgn.startswith("FBgn"):
                self.fbal_to_fbgn[fbal] = fbgn

    def _load_allele_descriptions(self):
        """cols: Allele_symbol, Allele_id, Gene_symbol, Gene_id, Allele_class, ...,
        Description_text, Description_supporting_reference, Stocks_number"""
        for cols in _iter_data_rows("alleles/dmel_classical_and_insertion_allele_descriptions"):
            if len(cols) < 21:
                continue
            allele_sym = cols[0]
            fbgn = cols[3]
            description = cols[18]
            ref = cols[19] if len(cols) > 19 else ""
            if fbgn and description:
                self.allele_descriptions_by_gene[fbgn].append({
                    "allele": allele_sym,
                    "description": description,
                    "ref": ref,
                })

    def _load_orthologs_disease(self):
        """cols: Dmel_gene_ID, Dmel_gene_symbol, Human_gene_HGNC_ID, Human_gene_OMIM_ID,
        Human_gene_symbol, DIOPT_score, OMIM_Phenotype_IDs, OMIM_Phenotype_IDs[name]"""
        named_re = re.compile(r"(\d+)\[([^\]]+)\]")
        for cols in _iter_data_rows("orthologs/dmel_human_orthologs_disease"):
            if len(cols) < 6:
                continue
            fbgn = cols[0]
            human_sym = cols[4]
            try:
                diopt = int(cols[5])
            except ValueError:
                diopt = None
            omim_ids = cols[6] if len(cols) > 6 else ""
            omim_named = cols[7] if len(cols) > 7 else ""
            # parse omim phenotype names
            phenotypes = []
            for m in named_re.finditer(omim_named):
                phenotypes.append({"omim_id": m.group(1), "name": m.group(2).strip()})
            self.orthologs_disease[fbgn].append({
                "human_symbol": human_sym,
                "hgnc": cols[2],
                "mim": cols[3],
                "diopt_score": diopt,
                "omim_phenotypes": phenotypes,
            })

    def _load_disease_model_annotations(self):
        """cols: FBgn, symbol, HGNC, DO_qualifier, DO_ID, DO_term, allele_FBal,
        allele_symbol, ortholog_HGNC, ortholog_symbol, evidence, FBrf"""
        for cols in _iter_data_rows("human_disease/disease_model_annotations"):
            if len(cols) < 12:
                continue
            fbgn = cols[0]
            self.disease_models[fbgn].append({
                "do_qualifier": cols[3],
                "do_id": cols[4],
                "do_term": cols[5],
                "allele": cols[7],
                "ortholog_symbol": cols[9],
                "evidence": cols[10],
                "ref": cols[11],
            })

    def _load_representative_publications(self):
        """cols: FBgn, symbol, References (comma-separated 'FBrfNNN|PMID:NNN' tokens —
        PMID:NNN may be absent for unpublished/preprint refs)."""
        for cols in _iter_data_rows("references/representative_publications"):
            if len(cols) < 3:
                continue
            fbrfs = []
            for token in cols[2].split(","):
                token = token.strip()
                if not token:
                    continue
                # split on first '|' — left is FBrf, right (if present) is 'PMID:NNN'
                parts = token.split("|", 1)
                fbrf = parts[0].strip()
                if not fbrf.startswith("FBrf"):
                    continue
                fbrfs.append(fbrf)
                if len(parts) > 1 and parts[1].startswith("PMID:"):
                    pmid = parts[1][5:].strip()
                    if pmid and fbrf not in self.fbrf_to_pmid:
                        self.fbrf_to_pmid[fbrf] = pmid
            if fbrfs:
                self.rep_pubs[cols[0]] = fbrfs

    def _load_entity_publication(self):
        """cols: entity_id, entity_name, FlyBase_publication_id, PubMed_id"""
        for cols in _iter_data_rows("references/entity_publication"):
            if len(cols) < 3:
                continue
            entity_id = cols[0]
            if not entity_id.startswith("FBgn"):
                continue
            fbrf = cols[2] if len(cols) > 2 else ""
            pmid = cols[3] if len(cols) > 3 else ""
            if fbrf:
                self.gene_pubs[entity_id].append((fbrf, pmid))

    def _load_fbrf_pmid_doi(self):
        """cols: FBrf, PMID, PMCID, DOI, pub_type, miniref, pmid_added"""
        for cols in _iter_data_rows("references/fbrf_pmid_pmcid_doi"):
            if len(cols) < 6:
                continue
            fbrf, pmid, _pmcid, doi, pub_type, miniref = cols[:6]
            if pmid:
                self.fbrf_to_pmid[fbrf] = pmid
            # extract year from miniref like "Smith et al., 2023, Journal 12(3): e789"
            year_m = re.search(r"(\d{4})", miniref)
            self.fbrf_meta[fbrf] = {
                "miniref": miniref,
                "pub_type": pub_type,
                "doi": doi,
                "year": int(year_m.group(1)) if year_m else None,
            }

    def _load_genetic_interactions(self):
        # actual schema: starting_sym, starting_FBgn, partner_sym, partner_FBgn, type, ref
        # bidirectional: index both starting and partner
        try:
            for cols in _iter_data_rows("genes/gene_genetic_interactions"):
                if len(cols) < 6:
                    continue
                a_fbgn = cols[1]
                b_fbgn = cols[3]
                if not (a_fbgn.startswith("FBgn") and b_fbgn.startswith("FBgn")):
                    continue
                row_a = {"partner_fbgn": b_fbgn, "partner_symbol": cols[2],
                         "type": cols[4], "ref": cols[5], "as": "starting"}
                row_b = {"partner_fbgn": a_fbgn, "partner_symbol": cols[0],
                         "type": cols[4], "ref": cols[5], "as": "partner"}
                self.genetic_interactions[a_fbgn].append(row_a)
                self.genetic_interactions[b_fbgn].append(row_b)
        except FileNotFoundError:
            pass

    def _load_alliance_orthologs(self):
        """Alliance ortholog file: each row pair (Gene1 vs Gene2) for stringent orthologs.
        We only care about rows where one side is FB: and the other is HGNC: or MGI:.
        Schema: g1_id, g1_sym, g1_taxon, g1_species, g2_id, g2_sym, g2_taxon, g2_species,
                methods, n_called, max_possible, best, best_reverse"""
        path = ALLIANCE_DIR / "ORTHOLOGY-ALLIANCE_COMBINED.tsv.gz"
        if not path.exists():
            return
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line or line.startswith("#"):
                    continue
                cols = line.split("\t")
                if len(cols) < 10:
                    continue
                g1_id, g1_sym = cols[0], cols[1]
                g2_id, g2_sym = cols[4], cols[5]
                methods = cols[8]
                try:
                    n_called = int(cols[9])
                    max_possible = int(cols[10]) if len(cols) > 10 else None
                except ValueError:
                    n_called, max_possible = None, None
                # ensure FB side is identified
                fly_id, partner_id, partner_sym = None, None, None
                if g1_id.startswith("FB:") and (g2_id.startswith("HGNC:") or g2_id.startswith("MGI:")):
                    fly_id, partner_id, partner_sym = g1_id, g2_id, g2_sym
                elif g2_id.startswith("FB:") and (g1_id.startswith("HGNC:") or g1_id.startswith("MGI:")):
                    fly_id, partner_id, partner_sym = g2_id, g1_id, g1_sym
                else:
                    continue
                fbgn = fly_id.split(":", 1)[1]
                entry = {
                    "symbol": partner_sym,
                    "external_id": partner_id,
                    "methods": methods,
                    "diopt_score": n_called,
                    "diopt_max": max_possible,
                }
                if partner_id.startswith("HGNC:"):
                    self.human_orthologs[fbgn].append(entry)
                else:
                    self.mouse_orthologs[fbgn].append(entry)

    def _load_physical_interactions(self):
        try:
            # MITAB format — complex; minimal extraction
            with _open("genes/physical_interactions_mitab") as f:
                for line in f:
                    line = line.rstrip("\n")
                    if not line or line.startswith("#"):
                        continue
                    cols = line.split("\t")
                    if len(cols) < 12:
                        continue
                    # MITAB cols 1+2 are interactor A/B identifiers (flybase:FBgn...)
                    for fbgn_field in (cols[0], cols[1]):
                        m = re.search(r"FBgn\d{7}", fbgn_field)
                        if not m:
                            continue
                        a_fbgn = m.group(0)
                        other = cols[1] if fbgn_field == cols[0] else cols[0]
                        partner_m = re.search(r"FBgn\d{7}", other)
                        partner = partner_m.group(0) if partner_m else ""
                        if partner and partner != a_fbgn:
                            self.physical_interactions[a_fbgn].append({
                                "partner_fbgn": partner,
                                "assay": cols[6] if len(cols) > 6 else "",
                                "ref": cols[8] if len(cols) > 8 else "",
                            })
        except FileNotFoundError:
            pass


# Module-level singleton; lazy + thread-safe (double-checked locking).
# Multiple fetcher threads racing on this would otherwise each spawn their own
# BulkIndex instance (~500MB each), spiking RAM to several GB before GC catches up.
_BULK = None
_BULK_LOCK = threading.Lock()
def get_bulk() -> BulkIndex:
    global _BULK
    if _BULK is None:
        with _BULK_LOCK:
            if _BULK is None:
                _BULK = BulkIndex()
    return _BULK


# Convenience
def main():
    """Smoke test: load + inspect period gene."""
    b = get_bulk()
    fbgn = "FBgn0003068"
    print(f"\n=== {fbgn} ({b.symbols.get(fbgn)}) ===")
    print(f"synonyms:        {b.synonyms.get(fbgn, [])}")
    print(f"auto_summary:    {(b.summaries.get(fbgn) or '')[:150]}...")
    print(f"phenotype rows:  {len(b.phenotypes_by_gene.get(fbgn, []))}")
    sample_phen = b.phenotypes_by_gene.get(fbgn, [])[:3]
    for p in sample_phen:
        print(f"   • {p['phenotype']} ({p['phenotype_id']}) qualifier={p['qualifier']!r}")
    print(f"allele descs:    {len(b.allele_descriptions_by_gene.get(fbgn, []))}")
    print(f"orth+disease:    {len(b.orthologs_disease.get(fbgn, []))} human ortholog entries")
    for od in b.orthologs_disease.get(fbgn, [])[:3]:
        print(f"   • {od['human_symbol']} DIOPT {od['diopt_score']}/14  pheno: {[p['name'][:50] for p in od['omim_phenotypes']]}")
    print(f"disease models:  {len(b.disease_models.get(fbgn, []))}")
    print(f"rep pubs:        {len(b.rep_pubs.get(fbgn, []))} representative FBrfs")
    print(f"all pubs:        {len(b.gene_pubs.get(fbgn, []))} total (fbrf,pmid) edges")
    pmids = [p for f, p in b.gene_pubs.get(fbgn, []) if p]
    print(f"   with PMIDs:   {len(pmids)} → first 5: {pmids[:5]}")
    print(f"genetic ix:      {len(b.genetic_interactions.get(fbgn, []))}")
    print(f"physical ix:     {len(b.physical_interactions.get(fbgn, []))}")
    print(f"human orthologs (Alliance): {len(b.human_orthologs.get(fbgn, []))}")
    for o in b.human_orthologs.get(fbgn, [])[:3]:
        print(f"   • {o['symbol']:8} {o['external_id']:16} DIOPT {o['diopt_score']}/{o['diopt_max']}")
    print(f"mouse orthologs (Alliance): {len(b.mouse_orthologs.get(fbgn, []))}")
    for o in b.mouse_orthologs.get(fbgn, [])[:3]:
        print(f"   • {o['symbol']:8} {o['external_id']:16} DIOPT {o['diopt_score']}/{o['diopt_max']}")


if __name__ == "__main__":
    main()
