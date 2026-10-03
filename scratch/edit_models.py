import os

filepath = 'backend/app/database/models.py'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    new_lines.append(line)
    if "organization: Mapped[\"Organization\"] = relationship(\"Organization\", backref=\"workflows\")" in line:
        new_lines.insert(-1, '    template_id: Mapped[int | None] = mapped_column(\n')
        new_lines.insert(-1, '        ForeignKey("templates.id", ondelete="SET NULL"),\n')
        new_lines.insert(-1, '        nullable=True,\n')
        new_lines.insert(-1, '    )\n\n')

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
