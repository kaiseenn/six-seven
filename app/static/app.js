document.addEventListener('DOMContentLoaded', () => {
    const {DeckGL, ColumnLayer, AmbientLight, PointLight, LightingEffect} = deck;

    // Disable right-click context menu on the map container
    document.getElementById('map-container').addEventListener('contextmenu', (e) => {
        e.preventDefault();
        return false;
    });

    // --- Configuration ---
    const MAX_DEPTH = 7000; // Used for inversion logic
    const Z_SCALE = 10;      // Vertical exaggeration factor

    // Biome Colors (RGB arrays for Deck.gl)
    const biomeColors = {
        'slope': [112, 128, 144],      // SlateGray
        'seamount': [255, 107, 107],   // Reddish
        'plain': [70, 130, 180],       // SteelBlue
        'trench': [20, 20, 20],        // Very Dark
        'hydrothermal': [255, 215, 0], // Gold
        'unknown': [136, 136, 136]
    };

    // State
    let currentViewMode = 'biome'; // 'biome' or 'score'
    let maxScore = 1; // Will be updated from data
    const infoDiv = document.getElementById('cell-info');
    let selectedCell = null; // For click-locking
    let highlightedCells = []; // Array of {row, col} for AI highlighting

    // --- Lighting ---
    const ambientLight = new AmbientLight({
        color: [255, 255, 255],
        intensity: 1.0
    });

    const pointLight = new PointLight({
        color: [255, 255, 255],
        intensity: 2.0,
        position: [145.67, -12.34, 80000] // Light from above center
    });

    const lightingEffect = new LightingEffect({ambientLight, pointLight});

    let deckglInstance = null; // Store instance to update layers/camera
    let allData = []; // Store loaded data

    // --- Data Fetching ---
    fetch('/api/grid')
        .then(response => {
            console.log('API response status:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('Data received, length:', data.length);
            if (data.error) {
                console.error('API error:', data.error);
                return;
            }
            // Calculate max score for normalization
            maxScore = Math.max(...data.map(d => d.score || 0));
            if (maxScore <= 0) maxScore = 1; // Avoid div by zero
            console.log('Max score:', maxScore);
            
            allData = data.map(d => ({
                ...d,
                // Inverted depth: Shallow (Seamount) = Tall, Deep (Trench) = Short
                elevation: (MAX_DEPTH - d.depth)
            }));
            console.log('Processed data, length:', allData.length);
            console.log('Initializing DeckGL...');
            initDeckGL(allData);
            console.log('Setting up controls...');
            setupControls(allData);
            console.log('Setting up search...');
            setupSearch();
            console.log('Setting up chat...');
            setupChat();
            console.log('Setting up export...');
            setupExport();
            console.log('Initialization complete!');
        })
        .catch(err => {
            console.error('Error fetching grid:', err);
            alert('Failed to load map data. Check console for details.');
        });

    function initDeckGL(processedData) {
        deckglInstance = new DeckGL({
            container: 'map-container',
            // Remove mapStyle to disable base map
            initialViewState: {
                longitude: 145.8,
                latitude: -12.45,
                zoom: 9,
                pitch: 45,
                bearing: 20
            },
            controller: true,
            effects: [lightingEffect],
            layers: [renderLayer(processedData)],
            getTooltip: ({object}) => object && {
                html: `
                    <div><b>${currentViewMode === 'score' ? 'Score: ' + object.score.toFixed(0) : object.biome.toUpperCase()}</b></div>
                    <div>Depth: ${Math.trunc(object.depth)}m</div>
                    <div>(${object.row}, ${object.col})</div>
                `,
                style: {
                    backgroundColor: '#112240',
                    color: '#ccd6f6',
                    fontSize: '0.8em'
                }
            }
        });
    }

    function renderLayer(data) {
        return new ColumnLayer({
            id: 'grid-cell-layer',
            data: data,
            diskResolution: 4, 
            radius: 500,       
            extruded: true,
            pickable: true,
            elevationScale: Z_SCALE,
            getPosition: d => [d.lon, d.lat],
            getFillColor: d => getCellColor(d),
            getElevation: d => {
                // Max height for highlighted tiles
                if (selectedCell && d.row === selectedCell.row && d.col === selectedCell.col) {
                    return MAX_DEPTH; // Maximum elevation
                }
                if (isHighlighted(d)) {
                    return MAX_DEPTH; // Maximum elevation
                }
                return d.elevation;
            },
            getLineColor: d => {
                if (selectedCell && d.row === selectedCell.row && d.col === selectedCell.col) {
                    return [0, 255, 0]; // Bright green outline
                }
                const highlightMatch = highlightedCells.find(h => h.row === d.row && h.col === d.col);
                if (highlightMatch) {
                    // Use custom color if provided, else default bright green
                    return highlightMatch.color ? highlightMatch.color : [0, 255, 0]; 
                }
                return [0, 0, 0];
            },
            getLineWidth: d => {
                if (selectedCell && d.row === selectedCell.row && d.col === selectedCell.col) {
                    return 20;
                }
                if (isHighlighted(d)) {
                    return 20;
                }
                return 0;
            },
            lineWidthMinPixels: 0,
            
            updateTriggers: {
                getFillColor: [currentViewMode, selectedCell, highlightedCells],
                getElevation: [selectedCell, highlightedCells],
                getLineWidth: [selectedCell, highlightedCells],
                getLineColor: [selectedCell, highlightedCells]
            },

            autoHighlight: true,
            highlightColor: [100, 255, 218, 128],
            
            onHover: ({object}) => {
                if (!selectedCell && object) {
                    updateSidebar(object);
                }
            },
            onClick: ({object}) => {
                if (object) {
                    selectTile(object);
                } else {
                    deselectTile();
                }
            }
        });
    }
    
    function isHighlighted(d) {
        return highlightedCells.some(h => h.row === d.row && h.col === d.col);
    }
    
    function getCellColor(d) {
        // 1. User Selection Priority
        if (selectedCell) {
            if (d.row === selectedCell.row && d.col === selectedCell.col) {
                return [0, 255, 0, 255]; // Bright Green
            }
            // If we have highlights active, check those too
            const highlightMatch = highlightedCells.find(h => h.row === d.row && h.col === d.col);
            if (highlightMatch) {
                // Use custom color if provided, else default bright green
                return highlightMatch.color ? highlightMatch.color : [0, 255, 0, 255];
            }
            // Otherwise dim
            const baseColor = currentViewMode === 'biome' 
                ? (biomeColors[d.biome] || biomeColors['unknown'])
                : getScoreColor(d);
            return [baseColor[0], baseColor[1], baseColor[2], 50]; 
        }
        
        // 2. AI Highlight Priority (No user selection)
        if (highlightedCells.length > 0) {
            const highlightMatch = highlightedCells.find(h => h.row === d.row && h.col === d.col);
            if (highlightMatch) {
                // Use custom color if provided, else default bright green
                return highlightMatch.color ? highlightMatch.color : [0, 255, 0, 255];
            }
            // Dim non-highlighted
            const baseColor = currentViewMode === 'biome' 
                ? (biomeColors[d.biome] || biomeColors['unknown'])
                : getScoreColor(d);
            return [baseColor[0], baseColor[1], baseColor[2], 50];
        }

        // 3. Default - use current view mode
        if (currentViewMode === 'biome') {
            return biomeColors[d.biome] || biomeColors['unknown'];
        } else {
            return getScoreColor(d);
        }
    }
    
    function getScoreColor(d) {
        // Score mode: Brighter colors
        // Map score 0-1 to a vibrant gradient
        // Low (Blue/Purple) -> Mid (Cyan/Green) -> High (Yellow/Orange/Red)
        const n = Math.max(0, (d.score || 0) / maxScore);
        
        // Define stops
        // 0.0: [0, 0, 139] (DarkBlue)
        // 0.33: [0, 255, 255] (Cyan)
        // 0.66: [0, 255, 0] (Lime)
        // 1.0: [255, 255, 0] (Yellow)
        
        let r, g, b;
        
        if (n < 0.33) {
            // DarkBlue to Cyan
            const t = n / 0.33;
            r = 0;
            g = Math.floor(255 * t);
            b = Math.floor(139 + (255 - 139) * t);
        } else if (n < 0.66) {
            // Cyan to Lime
            const t = (n - 0.33) / 0.33;
            r = 0;
            g = 255;
            b = Math.floor(255 * (1 - t));
        } else {
            // Lime to Yellow
            const t = (n - 0.66) / 0.34;
            r = Math.floor(255 * t);
            g = 255;
            b = 0;
        }
        
        return [r, g, b];
    }

    function selectTile(cell) {
        selectedCell = cell;
        updateSidebar(cell);
        updateLayer(allData); // Trigger re-render for highlights
    }

    function deselectTile() {
        selectedCell = null;
        infoDiv.innerHTML = '<p class="stat-label">Hover over a cell to view details.</p>';
        updateLayer(allData);
    }
    
    function setHighlights(tiles) {
        highlightedCells = tiles;
        // Reset selection to let highlights take focus visually
        selectedCell = null;
        updateLayer(allData);
    }
    
    function updateLayer(data) {
        deckglInstance.setProps({
            layers: [renderLayer(data)]
        });
    }
    
    function setupControls(data) {
        const btnBiome = document.getElementById('btn-biome');
        const btnScore = document.getElementById('btn-score');
        
        if (!btnBiome || !btnScore) {
            console.warn('View toggle buttons not found');
            return;
        }
        
        btnBiome.addEventListener('click', () => {
            currentViewMode = 'biome';
            btnBiome.classList.add('active');
            btnScore.classList.remove('active');
            updateLayer(data);
        });

        btnScore.addEventListener('click', () => {
            currentViewMode = 'score';
            btnScore.classList.add('active');
            btnBiome.classList.remove('active');
            updateLayer(data);
        });
    }

    function setupSearch() {
        const btn = document.getElementById('search-btn');
        const rowInput = document.getElementById('row-input');
        const colInput = document.getElementById('col-input');
        const clearBtn = document.getElementById('clear-highlights-btn');

        // Keep the search functionality available even if UI elements are removed
        const doSearch = (r, c) => {
            if (isNaN(r) || isNaN(c)) return;

            const found = allData.find(d => d.row === r && d.col === c);
            if (found) {
                selectTile(found);
            } else {
                console.warn('Cell not found within grid range.');
            }
        };

        // Only attach event listeners if elements exist
        if (btn && rowInput && colInput) {
            btn.addEventListener('click', () => {
                const r = parseInt(rowInput.value);
                const c = parseInt(colInput.value);
                doSearch(r, c);
            });
        }
        
        // Clear highlights button
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                selectedCell = null;
                highlightedCells = [];
                infoDiv.innerHTML = '<p class="stat-label">Hover over a cell to view details.</p>';
                updateLayer(allData);
            });
        }
        
        // Make doSearch available globally for programmatic use
        window.searchTile = doSearch;
    }

    function setupExport() {
        const exportBtn = document.getElementById('export-btn');
        
        if (!exportBtn) return;
        
        exportBtn.addEventListener('click', () => {
            if (!highlightedCells || highlightedCells.length === 0) {
                alert('No tiles currently selected to export.');
                return;
            }
            
            // Find the full data objects for highlighted cells
            const exportData = [];
            for (const h of highlightedCells) {
                const match = allData.find(d => d.row === h.row && d.col === h.col);
                if (match && match.full_data) {
                    exportData.push(match.full_data);
                }
            }
            
            if (exportData.length === 0) {
                alert('No data found for selected tiles.');
                return;
            }
            
            // Convert to CSV
            // Get all unique keys from the full data (some rows might be missing columns)
            // However, for a grid, usually keys are consistent. We use keys from the first full data object
            // or better, use a master list if we want to guarantee all columns. 
            // Let's assume allData has consistent schema or at least the first object is representative.
            // To be safe, we can union all keys from all rows if schema varies, but that's expensive.
            // Given the CSV origin, keys should be consistent.
            
            // Wait, the user asked for ALL columns even if empty.
            // The issue might be that `exportData[0]` might not have keys for empty values if they were dropped during processing?
            // In our Python `get_grid`, we do `full_data[k] = v` for all columns in CSV.
            // So `full_data` should already contain all columns from the CSV, even if values are empty strings.
            
            if (exportData.length === 0) return;

            // Hardcoded list of columns from merged.csv to ensure completeness
            const allKeys = [
                'row', 'col', 'x_km', 'y_km', 'lat', 'lon', 'depth_m', 'pressure_atm', 'biome', 
                'temperature_c', 'light_intensity', 'terrain_roughness', 
                'coral_coral_cover_pct', 'coral_health_index', 'coral_bleaching_risk', 'coral_biodiversity_index', 
                'current_u_mps', 'current_v_mps', 'current_speed_mps', 'current_stability', 'current_flow_direction', 
                'hazard_type', 'hazard_severity', 'hazard_notes', 
                'life_species', 'life_avg_depth_m', 'life_density', 'life_threat_level', 'life_behavior', 'life_trophic_level', 'life_prey_species', 
                'poi_id', 'poi_category', 'poi_label', 'poi_description', 'poi_research_value', 
                'resource_type', 'resource_family', 'resource_abundance', 'resource_purity', 'resource_extraction_difficulty', 'resource_environmental_impact', 'resource_economic_value', 'resource_description', 
                'biome_predators', 'biome_prey', 'biome_interaction_strengths'
            ];
            
            const keys = allKeys;
            
            const csvRows = [];
            
            // Header
            csvRows.push(keys.join(','));
            
            // Rows
            for (const row of exportData) {
                const values = keys.map(key => {
                    const val = row[key];
                    // Handle strings with commas, quotes, or newlines
                    const strVal = String(val === null || val === undefined ? '' : val);
                    if (strVal.includes(',') || strVal.includes('"') || strVal.includes('\n')) {
                        return `"${strVal.replace(/"/g, '""')}"`;
                    }
                    return strVal;
                });
                csvRows.push(values.join(','));
            }
            
            const csvString = csvRows.join('\n');
            const blob = new Blob([csvString], { type: 'text/csv' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            
            const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
            a.setAttribute('hidden', '');
            a.setAttribute('href', url);
            a.setAttribute('download', `abyssal_selection_${timestamp}.csv`);
            
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        });
    }

    function setupChat() {
        const input = document.getElementById('chat-input');
        const btn = document.getElementById('chat-send');
        const msgContainer = document.getElementById('chat-messages');

        const addMsg = (text, type) => {
            const div = document.createElement('div');
            div.className = `message ${type}`;
            div.textContent = text;
            msgContainer.appendChild(div);
            msgContainer.scrollTop = msgContainer.scrollHeight;
        };

        const handleSend = async () => {
            const text = input.value.trim();
            if (!text) return;
            
            addMsg(text, 'user');
            input.value = '';
            input.disabled = true; // Prevent double submit

            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text, thread_id: 123 })
                });

                if (!response.ok) throw new Error('Network response was not ok');

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                
                // Prepare a container for bot stream
                const botMsgDiv = document.createElement('div');
                botMsgDiv.className = 'message bot';
                msgContainer.appendChild(botMsgDiv);
                
                let buffer = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    buffer += decoder.decode(value, { stream: true });
                    
                    // Process complete lines (NDJSON)
                    const lines = buffer.split('\n');
                    buffer = lines.pop(); // Keep incomplete chunk
                    
                    for (const line of lines) {
                        if (!line.trim()) continue;
                        try {
                            const msg = JSON.parse(line);
                            if (msg.type === 'text') {
                                botMsgDiv.textContent += msg.content;
                            } else if (msg.type === 'highlight') {
                                // Execute highlight command
                                setHighlights(msg.tiles);
                                
                                // Add a small system note in chat
                                const note = document.createElement('div');
                                note.className = 'highlight-msg';
                                note.textContent = `✨ Highlighted ${msg.tiles.length} tiles on map.`;
                                msgContainer.appendChild(note);
                            }
                        } catch (e) {
                            console.error('Parse error', e);
                        }
                    }
                    msgContainer.scrollTop = msgContainer.scrollHeight;
                }
            } catch (err) {
                addMsg('Error connecting to assistant.', 'bot');
                console.error(err);
            } finally {
                input.disabled = false;
                input.focus();
            }
        };

        btn.addEventListener('click', handleSend);
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') handleSend();
        });
    }

    function updateSidebar(cell) {
        const d = cell.full_data;

        const formatVal = (key, val) => {
            if (Array.isArray(val)) {
                return val.length > 0 ? val.join(', ') : 'None';
            }
            if (typeof val === 'number') {
                // Max 8 significant figures
                return parseFloat(val.toPrecision(8));
            }
            return val;
        };

        let listItems = '';
        const keys = Object.keys(d).sort();
        
        for (const key of keys) {
            const val = d[key];
            if (Array.isArray(val) && val.length === 0) continue;
            
            listItems += `
                <div class="stat-row">
                    <span class="stat-label" title="${key}">${key}</span>
                    <span class="stat-value" style="text-align: right; max-width: 180px; overflow-wrap: break-word;">
                        ${formatVal(key, val)}
                    </span>
                </div>
            `;
        }

        infoDiv.innerHTML = `
            <div class="stat-box">
                ${listItems}
            </div>
        `;
    }
});
