#!/usr/bin/env python
"""Fetch the OnStove Mendeley dataset (inputs + published outputs).

Dataset: "OnStove inputs and outputs", Mendeley Data
doi:10.17632/7y943f6wf8.2 (v2), generated with OnStove v0.1.1 — the companion
to Khavari et al. (2023), Nature Sustainability.

Two modes:

* ``--from-mendeley`` — download every file in the dataset via the Mendeley
  public API into ``--dest``, preserving the dataset's own structure. Requires
  network access to ``data.mendeley.com`` + ``requests``.
* ``--from-local <dir>`` — you already downloaded the dataset; just point at it.
  The script prints the file tree so you can set the ``paths:`` in your country
  config to match.

It does NOT guess how to re-lay-out the dataset into OnStove's expected folders
(that depends on the dataset's internal structure, which you should eyeball from
the printed tree and reflect in ``config/<country>.yaml`` + the repo's existing
Snakemake harness, ``snakefile.smk``).

NOTE: in the Claude-Code-on-the-web sandbox the network policy blocks
data.mendeley.com and there is no geospatial stack — run this on a machine that
has both. The ``--from-mendeley`` path is therefore not exercised in CI.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

MENDELEY_API = "https://data.mendeley.com/public-api/datasets/{id}/files?version={ver}"


def from_mendeley(dataset_id: str, version: int, dest: Path) -> int:
    try:
        import requests
    except ImportError:
        print("requests not installed; `pip install requests`", file=sys.stderr)
        return 2

    url = MENDELEY_API.format(id=dataset_id, ver=version)
    print(f"listing {url}")
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    files = resp.json()
    if not isinstance(files, list):
        print(f"unexpected API response: {files!r}", file=sys.stderr)
        return 1

    dest.mkdir(parents=True, exist_ok=True)
    for f in files:
        name = f.get("filename") or f.get("name")
        dl = (f.get("content_details") or {}).get("download_url") or f.get("download_url")
        if not (name and dl):
            print(f"  skip (no name/url): {f}", file=sys.stderr)
            continue
        out = dest / name
        print(f"  downloading {name} -> {out}")
        with requests.get(dl, stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(out, "wb") as fh:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    fh.write(chunk)
    print(f"\nDone. Files under {dest}:")
    _print_tree(dest)
    return 0


def from_local(src: Path) -> int:
    if not src.exists():
        print(f"{src} does not exist", file=sys.stderr)
        return 1
    print(f"Dataset already present at {src}. File tree:")
    _print_tree(src)
    print("\nNow set the `paths:` block in your config/<country>.yaml to match,\n"
          "then prepare layers with the repo's Snakemake harness (snakefile.smk)\n"
          "or example/OnStove_notebook.ipynb.")
    return 0


def _print_tree(root: Path, max_entries: int = 200) -> None:
    count = 0
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        indent = "  " * (len(rel.parts) - 1)
        print(f"  {indent}{p.name}{'/' if p.is_dir() else ''}")
        count += 1
        if count >= max_entries:
            print(f"  ... (truncated at {max_entries} entries)")
            break


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--from-mendeley", action="store_true")
    g.add_argument("--from-local", type=Path, metavar="DIR")
    p.add_argument("--dataset-id", default="7y943f6wf8")
    p.add_argument("--version", type=int, default=2)
    p.add_argument("--dest", type=Path, default=Path("data/mendeley_7y943f6wf8"))
    args = p.parse_args(argv)

    if args.from_local is not None:
        return from_local(args.from_local)
    return from_mendeley(args.dataset_id, args.version, args.dest)


if __name__ == "__main__":
    raise SystemExit(main())
