import os

filepath = 'frontend/src/components/TemplatesView.jsx'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "import { api } from '../api';" in line:
        new_lines.append(line)
        new_lines.append("import TemplateDetailView from './TemplateDetailView';\n")
    elif "const [searchQuery, setSearchQuery] = useState('');" in line:
        new_lines.append(line)
        new_lines.append("  const [selectedTemplateId, setSelectedTemplateId] = useState(null);\n")
    elif "return (" in line and "div style={{ maxWidth: '1000px', margin: '0 auto', padding: '20px 0' }}>" in lines[lines.index(line) + 1]:
        # Handle the top level return
        new_lines.append(line)
        new_lines.append("    <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '20px 0' }}>\n")
        new_lines.append("      {selectedTemplateId ? (\n")
        new_lines.append("        <TemplateDetailView \n")
        new_lines.append("          templateId={selectedTemplateId} \n")
        new_lines.append("          onBack={() => setSelectedTemplateId(null)} \n")
        new_lines.append("        />\n")
        new_lines.append("      ) : (\n")
        new_lines.append("        <>\n")
    elif "alert(`Use Template: ${template.name}\\n\\nIn the next phase, this will open the guided setup wizard.`);" in line:
        new_lines.append("                      setSelectedTemplateId(template.id);\n")
    else:
        new_lines.append(line)

# Handle the closing div for the non-detail view
new_lines.insert(-2, "        </>\n      )}\n")
# Wait, this logic for the return is a bit messy. Let's just rewrite the return block cleanly.

