const fs = require('fs');
let code = fs.readFileSync('frontend/src/components/WorkflowsView.jsx', 'utf8');

// The corrupted characters
code = code.replace(/<div className="metric-tile-value">.*?<\/div>/g, '<div className="metric-tile-value">—</div>');

// The bullet for version
code = code.replace(/v\{wf\.version_number\}.*?\{new Date/g, 'v{wf.version_number} • {new Date');

// The arrows in the step display
code = code.replace(/<span style={{\s*color: 'var\(--text-muted\)',\s*fontSize: '14px',\s*userSelect: 'none',\s*}}>\s*.*?\s*<\/span>/g, `<span style={{ color: 'var(--text-muted)', fontSize: '14px', userSelect: 'none' }}>→</span>`);

fs.writeFileSync('frontend/src/components/WorkflowsView.jsx', code, 'utf8');
console.log("Fixed corrupted characters");
