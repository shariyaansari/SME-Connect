import os

filepath = 'frontend/src/App.jsx'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "import WorkflowsView from './components/WorkflowsView';" in line:
        new_lines.append(line)
        new_lines.append("import TemplatesView from './components/TemplatesView';\n")
    elif "const [activeTab, setActiveTab] = useState('workflows');" in line:
        new_lines.append("  const [activeTab, setActiveTab] = useState('templates');\n")
    elif "{activeTab === 'workflows' && (" in line:
        new_lines.append("        {activeTab === 'templates' && (\n")
        new_lines.append("          <TemplatesView\n")
        new_lines.append("            onNavigateWorkflows={() => setActiveTab('workflows')}\n")
        new_lines.append("            onNavigateConnectors={() => setActiveTab('connected')}\n")
        new_lines.append("          />\n")
        new_lines.append("        )}\n\n")
        new_lines.append(line)
    else:
        new_lines.append(line)

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
