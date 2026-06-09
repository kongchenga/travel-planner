"""Check JS syntax more carefully."""
with open("frontend/app.js", "r", encoding="utf-8") as f:
    content = f.read()
    lines = content.split("\n")

# Show lines around 260
print("=== Lines 255-270 ===")
for i in range(254, min(270, len(lines))):
    print(f"{i+1}: {lines[i]}")

print("\n=== Chars 6020-6060 ===")
print(repr(content[6020:6060]))

# Check all double quote pairs
for i, line in enumerate(lines):
    # Count unescaped double quotes
    dq = 0
    skip = False
    for ch in line:
        if ch == '"':
            dq += 1
    if dq % 2 != 0:
        # This might be inside single-quoted string, check that too
        sq = 0
        in_single = False
        for ch in line:
            if ch == "'":
                in_single = not in_single
            elif ch == '"' and not in_single:
                sq += 1
        # This is getting complex. Just report odd double quotes.
        # Actually the issue is likely single quotes inside double-quoted strings
        print(f"Odd dq at line {i+1}: {line[:80]}")
