#!/usr/bin/env python3
"""
Sample Hash Testing Module
---------------------------
Demonstrates testing the generated wordlist against sample password hashes.

Two modes:
  1) --make-hashes   : create a local "sample_hashes.txt" by hashing a few
                        passwords derived from a test profile (simulating a
                        weak-password victim) using MD5 and SHA-1.
  2) --crack          : run a dictionary attack -- hash every candidate word
                        in the wordlist and check it against the sample
                        hash file, reporting hit rate and time taken.

This is a LOCAL, SELF-GENERATED demonstration for lab/report purposes.
No real-world, third-party, or unauthorized hashes are used or targeted.
"""

import argparse
import hashlib
import time
from pathlib import Path


def md5_hash(word: str) -> str:
    return hashlib.md5(word.encode("utf-8")).hexdigest()


def sha1_hash(word: str) -> str:
    return hashlib.sha1(word.encode("utf-8")).hexdigest()


HASH_FUNCS = {"md5": md5_hash, "sha1": sha1_hash}


def make_sample_hashes(passwords, output_path):
    """
    Create a sample_hashes.txt file in the format:
        <algorithm>:<hash>:<plaintext-for-reference-only>

    The plaintext column exists ONLY so the report/grader can verify the
    demo is working; in a real test you would not have this column.
    """
    lines = []
    for pw in passwords:
        lines.append(f"md5:{md5_hash(pw)}:{pw}")
        lines.append(f"sha1:{sha1_hash(pw)}:{pw}")
    Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[+] Wrote {len(lines)} sample hashes to {output_path}")


def load_sample_hashes(path):
    entries = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        algo, hashval, *rest = line.split(":")
        entries.append({"algo": algo, "hash": hashval, "plain_ref": rest[0] if rest else None})
    return entries


def crack(wordlist_path, hashes_path, report_path=None):
    wordlist = Path(wordlist_path).read_text(encoding="utf-8").splitlines()
    targets = load_sample_hashes(hashes_path)

    # Index targets by algorithm for fast lookup: hash -> entry
    index_by_algo = {}
    for t in targets:
        index_by_algo.setdefault(t["algo"], {})[t["hash"]] = t

    cracked = []
    cracked_hash_keys = set()  # (algo, hash) pairs already solved
    start = time.perf_counter()

    for word in wordlist:
        for algo, func in HASH_FUNCS.items():
            bucket = index_by_algo.get(algo)
            if not bucket:
                continue
            h = func(word)
            key = (algo, h)
            if h in bucket and key not in cracked_hash_keys:
                cracked.append({**bucket[h], "found_word": word})
                cracked_hash_keys.add(key)

    elapsed = time.perf_counter() - start

    total = len(targets)
    hit = len(cracked)
    lines = []
    lines.append("=== Dictionary Attack Report ===")
    lines.append(f"Wordlist size      : {len(wordlist)} candidates")
    lines.append(f"Target hashes      : {total}")
    lines.append(f"Cracked            : {hit} ({(hit/total*100 if total else 0):.1f}%)")
    lines.append(f"Time taken         : {elapsed:.4f} seconds")
    lines.append("")
    for c in cracked:
        verified = "OK" if c["plain_ref"] == c["found_word"] else "mismatch?"
        lines.append(f"  [{c['algo']}] {c['hash']}  =>  '{c['found_word']}'  ({verified})")

    not_cracked = [t for t in targets if (t["algo"], t["hash"]) not in cracked_hash_keys]
    if not_cracked:
        lines.append("")
        lines.append("Hashes NOT cracked by this wordlist:")
        for t in not_cracked:
            lines.append(f"  [{t['algo']}] {t['hash']}")

    report = "\n".join(lines)
    print(report)
    if report_path:
        Path(report_path).write_text(report + "\n", encoding="utf-8")
        print(f"\n[+] Report saved to {report_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate and test sample hashes against a wordlist.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_make = sub.add_parser("make-hashes", help="Create sample_hashes.txt from test passwords")
    p_make.add_argument("--passwords", nargs="+", required=True,
                         help="Plaintext passwords to hash (simulated weak-password victim)")
    p_make.add_argument("-o", "--output", default="sample_hashes.txt")

    p_crack = sub.add_parser("crack", help="Run dictionary attack using a wordlist")
    p_crack.add_argument("--wordlist", required=True)
    p_crack.add_argument("--hashes", required=True)
    p_crack.add_argument("--report", default=None)

    args = parser.parse_args()

    if args.cmd == "make-hashes":
        make_sample_hashes(args.passwords, args.output)
    elif args.cmd == "crack":
        crack(args.wordlist, args.hashes, args.report)


if __name__ == "__main__":
    main()
