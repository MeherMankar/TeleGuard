import ast, os

handlers_dir = r'd:\Vs code\teleguard\teleguard\handlers'
existing_files = set(os.listdir(handlers_dir))

missing = []
for fname in sorted(existing_files):
    if not fname.endswith('.py'):
        continue
    fpath = os.path.join(handlers_dir, fname)
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            src = f.read()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith('.') and '.' not in node.module[1:]:
                    mod_name = node.module.lstrip('.')
                    candidate = mod_name + '.py'
                    if candidate not in existing_files:
                        names = [a.name for a in node.names]
                        missing.append((fname, mod_name, names))
    except Exception as e:
        print(f'PARSE ERROR {fname}: {e}')

if missing:
    for src, mod, names in missing:
        print(f'{src}  ->  from .{mod} import {", ".join(names)}')
else:
    print('No missing local imports found.')
