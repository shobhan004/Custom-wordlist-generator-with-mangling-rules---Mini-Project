# Custom Wordlist Generator with Mangling Rules (CUPP-style)

A small Python toolkit that mirrors the core idea of CUPP (Common User
Passwords Profiler): build a targeted password wordlist from a person's
profile hints, mangle it with realistic human password habits, and test
the result against sample password hashes in a controlled lab setting.

## ⚠️ Ethical use only

This project is built strictly for the Cyber Security Lab mini-project and
for authorized security testing / awareness demonstrations (e.g. testing
your **own** accounts, or systems you have **written permission** to test).
Do **not** use it against accounts, systems, or people without explicit,
documented authorization. Unauthorized password guessing / cracking is
illegal in most jurisdictions (e.g. under India's IT Act, 2000, Sections 43
& 66).

## Folder structure

```
project/
├── src/
│   ├── wordlist_generator.py   # profile -> mangled wordlist
│   └── hash_test.py            # make sample hashes + dictionary attack
├── samples/
│   └── sample_profile.json     # example input profile
├── output/                     # generated wordlist / hashes / reports (demo run)
└── README.md
```

## 1. Generate a wordlist from a profile

Interactive (asks questions like CUPP does):
```bash
python src/wordlist_generator.py --interactive -o wordlist.txt
```

From a JSON profile file:
```bash
python src/wordlist_generator.py --profile samples/sample_profile.json --level basic -o wordlist.txt
```

Profile JSON fields: `first_name, last_name, nickname, birth_date,
partner_name, partner_birth_date, pet_name, company, keywords`.

Useful flags:
| Flag | Purpose |
|---|---|
| `--level basic\|medium` | basic = small realistic suffix/year range; medium = wide range |
| `--no-leet` | disable leetspeak substitution rules |
| `--no-case` | disable case-mangling (UPPER/lower/Capitalized/tOGGLE) |
| `--no-dates` | disable date-derived suffixes |
| `--no-specials` | disable `!@#$` style special-character suffixes |
| `--max-words N` | hard cap on output size (default 200,000) |
| `--min-length N` | drop candidates shorter than N characters |

## 2. Create sample hashes (simulated weak-password victim)

```bash
python src/hash_test.py make-hashes --passwords "Rohan2001" "tommy123" "Priya1408" -o sample_hashes.txt
```
This produces lines of `algorithm:hash:plaintext-for-verification`.

## 3. Run the dictionary attack / test

```bash
python src/hash_test.py crack --wordlist wordlist.txt --hashes sample_hashes.txt --report crack_report.txt
```

Prints and saves a report: wordlist size, number of hashes cracked, hit
rate, and time taken — this is the evidence used in the project report.

## Mangling rules implemented

1. **Leetspeak substitution** — a→4/@, e→3, i→1/!, o→0, s→5/$, t→7, l→1, b→8, g→9
2. **Case mutation** — lower, UPPER, Capitalized, tOGGLEcASE
3. **Suffix rules** — common numbers, years (profile-derived or range-based), date fragments (dd, mm, yyyy, yy, ddmm, mmyyyy, etc.), special characters
4. **Two-token combination** — e.g. `firstname+petname`, `nickname+birthyear`

## Known scope / limitations

See the project report, Section "Scope & Limitations", for the full
discussion — in short: no salted/peppered hash support, no rule chaining
beyond one leet + one suffix pass, no GPU/rainbow-table acceleration, and
no online/network attack capability. This is a **local, educational**
dictionary-generation and testing tool, not a production password auditor.
