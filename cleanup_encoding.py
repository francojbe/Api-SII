import re

def clean_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove emojis and non-ascii characters from print statements
    # A simple way is to replace everything > 127 in strings passed to print
    def replace_non_ascii(match):
        text = match.group(0)
        # Keep common accented characters if possible, or just strip them.
        # Let's strip all non-ascii from print statements for maximum reliability.
        return re.sub(r'[^\x00-\x7f]', '', text)

    # Find print(f"...") or print("...") and remove non-ascii inside the string
    cleaned = re.sub(r'print\s*\(\s*f?["\'].*?["\']\s*\)', replace_non_ascii, content, flags=re.DOTALL)
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(cleaned)

clean_file('scraper.py')
clean_file('main.py')
clean_file('auditor_ia.py')
