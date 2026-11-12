#!/usr/bin/env python3
"""
Deploy or sync exports/hf_space to Hugging Face Space (re-cep/vitiligo-curative-discovery).
"""

import argparse
import sys
from pathlib import Path

from huggingface_hub import HfApi


def deploy(repo_id: str, commit_msg: str):
    root = Path(__file__).resolve().parent.parent.parent
    hf_space_dir = root / "exports" / "hf_space"

    if not (hf_space_dir / "index.html").is_file():
        print(f"Error: {hf_space_dir / 'index.html'} not found.")
        sys.exit(1)

    api = HfApi()
    try:
        user = api.whoami()
        print(f"Authenticated as: {user.get('name')}")
    except Exception as e:
        print(f"Authentication check notice: {e}")

    print(f"Uploading {hf_space_dir} to Space {repo_id}...")
    commit_info = api.upload_folder(
        folder_path=str(hf_space_dir),
        repo_id=repo_id,
        repo_type="space",
        commit_message=commit_msg,
    )
    print("Deployment successful! Commit URL:", commit_info)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy exports/hf_space to Hugging Face Space.")
    parser.add_argument(
        "--repo-id",
        default="re-cep/vitiligo-curative-discovery",
        help="Target HF Space repo ID",
    )
    parser.add_argument(
        "--message",
        default="feat(space): update static suite with interactive features",
        help="Commit message",
    )
    args = parser.parse_args()
    deploy(args.repo_id, args.message)
