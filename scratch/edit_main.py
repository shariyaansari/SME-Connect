import os

filepath = 'backend/app/main.py'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "from app.modules.workflows.router import router as workflows_router" in line:
        new_lines.append(line)
        new_lines.append("from app.modules.templates.router import router as templates_router\n")
    elif "app.include_router(workflows_router)" in line:
        new_lines.append(line)
        new_lines.append("app.include_router(templates_router)\n")
    else:
        new_lines.append(line)

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
