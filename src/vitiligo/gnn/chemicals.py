"""Chemical structure feature extractor using PubChem SMILES and RDKit Morgan fingerprints."""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import torch
from rdkit import Chem
from rdkit.Chem import AllChem

from vitiligo.gnn.dataset import GraphDataset
from vitiligo.logging import get_logger

logger = get_logger(__name__)

DEFAULT_SMILES_CACHE = Path("data/cache/gnn/drug_smiles.json")
DEFAULT_CHEMICAL_CACHE = Path("data/cache/gnn/chemical_fingerprints.pt")
FINGERPRINT_BITS = 1024
MORGAN_RADIUS = 2


def clean_drug_name(name: str) -> str:
    """Strip common salt, ester, and hydrate modifiers for chemical structure lookup."""
    n = re.sub(
        r"(?i)\b(tosylate|phosphate|hydrochloride|dihydrochloride|succinate|sodium|hydrate|anhydrous|acetate|fumarate|maleate|sulfate|tartrate|mesylate|potassium|citrate|calcium|monohydrate|dipropionate|butyrate|valerate|propionate)\b",
        "",
        name,
    )
    n = re.sub(r"[\(\),]", " ", n).strip()
    return re.sub(r"\s+", " ", n).strip()


def fetch_pubchem_smiles(name: str, cache: dict[str, str | None]) -> str | None:
    """Fetch canonical/connectivity SMILES for a single drug from PubChem PUG REST with rate-limit handling."""
    if name in cache and cache[name] is not None:
        return cache[name]

    cleaned = clean_drug_name(name)
    queries = [cleaned] if cleaned.lower() == name.lower() else [cleaned, name]

    for q in queries:
        if not q or len(q) < 2:
            continue
        enc = urllib.parse.quote(q)
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{enc}/property/ConnectivitySMILES,SMILES/JSON"
        for attempt in range(3):
            try:
                time.sleep(0.06)
                req = urllib.request.Request(url, headers={"User-Agent": "VitiligoDiscovery/1.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    props = data["PropertyTable"]["Properties"][0]
                    smiles = props.get("ConnectivitySMILES") or props.get("SMILES")
                    if smiles:
                        cache[name] = smiles
                        return smiles
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    time.sleep(1.0 + attempt * 1.0)
                    continue
                elif e.code == 404:
                    break
            except Exception:
                time.sleep(0.5)
                continue

    cache[name] = None
    return None


def resolve_all_drug_smiles(
    dataset: GraphDataset,
    cache_path: Path | str = DEFAULT_SMILES_CACHE,
    max_workers: int = 4,
) -> dict[str, str]:
    """Resolve SMILES for all canonical drug entities in dataset with persistent disk caching."""
    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    cache: dict[str, str | None] = {}
    if cache_path.exists():
        try:
            with open(cache_path, encoding="utf-8") as f:
                cache = json.load(f)
            logger.info("Loaded %d cached drug SMILES from %s", len(cache), cache_path)
        except Exception as e:
            logger.warning("Failed to load SMILES cache: %s", e)

    drug_indices = dataset.canonical_drug_indices or dataset.kind_to_indices.get("DRUG", [])
    drug_names = [dataset.entities[idx].name for idx in drug_indices]

    # Re-try names that were previously null or missing
    missing = [name for name in drug_names if name not in cache or cache[name] is None]
    if missing:
        logger.info("Resolving SMILES from PubChem for %d drugs...", len(missing))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fetch_pubchem_smiles, n, cache): n for n in missing}
            for fut in as_completed(futures):
                fut.result()

        # Save updated cache
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
        logger.info("Saved %d resolved SMILES to %s", len(cache), cache_path)

    # Filter to non-null SMILES
    return {k: v for k, v in cache.items() if v is not None}


def smiles_to_morgan_fingerprint(
    smiles: str,
    n_bits: int = FINGERPRINT_BITS,
    radius: int = MORGAN_RADIUS,
) -> np.ndarray | None:
    """Convert a SMILES string to a binary Morgan / ECFP4 fingerprint numpy array."""
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius, nBits=n_bits)
        arr = np.zeros((n_bits,), dtype=np.float32)
        for on_bit in fp.GetOnBits():
            arr[on_bit] = 1.0
        # Normalize to unit length
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr /= norm
        return arr
    except Exception:
        return None


def build_chemical_node_features(
    dataset: GraphDataset,
    cache_path: Path | str = DEFAULT_CHEMICAL_CACHE,
    force_reload: bool = False,
) -> torch.Tensor:
    """Build a [num_nodes, FINGERPRINT_BITS] tensor containing Morgan fingerprints for drugs."""
    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    if not force_reload and cache_path.exists():
        try:
            tensor = torch.load(cache_path, weights_only=True)
            if tensor.shape[0] == dataset.num_nodes and tensor.shape[1] == FINGERPRINT_BITS:
                logger.info("Loaded cached chemical fingerprints from %s (shape: %s)", cache_path, tensor.shape)
                return tensor
        except Exception as e:
            logger.warning("Could not load chemical cache (%s); regenerating...", e)

    smiles_dict = resolve_all_drug_smiles(dataset)
    num_nodes = dataset.num_nodes
    chem_matrix = np.zeros((num_nodes, FINGERPRINT_BITS), dtype=np.float32)

    matched = 0
    drug_indices = dataset.kind_to_indices.get("DRUG", [])
    for d_idx in drug_indices:
        name = dataset.entities[d_idx].name
        smi = smiles_dict.get(name)
        if smi:
            fp = smiles_to_morgan_fingerprint(smi, n_bits=FINGERPRINT_BITS, radius=MORGAN_RADIUS)
            if fp is not None:
                chem_matrix[d_idx] = fp
                matched += 1

    logger.info(
        "Generated Morgan ECFP4 fingerprints for %d / %d drugs (total nodes: %d)",
        matched,
        len(drug_indices),
        num_nodes,
    )
    tensor = torch.from_numpy(chem_matrix)
    torch.save(tensor, cache_path)
    logger.info("Saved chemical fingerprint tensor to %s", cache_path)
    return tensor
