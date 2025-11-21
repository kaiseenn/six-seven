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
            console.log('Initialization complete!');
        })
        .catch(err => {
            console.error('Error fetching grid:', err);
            alert('Failed to load map data. Check console for details.');
        });

    function initDeckGL(processedData) {
        deckglInstance = new DeckGL({
            container: 'map-container',
            mapStyle: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json', // MapLibre style
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
                    <div>Depth: ${object.depth}m</div>
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
            getElevation: d => d.elevation,
            getLineColor: d => (selectedCell && d.row === selectedCell.row && d.col === selectedCell.col) ? [255, 215, 0] : [0, 0, 0],
            getLineWidth: d => (selectedCell && d.row === selectedCell.row && d.col === selectedCell.col) ? 20 : 0,
            lineWidthMinPixels: 0,
            
            updateTriggers: {
                getFillColor: [currentViewMode, selectedCell, highlightedCells],
                getLineWidth: [selectedCell],
                getLineColor: [selectedCell]
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
                return [255, 215, 0, 255]; // Opaque Gold
            }
            // If we have highlights active, check those too
            if (isHighlighted(d)) {
                return [255, 215, 0, 255]; // Also Gold
            }
            // Otherwise dim
            const baseColor = currentViewMode === 'biome' 
                ? (biomeColors[d.biome] || biomeColors['unknown'])
                : getScoreColor(d);
            return [baseColor[0], baseColor[1], baseColor[2], 50]; 
        }
        
        // 2. AI Highlight Priority (No user selection)
        if (highlightedCells.length > 0) {
            if (isHighlighted(d)) {
                return [255, 215, 0, 255]; // Gold
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

        const doSearch = () => {
            const r = parseInt(rowInput.value);
            const c = parseInt(colInput.value);
            
            if (isNaN(r) || isNaN(c)) return;

            const found = allData.find(d => d.row === r && d.col === c);
            if (found) {
                selectTile(found);
            } else {
                alert('Cell not found within grid range.');
            }
        };

        btn.addEventListener('click', doSearch);
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
                if (key.includes('lat') || key.includes('lon')) return val.toFixed(4);
                if (key.includes('depth') || key.includes('pressure') || key.includes('temp')) return val.toFixed(2);
                return val;
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
                 <div class="stat-row" style="border-bottom: 1px solid #8892b0; margin-bottom: 10px; padding-bottom: 5px;">
                    <span class="stat-label"><strong>Column</strong></span>
                    <span class="stat-value"><strong>Value</strong></span>
                </div>
                ${listItems}
            </div>
        `;
    }
});
