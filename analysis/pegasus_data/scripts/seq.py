import re, glob, sys
FIELDS = ("unit_price", "payment_days", "effective_date", "index_clause", "contract_months", "lead_time_days", "volume_per_year", "tooling_eur", "ppm_commitment", "chargeback_eur_per_complaint", "incoterm")
for pat in sys.argv[1:]:
    for f in sorted(glob.glob(f"traces/{pat}-*.txt")):
        t = open(f).read(); head = t.split("\n", 1)[0]
        print("\n" + head[:230])
        lines = t.split("\n"); i = 0
        while i < len(lines):
            if re.fullmatch(r"(sup:\d+|Buyer)", lines[i]) and i + 2 < len(lines) and lines[i + 2].startswith("round"):
                actor, status, rnd = lines[i], lines[i + 1], lines[i + 2]
                j = i + 3; terms = {}
                while j + 1 < len(lines) and lines[j] in FIELDS:
                    v = lines[j + 1]; terms[lines[j][:5]] = (v[:28] if lines[j] == "index_clause" else v); j += 2
                    if j < len(lines) and re.fullmatch(r"[-+][0-9.]+", lines[j]): j += 1
                blk = "\n".join(lines[j:j + 45])
                claims = re.findall(r"Checked claim\s*\n([a-z_]+)\s*\n:\s*\n(\w+)", blk)
                alt = len(re.findall(r"^alternative", blk, re.M))
                print(f"  r{rnd[6:]} {actor:10} {status:12} {terms} {claims if claims else ''}{' alt=' + str(alt) if alt else ''}")
                i = j
            else:
                i += 1
