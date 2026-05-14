"""Curated gene list spanning annotation tiers for the GLM distillation pilot.

Selection rationale:
  - Tier A (well-studied, ≥50 representative refs): test high-context handling
  - Tier B (medium, 10-50 refs): test typical XQTL candidate gene
  - Tier C (sparse, mostly CG-identifier, <10 refs): test ortholog-rescue case where
    fly annotation is thin but mouse/human ortholog is informative
"""

GENES = [
    # Tier A — well-studied
    {"fbgn": "FBgn0003068", "symbol": "per",   "tier": "A", "note": "circadian clock"},
    {"fbgn": "FBgn0004647", "symbol": "N",     "tier": "A", "note": "Notch signaling"},
    {"fbgn": "FBgn0001168", "symbol": "h",     "tier": "A", "note": "hairy / pair-rule"},
    {"fbgn": "FBgn0000527", "symbol": "e",     "tier": "A", "note": "ebony / pigmentation+behavior"},
    {"fbgn": "FBgn0003996", "symbol": "w",     "tier": "A", "note": "white / Long's FlyBase example"},

    # Tier B — medium
    {"fbgn": "FBgn0003392", "symbol": "shi",   "tier": "B", "note": "shibire / dynamin"},
    {"fbgn": "FBgn0014020", "symbol": "Rho1",  "tier": "B", "note": "Rho1 GTPase"},
    {"fbgn": "FBgn0000577", "symbol": "en",    "tier": "B", "note": "engrailed segmentation"},
    {"fbgn": "FBgn0035976", "symbol": "PGRP-LB","tier": "B","note": "PGRP-LB immune (Long mentioned)"},
    {"fbgn": "FBgn0003731", "symbol": "Egfr",  "tier": "B", "note": "EGF receptor"},

    # Tier C — sparse / CG-identifier-only (cross-species rescue test)
    {"fbgn": "FBgn0033749", "symbol": "CG13110", "tier": "C", "note": "sparse CG"},
    {"fbgn": "FBgn0036708", "symbol": "CG7461",  "tier": "C", "note": "sparse CG"},
    {"fbgn": "FBgn0030608", "symbol": "CG3434",  "tier": "C", "note": "sparse CG"},
    {"fbgn": "FBgn0028717", "symbol": "CG6175",  "tier": "C", "note": "sparse CG"},
    {"fbgn": "FBgn0039755", "symbol": "CG15545", "tier": "C", "note": "sparse CG"},
]

if __name__ == "__main__":
    for g in GENES:
        print(g)
