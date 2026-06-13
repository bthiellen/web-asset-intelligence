/**
 * ASSET INTEL - CLIENT-SIDE CONTROLLER AND VIS.JS NETWORK MANAGER
 */

document.addEventListener('DOMContentLoaded', () => {
  // Application State
  const state = {
    network: null,
    nodesDataSet: new vis.DataSet([]),
    edgesDataSet: new vis.DataSet([]),
    rawNodes: [],
    rawEdges: [],
    physicsEnabled: true,
    selectedNodeId: null,
    selectedFile: null
  };

  // Theme configuration for node visual groups
  const nodeStyles = {
    Domain: {
      color: { background: '#0891b2', border: '#06b6d4', highlight: { background: '#0e7490', border: '#22d3ee' } },
      shape: 'dot',
      size: 16
    },
    IP: {
      color: { background: '#4f46e5', border: '#6366f1', highlight: { background: '#3730a3', border: '#818cf8' } },
      shape: 'dot',
      size: 14
    },
    Certificate: {
      color: { background: '#d97706', border: '#f59e0b', highlight: { background: '#92400e', border: '#fbbf24' } },
      shape: 'dot',
      size: 12
    },
    Entity: {
      color: { background: '#059669', border: '#10b981', highlight: { background: '#065f46', border: '#34d399' } },
      shape: 'dot',
      size: 18
    },
    Address: {
      color: { background: '#e11d48', border: '#f43f5e', highlight: { background: '#9f1239', border: '#fb7185' } },
      shape: 'dot',
      size: 12
    },
    Unknown: {
      color: { background: '#4b5563', border: '#9ca3af', highlight: { background: '#374151', border: '#d1d5db' } },
      shape: 'dot',
      size: 12
    }
  };

  // DOM Elements
  const analyzeForm = document.getElementById('analyzeForm');
  const targetDomainInput = document.getElementById('targetDomain');
  const analyzeBtn = document.getElementById('analyzeBtn');
  const analyzeSpinner = document.getElementById('analyzeSpinner');
  
  const uploadForm = document.getElementById('uploadForm');
  const filingFileInput = document.getElementById('filingFile');
  const dropZone = document.getElementById('dropZone');
  const fileInfo = document.getElementById('fileInfo');
  const selectedFileName = document.getElementById('selectedFileName');
  const removeFileBtn = document.getElementById('removeFileBtn');
  const uploadBtn = document.getElementById('uploadBtn');
  const uploadSpinner = document.getElementById('uploadSpinner');

  const inspectorEmpty = document.getElementById('inspectorEmpty');
  const inspectorContent = document.getElementById('inspectorContent');
  const nodeTypeBadge = document.getElementById('nodeTypeBadge');
  const nodeTitle = document.getElementById('nodeTitle');
  const nodePropertiesBody = document.getElementById('nodePropertiesBody');

  const graphSearchInput = document.getElementById('graphSearchInput');
  const clearSearchBtn = document.getElementById('clearSearchBtn');
  const resetZoomBtn = document.getElementById('resetZoomBtn');
  const togglePhysicsBtn = document.getElementById('togglePhysicsBtn');
  
  const canvasLoader = document.getElementById('canvasLoader');
  const networkCanvas = document.getElementById('networkCanvas');
  const statusToast = document.getElementById('statusToast');
  const statusToastText = document.getElementById('statusToastText');

  // Initialization
  initNetwork();
  loadGraphData();
  setupEventHandlers();

  // Initialize Vis.js Network Options
  function initNetwork() {
    const container = networkCanvas;
    const data = {
      nodes: state.nodesDataSet,
      edges: state.edgesDataSet
    };

    const options = {
      nodes: {
        font: {
          color: '#cbd5e1',
          size: 11,
          face: 'Outfit',
          strokeWidth: 2,
          strokeColor: '#090d16'
        },
        borderWidth: 1.5,
        shadow: {
          enabled: true,
          color: 'rgba(0,0,0,0.4)',
          size: 5,
          x: 0,
          y: 3
        }
      },
      edges: {
        color: {
          color: 'rgba(100, 116, 139, 0.25)',
          highlight: 'rgba(6, 182, 212, 0.6)',
          hover: 'rgba(6, 182, 212, 0.4)'
        },
        font: {
          color: '#64748b',
          size: 9,
          face: 'Space Grotesk',
          strokeWidth: 1,
          strokeColor: '#090d16',
          align: 'middle'
        },
        arrows: {
          to: { enabled: true, scaleFactor: 0.8 }
        },
        width: 1,
        smooth: {
          enabled: true,
          type: 'cubicBezier',
          forceDirection: 'none',
          roundness: 0.4
        }
      },
      physics: {
        enabled: state.physicsEnabled,
        barnesHut: {
          gravitationalConstant: -1800,
          centralGravity: 0.15,
          springLength: 120,
          springConstant: 0.04,
          damping: 0.09,
          avoidOverlap: 0.3
        },
        stabilization: {
          enabled: true,
          iterations: 150,
          updateInterval: 25,
          onlyDynamicEdges: false,
          fit: true
        }
      },
      interaction: {
        hover: true,
        tooltipDelay: 200,
        zoomView: true,
        dragView: true
      }
    };

    state.network = new vis.Network(container, data, options);

    // Node selection event
    state.network.on('selectNode', (params) => {
      if (params.nodes.length > 0) {
        state.selectedNodeId = params.nodes[0];
        displayNodeDetails(state.selectedNodeId);
      }
    });

    // Node deselection event
    state.network.on('deselectNode', () => {
      state.selectedNodeId = null;
      hideNodeDetails();
    });
  }

  // Load telemetries from API
  async function loadGraphData() {
    showLoader(true);
    try {
      const response = await fetch('/api/graph');
      if (!response.ok) {
        throw new Error(`Failed to fetch graph data: ${response.statusText}`);
      }
      const data = await response.json();
      state.rawNodes = data.nodes || [];
      state.rawEdges = data.edges || [];

      // Transform raw nodes to vis.js format
      const visNodes = state.rawNodes.map(node => {
        const style = nodeStyles[node.type] || nodeStyles.Unknown;
        
        // Determine label length limit
        let displayLabel = node.label;
        if (node.type === 'Certificate' && displayLabel.length > 15) {
          displayLabel = displayLabel.substring(0, 10) + '...';
        }
        
        return {
          id: node.id,
          label: displayLabel,
          title: `${node.type}: ${node.id}`,
          ...style
        };
      });

      // Transform raw edges to vis.js format
      const visEdges = state.rawEdges.map(edge => ({
        id: edge.id,
        from: edge.from,
        to: edge.to,
        label: edge.label
      }));

      // Update DataSets
      state.nodesDataSet.clear();
      state.edgesDataSet.clear();
      
      state.nodesDataSet.add(visNodes);
      state.edgesDataSet.add(visEdges);

      // Re-apply select node if it was previously selected and still exists
      if (state.selectedNodeId && state.nodesDataSet.get(state.selectedNodeId)) {
        state.network.selectNodes([state.selectedNodeId]);
        displayNodeDetails(state.selectedNodeId);
      } else {
        hideNodeDetails();
      }

      showToast('Graph synchronized successfully', 'success');
    } catch (error) {
      console.error(error);
      showToast(error.message, 'error');
    } finally {
      showLoader(false);
    }
  }

  // Set up Event Handlers
  function setupEventHandlers() {
    // Analyze domain target form
    analyzeForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const domain = targetDomainInput.value.trim();
      if (!domain) return;

      setAnalyzingState(true);
      showToast(`Passive discovery initialized for ${domain}`, 'info');

      try {
        const response = await fetch('/api/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ domain })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
          throw new Error(data.detail || 'Target analysis failed.');
        }

        showToast(data.message || `Successfully mapped ${domain}`, 'success');
        targetDomainInput.value = '';
        
        // Reload telemetry
        await loadGraphData();

        // Focus on the newly added domain node if it exists
        if (state.nodesDataSet.get(domain)) {
          state.selectedNodeId = domain;
          state.network.selectNodes([domain]);
          displayNodeDetails(domain);
          focusNode(domain);
        }
      } catch (error) {
        console.error(error);
        showToast(error.message, 'error');
      } finally {
        setAnalyzingState(false);
      }
    });

    // Ingest filing Form
    uploadForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!state.selectedFile) return;

      setUploadingState(true);
      showToast('Processing corporate filing upload...', 'info');

      const formData = new FormData();
      formData.append('file', state.selectedFile);

      try {
        const response = await fetch('/api/upload', {
          method: 'POST',
          body: formData
        });
        
        const data = await response.json();
        
        if (!response.ok) {
          throw new Error(data.detail || 'Filing upload processing failed.');
        }

        showToast(data.message || 'Filing successfully mapped and added.', 'success');
        resetUploadForm();
        
        // Reload telemetry
        await loadGraphData();
      } catch (error) {
        console.error(error);
        showToast(error.message, 'error');
      } finally {
        setUploadingState(false);
      }
    });

    // Drag-and-drop setup for upload files
    ['dragenter', 'dragover'].forEach(eventName => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
      }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
      }, false);
    });

    dropZone.addEventListener('drop', (e) => {
      const dt = e.dataTransfer;
      const files = dt.files;
      if (files.length > 0) {
        handleFileSelect(files[0]);
      }
    });

    filingFileInput.addEventListener('change', (e) => {
      if (e.target.files.length > 0) {
        handleFileSelect(e.target.files[0]);
      }
    });

    removeFileBtn.addEventListener('click', () => {
      resetUploadForm();
    });

    // Graph UI control events
    resetZoomBtn.addEventListener('click', () => {
      state.network.fit({ animation: { duration: 800, easingFunction: 'easeInOutQuad' } });
      showToast('Recentered view fit', 'info');
    });

    togglePhysicsBtn.addEventListener('click', () => {
      state.physicsEnabled = !state.physicsEnabled;
      state.network.setOptions({ physics: { enabled: state.physicsEnabled } });
      
      if (state.physicsEnabled) {
        togglePhysicsBtn.classList.add('active');
        showToast('Physics layout enabled', 'info');
      } else {
        togglePhysicsBtn.classList.remove('active');
        showToast('Physics layout frozen', 'info');
      }
    });

    // Graph Search features
    graphSearchInput.addEventListener('input', () => {
      const query = graphSearchInput.value.trim().toLowerCase();
      if (query.length > 0) {
        clearSearchBtn.style.display = 'block';
        highlightNodes(query);
      } else {
        clearSearchBtn.style.display = 'none';
        resetNodeHighlights();
      }
    });

    clearSearchBtn.addEventListener('click', () => {
      graphSearchInput.value = '';
      clearSearchBtn.style.display = 'none';
      resetNodeHighlights();
    });
  }

  // File selection display helpers
  function handleFileSelect(file) {
    if (file.type !== 'application/json' && !file.name.endsWith('.json')) {
      showToast('Only JSON filing exports are accepted.', 'error');
      return;
    }
    state.selectedFile = file;
    selectedFileName.textContent = file.name;
    fileInfo.style.display = 'flex';
    dropZone.style.display = 'none';
  }

  function resetUploadForm() {
    state.selectedFile = null;
    filingFileInput.value = '';
    fileInfo.style.display = 'none';
    dropZone.style.display = 'flex';
  }

  // Focus and Zoom onto a Node
  function focusNode(nodeId) {
    state.network.focus(nodeId, {
      scale: 1.15,
      animation: {
        duration: 1000,
        easingFunction: 'easeInOutQuad'
      }
    });
  }

  // Highlight Nodes Matching Search Queries
  function highlightNodes(query) {
    const matches = [];
    const updates = [];

    state.rawNodes.forEach(node => {
      let isMatch = false;
      const style = nodeStyles[node.type] || nodeStyles.Unknown;
      
      // Look up target string properties
      if (node.id.toLowerCase().includes(query)) {
        isMatch = true;
      } else {
        // Search inside properties dictionary
        for (const [key, value] of Object.entries(node.properties || {})) {
          if (value && String(value).toLowerCase().includes(query)) {
            isMatch = true;
            break;
          }
        }
      }

      if (isMatch) {
        matches.push(node.id);
        updates.push({
          id: node.id,
          color: {
            background: style.color.background,
            border: '#ffffff',
            highlight: style.color.highlight
          },
          borderWidth: 3
        });
      } else {
        // Dim non-matching nodes
        updates.push({
          id: node.id,
          color: {
            background: 'rgba(30, 41, 59, 0.15)',
            border: 'rgba(255, 255, 255, 0.03)',
            highlight: style.color.highlight
          },
          borderWidth: 1
        });
      }
    });

    state.nodesDataSet.update(updates);

    // If there is exactly one match or a top match, focus onto it
    if (matches.length === 1) {
      focusNode(matches[0]);
      state.selectedNodeId = matches[0];
      state.network.selectNodes([matches[0]]);
      displayNodeDetails(matches[0]);
    }
  }

  // Reset Highlights after Search cleared
  function resetNodeHighlights() {
    const updates = state.rawNodes.map(node => {
      const style = nodeStyles[node.type] || nodeStyles.Unknown;
      return {
        id: node.id,
        color: style.color,
        borderWidth: 1.5
      };
    });
    state.nodesDataSet.update(updates);
  }

  // Display Node properties in Inspector Sidebar
  function displayNodeDetails(nodeId) {
    const nodeData = state.rawNodes.find(n => n.id === nodeId);
    if (!nodeData) return;

    // Set badge content and title
    nodeTypeBadge.textContent = nodeData.type;
    nodeTitle.textContent = nodeData.id;

    // Reset Badge styling
    nodeTypeBadge.className = 'badge';
    if (nodeData.type === 'Domain') nodeTypeBadge.style.background = 'rgba(6, 182, 212, 0.15)', nodeTypeBadge.style.color = '#06b6d4', nodeTypeBadge.style.borderColor = 'rgba(6, 182, 212, 0.2)';
    else if (nodeData.type === 'IP') nodeTypeBadge.style.background = 'rgba(99, 102, 241, 0.15)', nodeTypeBadge.style.color = '#818cf8', nodeTypeBadge.style.borderColor = 'rgba(99, 102, 241, 0.2)';
    else if (nodeData.type === 'Certificate') nodeTypeBadge.style.background = 'rgba(245, 158, 11, 0.15)', nodeTypeBadge.style.color = '#fbbf24', nodeTypeBadge.style.borderColor = 'rgba(245, 158, 11, 0.2)';
    else if (nodeData.type === 'Entity') nodeTypeBadge.style.background = 'rgba(16, 185, 129, 0.15)', nodeTypeBadge.style.color = '#34d399', nodeTypeBadge.style.borderColor = 'rgba(16, 185, 129, 0.2)';
    else if (nodeData.type === 'Address') nodeTypeBadge.style.background = 'rgba(244, 63, 94, 0.15)', nodeTypeBadge.style.color = '#fb7185', nodeTypeBadge.style.borderColor = 'rgba(244, 63, 94, 0.2)';

    // Render table rows
    nodePropertiesBody.innerHTML = '';
    
    // Sort keys logically
    const props = nodeData.properties || {};
    const keys = Object.keys(props).sort((a, b) => {
      // Keep main identifiers first, system timestamps last
      if (a === 'id' || a === 'name' || a === 'address') return -1;
      if (b === 'id' || b === 'name' || b === 'address') return 1;
      if (a.endsWith('_at')) return 1;
      if (b.endsWith('_at')) return -1;
      return a.localeCompare(b);
    });

    keys.forEach(key => {
      const val = props[key];
      if (val === null || val === undefined) return;

      const row = document.createElement('tr');
      const keyCell = document.createElement('td');
      keyCell.style.fontWeight = '600';
      keyCell.style.color = 'var(--text-muted)';
      keyCell.textContent = formatKeyName(key);

      const valCell = document.createElement('td');
      valCell.innerHTML = formatValueContent(key, val);

      row.appendChild(keyCell);
      row.appendChild(valCell);
      nodePropertiesBody.appendChild(row);
    });

    inspectorEmpty.style.display = 'none';
    inspectorContent.style.display = 'flex';
  }

  function hideNodeDetails() {
    inspectorEmpty.style.display = 'flex';
    inspectorContent.style.display = 'none';
  }

  // UI Key property formatting
  function formatKeyName(key) {
    return key
      .replace(/_/g, ' ')
      .replace(/\b\w/g, c => c.toUpperCase());
  }

  // UI Value property formatting
  function formatValueContent(key, val) {
    // If it's a timestamp (e.g. created_at, updated_at, timestamp, valid_from)
    if ((key.endsWith('_at') || key === 'timestamp' || key === 'valid_from' || key === 'valid_to') && typeof val === 'number') {
      // Millisecond timestamps
      return new Date(val).toLocaleString();
    }
    
    if (typeof val === 'string' && (val.startsWith('202') || val.includes('T')) && !isNaN(Date.parse(val))) {
      return new Date(val).toLocaleString();
    }

    // List rendering
    if (Array.isArray(val)) {
      if (val.length === 0) return '<span style="color: var(--text-muted)">empty</span>';
      return `<div style="display: flex; flex-direction: column; gap: 4px;">
        ${val.map(item => `<code style="font-family: var(--font-mono); font-size: 0.75rem; background: rgba(255,255,255,0.04); padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(255,255,255,0.05); display: inline-block;">${item}</code>`).join('')}
      </div>`;
    }

    if (typeof val === 'object' && val !== null) {
      return `<pre style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-secondary); max-height: 80px; overflow-y: auto;">${JSON.stringify(val, null, 2)}</pre>`;
    }

    return String(val);
  }

  // API Call loader overlays
  function showLoader(visible) {
    canvasLoader.style.display = visible ? 'flex' : 'none';
  }

  // Toast status notifier helper
  let toastTimeout = null;
  function showToast(message, type = 'info') {
    // Clear existing timeouts
    if (toastTimeout) {
      clearTimeout(toastTimeout);
    }

    statusToastText.textContent = message;
    statusToast.className = `status-toast show ${type}`;

    toastTimeout = setTimeout(() => {
      statusToast.classList.remove('show');
    }, 4500);
  }

  // Loader toggles for forms submitting
  function setAnalyzingState(isAnalyzing) {
    analyzeBtn.disabled = isAnalyzing;
    targetDomainInput.disabled = isAnalyzing;
    analyzeSpinner.style.display = isAnalyzing ? 'inline-block' : 'none';
  }

  function setUploadingState(isUploading) {
    uploadBtn.disabled = isUploading;
    removeFileBtn.disabled = isUploading;
    uploadSpinner.style.display = isUploading ? 'inline-block' : 'none';
  }
});
