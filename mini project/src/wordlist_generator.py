#!/usr/bin/env python3
"""
Custom Wordlist Generator with Mangling Rules
----------------------------------------------
A CUPP-style (Common User Passwords Profiler) generator that builds a
candidate password wordlist from personal profile hints (names, nicknames,
dates, pet/company names, keywords) and then "mangles" each base word using
leetspeak substitution, case variation, and suffix/prefix rules.

Educational / authorized-testing use only. See README.md for scope.

Usage:
    python wordlist_generator.py --interactive
    python wordlist_generator.py --profile samples/sample_profile.json -o wordlist.txt
"""

import argparse
import itertools
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# --------------------------------------------------------------------------
# 1. CONFIGURATION: mangling rule tables
# --------------------------------------------------------------------------

# Leetspeak substitution map. Each key maps to a list of possible
# replacements so we can generate more than one leet variant per word.
LEET_MAP = {
    "a": ["4", "@"],
    "e": ["3"],
    "i": ["1", "!"],
    "o": ["0"],
    "s": ["5", "$"],
    "t": ["7"],
    "l": ["1"],
    "b": ["8"],
    "g": ["9"],
}

# Common low/medium/high rule-set sizes. "level" controls how aggressively
# we expand suffixes/years/specials so the list doesn't explode by default.
SUFFIX_NUMBERS_BASIC = ["1", "12", "123", "007", "0"]
SUFFIX_NUMBERS_MEDIUM = [str(n) for n in range(0, 100)]
SPECIAL_SUFFIXES = ["!", "@", "#", "$", "*", "!!", "@#", "123!"]

CURRENT_YEAR = datetime.now().year
YEAR_RANGE_BASIC = [str(y) for y in range(CURRENT_YEAR - 10, CURRENT_YEAR + 1)]
YEAR_RANGE_MEDIUM = [str(y) for y in range(1960, CURRENT_YEAR + 1)]

# Safety cap: never let a single run of this educational tool silently
# produce an unbounded file. Raise with --max-words if you really need to.
DEFAULT_MAX_WORDS = 200_000


# --------------------------------------------------------------------------
# 2. PROFILE HANDLING
# --------------------------------------------------------------------------

def load_profile_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def profile_from_interview():
    """CUPP-style interactive questionnaire."""
    print("=== Profile-based Wordlist Generator ===")
    print("Leave a field blank and press Enter to skip it.\n")

    def ask(prompt):
        return input(prompt).strip()

    profile = {
        "first_name": ask("First name: "),
        "last_name": ask("Last name: "),
        "nickname": ask("Nickname: "),
        "birth_date": ask("Birth date (DD MM YYYY): "),
        "partner_name": ask("Partner / spouse name: "),
        "partner_birth_date": ask("Partner birth date (DD MM YYYY): "),
        "pet_name": ask("Pet name: "),
        "company": ask("Company / school name: "),
        "keywords": ask("Other keywords (comma separated, e.g. favourite team, city): "),
    }
    return profile


def extract_date_tokens(date_str):
    """Turn 'DD MM YYYY' into useful fragments: dd, mm, yyyy, yy, ddmm, mmyyyy..."""
    tokens = []
    if not date_str:
        return tokens
    parts = re.split(r"[\s/\-\.]+", date_str.strip())
    parts = [p for p in parts if p]
    if len(parts) >= 3:
        dd, mm, yyyy = parts[0], parts[1], parts[2]
        yy = yyyy[-2:] if len(yyyy) == 4 else yyyy
        tokens += [dd, mm, yyyy, yy, dd + mm, mm + dd, dd + yy, yy + mm, dd + mm + yyyy, dd + mm + yy]
    elif len(parts) == 1 and parts[0].isdigit():
        tokens.append(parts[0])
    return list(dict.fromkeys(tokens))  # dedupe, preserve order


def base_words_from_profile(profile):
    """Collect every 'raw' token we can mine from profile hints."""
    words = []

    for key in ("first_name", "last_name", "nickname", "partner_name", "pet_name", "company"):
        val = profile.get(key, "")
        if val:
            words.append(val)

    if profile.get("keywords"):
        words += [w.strip() for w in profile["keywords"].split(",") if w.strip()]

    # Name combinations (firstname+lastname, initials, etc.)
    fn, ln = profile.get("first_name", ""), profile.get("last_name", "")
    if fn and ln:
        words += [fn + ln, ln + fn, fn[0] + ln, fn + ln[0]]

    words = [w for w in words if w]
    return list(dict.fromkeys(words))


def date_tokens_from_profile(profile):
    tokens = []
    tokens += extract_date_tokens(profile.get("birth_date", ""))
    tokens += extract_date_tokens(profile.get("partner_birth_date", ""))
    return list(dict.fromkeys(tokens))


# --------------------------------------------------------------------------
# 3. MANGLING RULES
# --------------------------------------------------------------------------

def case_variants(word):
    """Common case mangling: lower, UPPER, Capitalized, tOGGLE."""
    variants = {word.lower(), word.upper(), word.capitalize()}
    toggled = "".join(c.lower() if c.isupper() else c.upper() for c in word)
    variants.add(toggled)
    return variants


def leet_variants(word, max_subs_per_word=2):
    """
    Generate leetspeak variants. To avoid a combinatorial explosion we:
      1) always produce the 'fully leeted' version (first substitution for
         every eligible character), and
      2) produce up to `max_subs_per_word` additional variants using the
         alternate substitution characters (e.g. 'a' -> '@' instead of '4').
    """
    lower = word.lower()
    eligible_positions = [i for i, c in enumerate(lower) if c in LEET_MAP]
    if not eligible_positions:
        return {word}

    variants = set()

    # Variant A: first-choice leet char everywhere
    chars = list(word)
    for i in eligible_positions:
        chars[i] = LEET_MAP[lower[i]][0]
    variants.add("".join(chars))

    # Variant(s) using alternate leet characters, capped
    produced = 0
    for alt_index in range(1, 3):  # try 2nd and 3rd choice substitutions
        if produced >= max_subs_per_word:
            break
        chars = list(word)
        changed = False
        for i in eligible_positions:
            options = LEET_MAP[lower[i]]
            if len(options) > alt_index:
                chars[i] = options[alt_index]
                changed = True
        if changed:
            variants.add("".join(chars))
            produced += 1

    return variants


def apply_suffixes(word, suffixes):
    return {word + s for s in suffixes} | {word}


def apply_prefixes(word, prefixes):
    return {p + word for p in prefixes} | {word}


# --------------------------------------------------------------------------
# 4. GENERATOR PIPELINE
# --------------------------------------------------------------------------

def generate_wordlist(profile, level="basic", max_words=DEFAULT_MAX_WORDS,
                       use_leet=True, use_case=True, use_dates=True,
                       use_specials=True, min_length=4):
    """
    Build the final mangled wordlist.

    level: "basic" (small, fast, realistic CUPP default) or
           "medium" (adds a much wider number/year suffix range).
    """
    base_words = base_words_from_profile(profile)
    date_tokens = date_tokens_from_profile(profile) if use_dates else []

    if level == "medium":
        number_suffixes = SUFFIX_NUMBERS_MEDIUM
        year_suffixes = YEAR_RANGE_MEDIUM
    else:
        number_suffixes = SUFFIX_NUMBERS_BASIC
        year_suffixes = YEAR_RANGE_BASIC

    suffix_pool = list(dict.fromkeys(number_suffixes + year_suffixes + date_tokens))
    if use_specials:
        suffix_pool += SPECIAL_SUFFIXES

    results = set()

    # Step 1: expand each base word with case variants
    stage1 = set()
    for w in base_words:
        stage1.add(w)
        if use_case:
            stage1 |= case_variants(w)

    # Step 2: add leetspeak variants of every case-mangled word
    stage2 = set(stage1)
    if use_leet:
        for w in list(stage1):
            stage2 |= leet_variants(w)

    # Step 3: apply suffixes (numbers / years / dates / specials)
    for w in stage2:
        results.add(w)
        for suf in suffix_pool:
            results.add(w + suf)
            if len(results) >= max_words:
                break
        if len(results) >= max_words:
            break

    # Step 4: two-word combinations for small profiles (name+pet, name+date)
    if len(base_words) <= 12:
        for a, b in itertools.permutations(base_words, 2):
            combo = a + b
            results.add(combo)
            for suf in date_tokens[:6]:  # keep this bounded
                results.add(combo + suf)
            if len(results) >= max_words:
                break

    # Final filter: minimum length (classic password-policy realism) + cap
    results = {w for w in results if len(w) >= min_length}
    results = sorted(results, key=lambda w: (len(w), w))  # shortest/likeliest first
    return results[:max_words]


# --------------------------------------------------------------------------
# 5. CLI
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="CUPP-style custom wordlist generator with mangling rules.")
    parser.add_argument("--profile", help="Path to a profile JSON file")
    parser.add_argument("--interactive", action="store_true", help="Build profile via interactive questions")
    parser.add_argument("-o", "--output", default="wordlist.txt", help="Output wordlist file")
    parser.add_argument("--level", choices=["basic", "medium"], default="basic",
                         help="basic = small realistic set, medium = wide year/number ranges")
    parser.add_argument("--max-words", type=int, default=DEFAULT_MAX_WORDS)
    parser.add_argument("--min-length", type=int, default=4)
    parser.add_argument("--no-leet", action="store_true")
    parser.add_argument("--no-case", action="store_true")
    parser.add_argument("--no-dates", action="store_true")
    parser.add_argument("--no-specials", action="store_true")
    args = parser.parse_args()

    if args.interactive:
        profile = profile_from_interview()
    elif args.profile:
        profile = load_profile_json(args.profile)
    else:
        print("Error: provide --profile <file.json> or --interactive", file=sys.stderr)
        sys.exit(1)

    wordlist = generate_wordlist(
        profile,
        level=args.level,
        max_words=args.max_words,
        use_leet=not args.no_leet,
        use_case=not args.no_case,
        use_dates=not args.no_dates,
        use_specials=not args.no_specials,
        min_length=args.min_length,
    )

    Path(args.output).write_text("\n".join(wordlist) + "\n", encoding="utf-8")
    print(f"[+] Base profile tokens   : {len(base_words_from_profile(profile))}")
    print(f"[+] Generated wordlist    : {len(wordlist)} candidate passwords")
    print(f"[+] Saved to              : {args.output}")


if __name__ == "__main__":
    main()
