const fs = require('fs');
const file = 'frontend/src/components/WorkflowsView.jsx';
let content = fs.readFileSync(file, 'utf8');

// Patch activeCount
content = content.replace(/workflows\.filter\(/g, '(workflows || []).filter(');

// Patch workflows.map
content = content.replace(/workflows\.length === 0/g, '(!workflows || workflows.length === 0)');
content = content.replace(/workflows\.map\(/g, '(workflows || []).map(');

// Patch capabilities
content = content.replace(/capabilities\.find\(/g, '(capabilities || []).find(');
content = content.replace(/capabilities\.map\(/g, '(capabilities || []).map(');
content = content.replace(/\?\.supported_triggers\.map/g, '?.supported_triggers?.map');
content = content.replace(/\?\.supported_triggers\.find/g, '?.supported_triggers?.find');
content = content.replace(/cap\.supported_triggers\.find\(/g, '(cap?.supported_triggers || []).find(');

// Patch draftDefinition.steps
content = content.replace(/draftDefinition\.steps\.map\(/g, '(draftDefinition?.steps || []).map(');

// Patch draftDefinition.trigger
content = content.replace(/draftDefinition\.trigger\.event/g, 'draftDefinition?.trigger?.event');
content = content.replace(/draftDefinition\.trigger\.connector/g, 'draftDefinition?.trigger?.connector');

// Patch workflows.find
content = content.replace(/workflows\.find\(/g, '(workflows || []).find(');

fs.writeFileSync(file, content, 'utf8');
console.log("Patched WorkflowsView.jsx successfully");
