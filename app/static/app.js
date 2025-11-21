document.addEventListener('DOMContentLoaded', () => {
    const {DeckGL, ColumnLayer, AmbientLight, PointLight, LightingEffect} = deck;

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

    const infoDiv = document.getElementById('cell-info');
    let selectedCell = null; // For click-locking

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

    // --- Data Fetching ---
    fetch('/api/grid')
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error(data.error);
                return;
            }
            initDeckGL(data);
        })
        .catch(err => console.error('Error fetching grid:', err));

    function initDeckGL(data) {
        // Process data for Deck.gl
        // We calculate 'elevation' here so we don't do it every frame
        const processedData = data.map(d => ({
            ...d,
            // Inverted depth: Shallow (Seamount) = Tall, Deep (Trench) = Short
            // We shift it so the deepest point is at 0 (or close to it)
            elevation: (MAX_DEPTH - d.depth)
        }));

        const deckgl = new DeckGL({
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
            layers: [
                new ColumnLayer({
                    id: 'grid-cell-layer',
                    data: processedData,
                    diskResolution: 4, // 4 vertices = Square column
                    radius: 500,       // 1km grid -> 500m radius (touches edges roughly)
                    extruded: true,
                    pickable: true,
                    elevationScale: Z_SCALE,
                    getPosition: d => [d.lon, d.lat],
                    getFillColor: d => biomeColors[d.biome] || biomeColors['unknown'],
                    getElevation: d => d.elevation,
                    getLineColor: [0, 0, 0],
                    getLineWidth: 0,
                    lineWidthMinPixels: 0,
                    // Interactive props
                    autoHighlight: true,
                    highlightColor: [100, 255, 218, 128],
                    
                    onHover: ({object}) => {
                        if (!selectedCell && object) {
                            updateSidebar(object);
                        }
                    },
                    onClick: ({object}) => {
                        if (object) {
                            selectedCell = object;
                            updateSidebar(object);
                        } else {
                            selectedCell = null;
                            infoDiv.innerHTML = '<p class="stat-label">Hover over a cell to view details.</p>';
                        }
                    }
                })
            ],
            getTooltip: ({object}) => object && {
                html: `
                    <div><b>${object.biome.toUpperCase()}</b></div>
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

    function updateSidebar(cell) {
        // Format tags
        const resourceTags = cell.resources.length > 0 
            ? cell.resources.map(r => `<span class="tag">${r}</span>`).join('')
            : '<span class="stat-label">None</span>';
            
        const hazardTags = cell.hazards.length > 0 
            ? cell.hazards.map(h => `<span class="tag hazard">${h}</span>`).join('')
            : '<span class="stat-label">Safe</span>';

        const lifeTags = cell.life.length > 0 
            ? cell.life.map(l => `<span class="tag life">${l}</span>`).join('')
            : '<span class="stat-label">None</span>';

        infoDiv.innerHTML = `
            <div class="stat-box">
                <div class="stat-row">
                    <span class="stat-label">Coordinates</span>
                    <span class="stat-value">(${cell.row}, ${cell.col})</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Biome</span>
                    <span class="stat-value" style="color: rgb(${biomeColors[cell.biome]?.join(',') || '136,136,136'})">${cell.biome.toUpperCase()}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Depth</span>
                    <span class="stat-value">${cell.depth.toFixed(1)} m</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Pressure</span>
                    <span class="stat-value">${cell.pressure.toFixed(1)} atm</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Temp</span>
                    <span class="stat-value">${cell.temp.toFixed(1)} °C</span>
                </div>
            </div>

            <h2>Resources</h2>
            <div style="margin-bottom: 15px;">${resourceTags}</div>

            <h2>Hazards</h2>
            <div style="margin-bottom: 15px;">${hazardTags}</div>

            <h2>Life Forms</h2>
            <div>${lifeTags}</div>
        `;
    }
});
