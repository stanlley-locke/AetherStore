import os
from pathlib import Path

root = Path('aetherstore')
output = Path('aetherstore-tree.txt')

ignore_dirs = {'.venv', '__pycache__'}

lines = []

def walk(dir_path, prefix=''):
    entries = sorted([e for e in dir_path.iterdir() if e.name not in ignore_dirs], key=lambda e: (not e.is_dir(), e.name.lower()))
    for i, entry in enumerate(entries):
        connector = '└── ' if i == len(entries) - 1 else '├── '
        lines.append(prefix + connector + entry.name)
        if entry.is_dir():
            extension = '    ' if i == len(entries) - 1 else '│   '
            walk(entry, prefix + extension)

lines.append(root.name)
walk(root)

output.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(f'Wrote tree to {output.resolve()}')