import os

filepath = 'frontend/src/components/Header.jsx'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "{ id: 'workflows', label: 'Workflows' }," in line:
        new_lines.append("            { id: 'templates', label: 'Templates' },\n")
        new_lines.append(line)
    else:
        new_lines.append(line)

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
