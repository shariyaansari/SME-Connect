import os

filepath = 'frontend/src/components/TemplatesView.jsx'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Add import
content = content.replace("import { api } from '../api';", "import { api } from '../api';\nimport TemplateDetailView from './TemplateDetailView';")

# Add state
content = content.replace("const [searchQuery, setSearchQuery] = useState('');", "const [searchQuery, setSearchQuery] = useState('');\n  const [selectedTemplateId, setSelectedTemplateId] = useState(null);")

# Add selectedTemplateId logic
old_return = """  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '20px 0' }}>"""

new_return = """  if (selectedTemplateId) {
    return (
      <TemplateDetailView 
        templateId={selectedTemplateId} 
        onBack={() => setSelectedTemplateId(null)} 
      />
    );
  }

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '20px 0' }}>"""

content = content.replace(old_return, new_return)

# Change button click
old_click = """onClick={() => {
                      // Visual only for 3A.4 MVP
                      alert(`Use Template: ${template.name}\\n\\nIn the next phase, this will open the guided setup wizard.`);
                    }}"""

new_click = """onClick={() => setSelectedTemplateId(template.id)}"""

content = content.replace(old_click, new_click)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
