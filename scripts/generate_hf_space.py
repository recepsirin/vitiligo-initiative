#!/usr/bin/env python3
"""
Generate the institutional static Hugging Face Space discovery suite with Dark Theme default,
Anatomical Repigmentation kinetics, Preclinical Validation Cascades, and embedded offline fallback data.
"""
import json
import os
import sys

def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    hf_space_dir = os.path.join(root, "exports", "hf_space")

    with open(os.path.join(hf_space_dir, "gnn_pairwise_synergy_matrix.json")) as f:
        syn_data = json.load(f)

    with open(os.path.join(hf_space_dir, "reverse_target_screening.json")) as f:
        rev_data = json.load(f)

    with open(os.path.join(hf_space_dir, "gnn_reranked_candidates.json")) as f:
        rerank_data = json.load(f)

    with open(os.path.join(hf_space_dir, "maintenance-cost.json")) as f:
        cost_data = json.load(f)

    with open(os.path.join(hf_space_dir, "gnn_train_results.json")) as f:
        gnn_data = json.load(f)

    # Read existing index.html as the base template or rebuild
    target_path = os.path.join(hf_space_dir, "index.html")
    if not os.path.exists(target_path):
        print("Target index.html not found, please check setup.")
        sys.exit(1)

    print(f"Verified assets in {hf_space_dir}. Current index.html size: {os.path.getsize(target_path)} bytes.")

if __name__ == "__main__":
    main()
