// RIG Remote Control JavaScript Client

class RigWebClient {
    constructor() {
        this.ws = null;
        this.selectedRadio = null;
        this.radios = {};
        this.plugins = {};
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        
        this.init();
    }
    
    init() {
        this.setupWebSocket();
        this.loadRadios();
        this.loadPlugins();
        this.loadFeatureCards();
        this.loadRadioConfigs();
        this.loadPluginConfigs();
        this.loadRadioDrivers();
        this.setupEventListeners();
        this.log('System initialized', 'info');
    }
    
    // WebSocket Management
    setupWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        try {
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                this.log('WebSocket connected', 'success');
                this.updateConnectionStatus(true);
                this.reconnectAttempts = 0;
            };
            
            this.ws.onmessage = (event) => {
                this.handleWebSocketMessage(JSON.parse(event.data));
            };
            
            this.ws.onclose = () => {
                this.log('WebSocket disconnected', 'warning');
                this.updateConnectionStatus(false);
                this.attemptReconnect();
            };
            
            this.ws.onerror = (error) => {
                this.log(`WebSocket error: ${error}`, 'error');
            };
            
        } catch (error) {
            this.log(`Failed to create WebSocket: ${error}`, 'error');
        }
    }
    
    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
            
            this.log(`Reconnecting in ${delay/1000}s (attempt ${this.reconnectAttempts})`, 'warning');
            
            setTimeout(() => {
                this.setupWebSocket();
            }, delay);
        } else {
            this.log('Max reconnection attempts reached', 'error');
        }
    }
    
    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'initial_state':
                this.handleInitialState(data);
                break;
            case 'radio_state_changed':
                this.handleRadioStateChange(data);
                break;
            case 'plugin_event':
                this.handlePluginEvent(data);
                break;
            case 'pong':
                // Handle ping/pong for keep-alive
                break;
            case 'error':
                this.log(`WebSocket error: ${data.message}`, 'error');
                break;
            default:
                console.log('Unknown WebSocket message:', data);
        }
    }
    
    handleInitialState(data) {
        if (data.radios) {
            data.radios.forEach(radio => {
                this.radios[radio.id] = radio;
            });
            this.updateRadioList();
        }
    }
    
    handleRadioStateChange(data) {
        if (data.radio_id && this.radios[data.radio_id]) {
            Object.assign(this.radios[data.radio_id], data.state);
            this.updateRadioDisplay();
        }
    }
    
    handlePluginEvent(data) {
        this.log(`Plugin ${data.plugin_key}: ${data.event_type}`, 'info');
        // Update plugin display if needed
    }
    
    // API Communication
    async apiCall(endpoint, method = 'GET', data = null) {
        try {
            const options = {
                method,
                headers: {
                    'Content-Type': 'application/json',
                }
            };
            
            if (data) {
                options.body = JSON.stringify(data);
            }
            
            const response = await fetch(`/api${endpoint}`, options);
            
            if (!response.ok) {
                throw new Error(`API call failed: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            this.log(`API call failed: ${error.message}`, 'error');
            throw error;
        }
    }
    
    // Radio Management
    async loadRadios() {
        try {
            const response = await this.apiCall('/radios');
            response.radios.forEach(radio => {
                this.radios[radio.id] = radio;
            });
            this.updateRadioList();
        } catch (error) {
            this.log('Failed to load radios', 'error');
        }
    }
    
    async refreshRadios() {
        this.log('Refreshing radio list...', 'info');
        await this.loadRadios();
    }
    
    selectRadio() {
        const select = document.getElementById('radio-select');
        const radioId = select.value;
        
        if (radioId && this.radios[radioId]) {
            this.selectedRadio = radioId;
            this.showRadioPanel();
            this.updateRadioDisplay();
            this.log(`Selected radio: ${this.radios[radioId].name}`, 'info');
        } else {
            this.selectedRadio = null;
            this.hideRadioPanel();
        }
    }
    
    updateRadioList() {
        const select = document.getElementById('radio-select');
        const currentValue = select.value;
        
        this.log(`Updating radio list with ${Object.keys(this.radios).length} radios`, 'info');
        
        // Clear existing options except first
        select.innerHTML = '<option value="">-- Choose Radio --</option>';
        
        Object.values(this.radios).forEach(radio => {
            const option = document.createElement('option');
            option.value = radio.id;
            option.textContent = `${radio.name} ${radio.connected ? '(Connected)' : '(Disconnected)'}`;
            select.appendChild(option);
            this.log(`Added radio to selector: ${radio.id} (${radio.name})`, 'info');
        });
        
        // Restore selection if possible
        if (currentValue && this.radios[currentValue]) {
            select.value = currentValue;
            this.log(`Restored selection: ${currentValue}`, 'info');
        } else if (currentValue) {
            this.log(`Could not restore selection ${currentValue} - radio no longer exists`, 'warning');
        }
        
        // Update radio count
        document.getElementById('radio-count').textContent = `Radios: ${Object.keys(this.radios).length}`;
    }
    
    updateRadioDisplay() {
        if (!this.selectedRadio || !this.radios[this.selectedRadio]) {
            return;
        }
        
        const radio = this.radios[this.selectedRadio];
        
        // Update display elements
        document.getElementById('selected-radio-name').textContent = radio.name;
        
        if (radio.frequency) {
            const freqMHz = (radio.frequency / 1000000).toFixed(3);
            document.getElementById('current-frequency').textContent = `${freqMHz} MHz`;
        }
        
        if (radio.mode) {
            document.getElementById('current-mode').textContent = radio.mode;
            this.updateModeButtons(radio.mode);
        }
        
        if (radio.ptt !== undefined) {
            this.updatePTTStatus(radio.ptt);
        }
        
        if (radio.rssi !== undefined) {
            this.updateSignalMeter(radio.rssi);
        }
        
        if (radio.connected !== undefined) {
            this.updateRadioConnectionStatus(radio.connected);
        }
    }
    
    updateModeButtons(currentMode) {
        const buttons = document.querySelectorAll('.mode-buttons button');
        buttons.forEach(button => {
            button.classList.toggle('active', button.textContent === currentMode);
        });
    }
    
    updatePTTStatus(pttOn) {
        const status = document.getElementById('ptt-status');
        const toggle = document.getElementById('ptt-toggle');
        
        if (pttOn) {
            status.textContent = 'PTT: ON';
            status.className = 'ptt-on';
            toggle.classList.add('active');
        } else {
            status.textContent = 'PTT: OFF';
            status.className = 'ptt-off';
            toggle.classList.remove('active');
        }
    }
    
    updateSignalMeter(rssi) {
        const bar = document.getElementById('signal-bar');
        const value = document.getElementById('rssi-value');
        
        value.textContent = `${rssi} dBm`;
        
        // Convert RSSI to percentage (rough approximation)
        // -120 dBm = 0%, -30 dBm = 100%
        const percentage = Math.max(0, Math.min(100, ((rssi + 120) / 90) * 100));
        bar.style.width = `${percentage}%`;
    }
    
    updateRadioConnectionStatus(connected) {
        const status = document.getElementById('radio-connection');
        const button = document.getElementById('connect-button');
        
        if (connected) {
            status.textContent = 'Connected';
            status.className = 'status-indicator connected';
            button.textContent = 'Disconnect';
            button.className = 'disconnect';
        } else {
            status.textContent = 'Disconnected';
            status.className = 'status-indicator disconnected';
            button.textContent = 'Connect';
            button.className = '';
        }
    }
    
    // Radio Control Functions
    async setFrequency() {
        if (!this.selectedRadio) return;
        
        const input = document.getElementById('frequency-input');
        const hz = parseInt(input.value);
        
        if (isNaN(hz) || hz <= 0) {
            this.log('Invalid frequency value', 'error');
            return;
        }
        
        try {
            await this.apiCall(`/radios/${this.selectedRadio}/frequency`, 'POST', { hz });
            this.log(`Frequency set to ${(hz/1000000).toFixed(3)} MHz`, 'success');
            input.value = '';
        } catch (error) {
            this.log('Failed to set frequency', 'error');
        }
    }
    
    async setMode(mode) {
        if (!this.selectedRadio) return;
        
        try {
            await this.apiCall(`/radios/${this.selectedRadio}/mode`, 'POST', { mode });
            this.log(`Mode set to ${mode}`, 'success');
        } catch (error) {
            this.log('Failed to set mode', 'error');
        }
    }
    
    async togglePTT() {
        if (!this.selectedRadio) return;
        
        const radio = this.radios[this.selectedRadio];
        const newPTT = !radio.ptt;
        
        try {
            await this.apiCall(`/radios/${this.selectedRadio}/ptt`, 'POST', { on: newPTT });
            this.log(`PTT ${newPTT ? 'ON' : 'OFF'}`, newPTT ? 'warning' : 'info');
        } catch (error) {
            this.log('Failed to toggle PTT', 'error');
        }
    }
    
    async setPTT(on) {
        if (!this.selectedRadio) return;
        
        try {
            await this.apiCall(`/radios/${this.selectedRadio}/ptt`, 'POST', { on });
        } catch (error) {
            this.log('Failed to set PTT', 'error');
        }
    }
    
    async connectRadio() {
        // TODO: Implement radio connection/disconnection
        this.log('Radio connection not yet implemented', 'warning');
    }
    
    // Feature Cards Management
    async loadFeatureCards() {
        try {
            const response = await this.apiCall('/plugin-cards');
            this.updateFeatureCardsDisplay(response.cards);
        } catch (error) {
            this.log('Failed to load feature cards', 'error');
        }
    }
    
    updateFeatureCardsDisplay(cards) {
        const container = document.getElementById('features-grid');
        container.innerHTML = '';
        
        cards.forEach(card => {
            const cardElement = this.createFeatureCard(card);
            container.appendChild(cardElement);
        });
        
        if (cards.length === 0) {
            container.innerHTML = '<p style="color: #7f8c8d; text-align: center; grid-column: 1 / -1;">No features available</p>';
        }
    }
    
    createFeatureCard(card) {
        const cardDiv = document.createElement('div');
        cardDiv.className = 'feature-card';
        cardDiv.onclick = () => this.openFeature(card.main_url);
        
        cardDiv.innerHTML = `
            <div class="feature-card-header">
                <div class="feature-card-icon">${card.icon}</div>
                <h3>${card.title}</h3>
            </div>
            <div class="feature-card-description">
                ${card.description}
            </div>
            <div class="feature-card-footer">
                <span class="feature-card-status ${card.status}">${card.status}</span>
                <div class="feature-card-actions">
                    ${card.settings_url ? `<a href="${card.settings_url}" class="btn-small" onclick="event.stopPropagation()">⚙️ Settings</a>` : ''}
                </div>
            </div>
        `;
        
        return cardDiv;
    }
    
    openFeature(url) {
        if (url) {
            window.location.href = url;
        }
    }

    // Plugin Management
    async loadPlugins() {
        try {
            const response = await this.apiCall('/plugins');
            this.plugins = {};
            response.plugins.forEach(plugin => {
                this.plugins[plugin.key] = plugin;
            });
            this.updatePluginDisplay();
        } catch (error) {
            this.log('Failed to load plugins', 'error');
        }
    }
    
    updatePluginDisplay() {
        const container = document.getElementById('plugins-list');
        container.innerHTML = '';
        
        Object.values(this.plugins).forEach(plugin => {
            const card = this.createPluginCard(plugin);
            container.appendChild(card);
        });
    }
    
    createPluginCard(plugin) {
        const card = document.createElement('div');
        card.className = 'plugin-card';
        
        card.innerHTML = `
            <h4>${plugin.label}</h4>
            <div class="plugin-status ${plugin.running ? 'running' : 'stopped'}">
                ${plugin.running ? 'Running' : 'Stopped'}
            </div>
            <div class="plugin-controls">
                <button class="start" onclick="rigClient.startPlugin('${plugin.key}')">Start</button>
                <button class="stop" onclick="rigClient.stopPlugin('${plugin.key}')">Stop</button>
            </div>
        `;
        
        return card;
    }
    
    async startPlugin(key) {
        try {
            await this.apiCall(`/plugins/${key}/start`, 'POST');
            this.log(`Started plugin: ${key}`, 'success');
            await this.loadPlugins();
        } catch (error) {
            this.log(`Failed to start plugin: ${key}`, 'error');
        }
    }
    
    async stopPlugin(key) {
        try {
            await this.apiCall(`/plugins/${key}/stop`, 'POST');
            this.log(`Stopped plugin: ${key}`, 'success');
            await this.loadPlugins();
        } catch (error) {
            this.log(`Failed to stop plugin: ${key}`, 'error');
        }
    }
    
    // UI Management
    showRadioPanel() {
        document.getElementById('radio-panel').classList.remove('hidden');
    }
    
    hideRadioPanel() {
        document.getElementById('radio-panel').classList.add('hidden');
    }
    
    updateConnectionStatus(connected) {
        const status = document.getElementById('connection-status');
        if (connected) {
            status.textContent = 'WebSocket: Connected';
            status.className = 'status-indicator connected';
        } else {
            status.textContent = 'WebSocket: Disconnected';
            status.className = 'status-indicator disconnected';
        }
    }
    
    log(message, type = 'info') {
        const container = document.getElementById('activity-log');
        const entry = document.createElement('div');
        const timestamp = new Date().toLocaleTimeString();
        
        entry.className = `log-entry ${type}`;
        entry.textContent = `[${timestamp}] ${message}`;
        
        container.appendChild(entry);
        container.scrollTop = container.scrollHeight;
        
        // Keep only last 100 entries
        while (container.children.length > 100) {
            container.removeChild(container.firstChild);
        }
    }
    
    setupEventListeners() {
        // Handle Enter key in frequency input
        document.getElementById('frequency-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.setFrequency();
            }
        });
        
        // Periodic ping to keep WebSocket alive
        setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000);
    }
    
    // Configuration Management
    async loadRadioConfigs() {
        try {
            const response = await this.apiCall('/config/radios');
            this.updateRadioConfigDisplay(response.radios);
        } catch (error) {
            this.log('Failed to load radio configurations', 'error');
        }
    }
    
    async loadPluginConfigs() {
        try {
            const response = await this.apiCall('/config/plugins');
            this.updatePluginConfigDisplay(response.plugins);
        } catch (error) {
            this.log('Failed to load plugin configurations', 'error');
        }
    }
    
    async loadRadioDrivers() {
        try {
            const response = await this.apiCall('/config/radio-drivers');
            this.updateRadioDriverSelect(response.drivers);
        } catch (error) {
            this.log('Failed to load radio drivers', 'error');
        }
    }
    
    updateRadioConfigDisplay(radios) {
        const container = document.getElementById('radios-config-list');
        container.innerHTML = '';
        
        radios.forEach(radio => {
            const item = document.createElement('div');
            item.className = 'config-item';
            item.innerHTML = `
                <h4>${radio.name}</h4>
                <div class="config-status ${radio.enabled ? 'enabled' : 'disabled'}">
                    ${radio.enabled ? 'Enabled' : 'Disabled'}
                </div>
                <p><strong>Type:</strong> ${radio.driver_type}</p>
                <p><strong>Internal ID:</strong> <code>${radio.id}</code></p>
                ${Object.keys(radio.config).length > 0 ? 
                    `<p><strong>Config:</strong> ${JSON.stringify(radio.config)}</p>` : 
                    '<p><em>No additional configuration</em></p>'
                }
                <div class="config-controls">
                    <button class="btn btn-primary" onclick="rigClient.editRadio('${radio.id}')">Edit</button>
                    <button class="btn ${radio.enabled ? 'btn-secondary' : 'btn-success'}" 
                            onclick="rigClient.toggleRadio('${radio.id}', ${!radio.enabled})">
                        ${radio.enabled ? 'Disable' : 'Enable'}
                    </button>
                    <button class="btn btn-danger" onclick="rigClient.deleteRadio('${radio.id}')">Delete</button>
                </div>
            `;
            container.appendChild(item);
        });
    }
    
    updatePluginConfigDisplay(plugins) {
        const container = document.getElementById('plugins-config-list');
        container.innerHTML = '';
        
        plugins.forEach(plugin => {
            const item = document.createElement('div');
            item.className = 'config-item';
            item.innerHTML = `
                <h4>${plugin.label} (${plugin.key})</h4>
                <div class="config-status ${plugin.enabled ? 'enabled' : 'disabled'}">
                    ${plugin.enabled ? 'Enabled' : 'Disabled'}
                </div>
                <p><strong>Running:</strong> ${plugin.running ? 'Yes' : 'No'}</p>
                <p><strong>External Service:</strong> ${plugin.external_service ? 'Yes' : 'No'}</p>
                <div class="config-controls">
                    <button class="btn ${plugin.enabled ? 'btn-secondary' : 'btn-success'}" 
                            onclick="rigClient.togglePlugin('${plugin.key}', ${!plugin.enabled})">
                        ${plugin.enabled ? 'Disable' : 'Enable'}
                    </button>
                    ${plugin.enabled ? `
                        <button class="btn ${plugin.running ? 'btn-secondary' : 'btn-success'}" 
                                onclick="rigClient.${plugin.running ? 'stopPlugin' : 'startPlugin'}('${plugin.key}')">
                            ${plugin.running ? 'Stop' : 'Start'}
                        </button>
                    ` : ''}
                    <a href="/plugins/${plugin.key}/settings/" class="btn btn-primary" style="text-decoration: none; color: white;">⚙️ Settings</a>
                </div>
            `;
            container.appendChild(item);
        });
    }
    
    updateRadioDriverSelect(drivers) {
        const select = document.getElementById('new-radio-driver');
        select.innerHTML = '<option value="">-- Select Driver --</option>';
        
        drivers.forEach(driver => {
            const option = document.createElement('option');
            option.value = driver.type;
            option.textContent = driver.name || driver.type;
            if (driver.description) {
                option.title = driver.description;
            }
            select.appendChild(option);
        });
    }
    
    async addRadio() {
        const name = document.getElementById('new-radio-name').value.trim();
        const driverType = document.getElementById('new-radio-driver').value;
        
        if (!name || !driverType) {
            this.log('Please fill in radio name and select driver type', 'error');
            return;
        }
        
        try {
            const response = await this.apiCall('/config/radios', 'POST', {
                name: name,
                driver_type: driverType,
                enabled: true,
                config: {}
            });
            
            this.log(`Added radio: ${name} (ID: ${response.radio.id})`, 'success');
            
            // Clear form
            document.getElementById('new-radio-name').value = '';
            document.getElementById('new-radio-driver').value = '';
            
            // Reload configurations
            await this.loadRadioConfigs();
            await this.loadRadios();
            
        } catch (error) {
            this.log(`Failed to add radio: ${error.message}`, 'error');
        }
    }
    
    async toggleRadio(radioId, enabled) {
        try {
            await this.apiCall(`/config/radios/${radioId}`, 'PUT', { enabled });
            this.log(`Radio ${radioId} ${enabled ? 'enabled' : 'disabled'}`, 'success');
            
            // Update radio availability in selector
            await this.loadRadios();
            this.updateRadioList();
            
            // Update configuration display
            await this.loadRadioConfigs();
        } catch (error) {
            this.log(`Failed to toggle radio: ${error.message}`, 'error');
        }
    }
    
    async deleteRadio(radioId) {
        // Find radio name for confirmation
        const radioName = this.radios[radioId]?.name || radioId;
        
        if (confirm(`Delete radio "${radioName}"? This cannot be undone.`)) {
            try {
                await this.apiCall(`/config/radios/${radioId}`, 'DELETE');
                this.log(`Deleted radio: ${radioName}`, 'success');
                
                // Remove from local cache immediately
                delete this.radios[radioId];
                
                // Clear selection if deleted radio was selected
                if (this.selectedRadio === radioId) {
                    this.selectedRadio = null;
                    this.hideRadioPanel();
                }
                
                // Update radio selector immediately
                this.updateRadioList();
                
                // Reload configurations to sync with server
                await this.loadRadioConfigs();
                
            } catch (error) {
                this.log(`Failed to delete radio: ${error.message}`, 'error');
                // Restore radio in cache on error
                await this.loadRadios();
            }
        }
    }
    
    async togglePlugin(pluginKey, enabled) {
        try {
            const endpoint = enabled ? 'enable' : 'disable';
            await this.apiCall(`/config/plugins/${pluginKey}/${endpoint}`, 'POST');
            this.log(`Plugin ${pluginKey} ${enabled ? 'enabled' : 'disabled'}`, 'success');
            await this.loadPluginConfigs();
            await this.loadPlugins();
        } catch (error) {
            this.log(`Failed to toggle plugin: ${error.message}`, 'error');
        }
    }
    
    async editRadio(radioId) {
        try {
            // Get current radio configuration and driver schema
            const [configResponse, driversResponse] = await Promise.all([
                this.apiCall(`/config/radios`),
                this.apiCall(`/config/radio-drivers`)
            ]);
            
            const radioConfig = configResponse.radios.find(r => r.id === radioId);
            if (!radioConfig) {
                this.log(`Radio ${radioId} not found`, 'error');
                return;
            }
            
            const driver = driversResponse.drivers.find(d => d.type === radioConfig.driver_type);
            const configSchema = driver?.config_schema || {};
            
            this.showEditRadioModal(radioConfig, configSchema);
            
        } catch (error) {
            this.log(`Failed to load radio configuration: ${error.message}`, 'error');
        }
    }
    
    showEditRadioModal(radioConfig, configSchema) {
        // Create modal if it doesn't exist
        let modal = document.getElementById('edit-radio-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'edit-radio-modal';
            modal.style.cssText = `
                display: none; 
                position: fixed; 
                top: 0; 
                left: 0; 
                width: 100%; 
                height: 100%; 
                background: rgba(0,0,0,0.8); 
                z-index: 1000;
            `;
            document.body.appendChild(modal);
        }
        
        // Build form based on config schema
        let configFields = '';
        if (Object.keys(configSchema).length > 0) {
            configFields = '<h4>Driver Configuration</h4>';
            for (const [key, field] of Object.entries(configSchema)) {
                const currentValue = radioConfig.config[key] || field.default || '';
                configFields += `
                    <div class="form-group">
                        <label>${field.title || key}:</label>
                        <input type="${field.type === 'number' ? 'number' : 'text'}" 
                               id="config-${key}" 
                               value="${currentValue}" 
                               placeholder="${field.description || ''}"
                               ${field.required ? 'required' : ''}>
                        ${field.description ? `<small>${field.description}</small>` : ''}
                    </div>
                `;
            }
        }
        
        modal.innerHTML = `
            <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: #2c2c2c; padding: 2rem; border-radius: 8px; width: 90%; max-width: 600px; max-height: 90%; overflow-y: auto; color: #e0e0e0;">
                <h2>Edit Radio: ${radioConfig.name}</h2>
                
                <div class="form-group">
                    <label>Radio Name:</label>
                    <input type="text" id="edit-radio-name" value="${radioConfig.name}" required>
                </div>
                
                <div class="form-group">
                    <label>Driver Type:</label>
                    <input type="text" value="${radioConfig.driver_type}" disabled style="background-color: #444; color: #888;">
                    <small>Driver type cannot be changed after creation</small>
                </div>
                
                <div class="form-group">
                    <label>Enabled:</label>
                    <select id="edit-radio-enabled">
                        <option value="true" ${radioConfig.enabled ? 'selected' : ''}>Yes</option>
                        <option value="false" ${!radioConfig.enabled ? 'selected' : ''}>No</option>
                    </select>
                </div>
                
                ${configFields}
                
                <div class="form-actions" style="margin-top: 1rem; display: flex; gap: 1rem;">
                    <button class="btn btn-primary" onclick="rigClient.saveRadioEdit('${radioConfig.id}', ${JSON.stringify(configSchema).replace(/"/g, '&quot;')})">Save Changes</button>
                    <button class="btn btn-secondary" onclick="rigClient.closeEditRadioModal()">Cancel</button>
                </div>
            </div>
        `;
        
        modal.style.display = 'block';
    }
    
    async saveRadioEdit(radioId, configSchema) {
        try {
            const name = document.getElementById('edit-radio-name').value.trim();
            const enabled = document.getElementById('edit-radio-enabled').value === 'true';
            
            if (!name) {
                this.log('Radio name is required', 'error');
                return;
            }
            
            // Collect config values
            const config = {};
            for (const key of Object.keys(configSchema)) {
                const input = document.getElementById(`config-${key}`);
                if (input) {
                    config[key] = input.value;
                }
            }
            
            const response = await this.apiCall(`/config/radios/${radioId}`, 'PUT', {
                name: name,
                enabled: enabled,
                config: config
            });
            
            this.log(`Radio ${radioId} updated successfully`, 'success');
            this.closeEditRadioModal();
            
            // Reload configurations and radio list
            await this.loadRadioConfigs();
            await this.loadRadios();
            
        } catch (error) {
            this.log(`Failed to update radio: ${error.message}`, 'error');
        }
    }
    
    closeEditRadioModal() {
        const modal = document.getElementById('edit-radio-modal');
        if (modal) {
            modal.style.display = 'none';
        }
    }
}

// Global functions for HTML onclick handlers
function selectRadio() {
    rigClient.selectRadio();
}

function refreshRadios() {
    rigClient.refreshRadios();
}

function setFrequency() {
    rigClient.setFrequency();
}

function setMode(mode) {
    rigClient.setMode(mode);
}

function togglePTT() {
    rigClient.togglePTT();
}

function setPTT(on) {
    rigClient.setPTT(on);
}

function connectRadio() {
    rigClient.connectRadio();
}

function showConfigTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.config-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-button').forEach(button => {
        button.classList.remove('active');
    });
    
    // Show selected tab
    document.getElementById(`config-${tabName}`).classList.add('active');
    event.target.classList.add('active');
}

function addRadio() {
    rigClient.addRadio();
}

// Initialize application
let rigClient;
document.addEventListener('DOMContentLoaded', () => {
    rigClient = new RigWebClient();
});