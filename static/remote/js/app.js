let selectedRadio = null;
let isTransmitting = false;

const socket = io();

socket.on('connect', () => {
    document.getElementById('statusConn').innerText = "Status: Online";
});

socket.on('disconnect', () => {
    document.getElementById('statusConn').innerText = "Status: Offline";
});

socket.on('radio_list', function(radioList) {
    const select = document.getElementById('radioSelect');
    select.innerHTML = '<option disabled selected>-- choose --</option>';
    radioList.forEach(id => {
        const opt = document.createElement('option');
        opt.value = id;
        opt.text = id;
        select.appendChild(opt);
    });
});

function selectRadio() {
    const selected = document.getElementById('radioSelect').value;
    socket.emit('select_radio', { id: selected });
}

socket.on('radio_selected', function(data) {
    selectedRadio = data.id;
    document.getElementById('statusRadio').innerText = "Radio: " + selectedRadio;
});

socket.on('radio_status', function(data) {
    if (data.id !== selectedRadio) return;

    if ('freq' in data && data.freq > 0) {
        const freqKHz = (data.freq / 1000).toFixed(1);
        const parts = freqKHz.split('.');
        const formatted = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ' ') + '.' + parts[1];
        document.getElementById('freq').innerText = `${formatted} kHz`;
    } else {
        document.getElementById('freq').innerText = '--';
    }

    document.getElementById('ptt').innerText = data.ptt ? 'ON' : 'OFF';
    updateSignalMeter(data.signal);
    updatePTTVisual(data.ptt);

    // Mode
    if ('mode' in data && data.mode) {
        document.getElementById('modeValue').innerText = data.mode;
    } else {
        document.getElementById('modeValue').innerText = '--';
    }

    // Bandwidth
    if ('bandwidth' in data && data.bandwidth > 0) {
        const bwKHz = (data.bandwidth / 1000).toFixed(1);
        document.getElementById('bandwidthValue').innerText = `${bwKHz} kHz`;
    } else {
        document.getElementById('bandwidthValue').innerText = '--';
    }

    // CTCSS
    if ('ctcss' in data && data.ctcss > 0) {
        const ctcssHz = (data.ctcss / 10).toFixed(1);
        document.getElementById('ctcssValue').innerText = `${ctcssHz} Hz`;
    } else {
        document.getElementById('ctcssValue').innerText = "Off";
    }

    // DCS
    if ('dcs' in data && data.dcs > 0) {
        const code = data.dcs.toString().padStart(3, '0');
        document.getElementById('dcsValue').innerText = `D${code}`;
    } else {
        document.getElementById('dcsValue').innerText = "Off";
    }
});

socket.on('ptt_toggled', function(data) {
    if (data.id !== selectedRadio) return;
    document.getElementById('ptt').innerText = data.ptt ? 'ON' : 'OFF';
    updatePTTVisual(data.ptt);
});

const pttBtn = document.getElementById('pttPushBtn');
pttBtn.addEventListener('mousedown', () => {
    if (selectedRadio) {
        socket.emit('ptt_on');
        startTXAudio();
    }
});
pttBtn.addEventListener('mouseup', () => {
    if (selectedRadio) {
        socket.emit('ptt_off');
        stopTXAudio();
    }
});
pttBtn.addEventListener('touchstart', (e) => {
    e.preventDefault();
    if (selectedRadio) {
        socket.emit('ptt_on');
        startTXAudio();
    }
});
pttBtn.addEventListener('touchend', (e) => {
    e.preventDefault();
    if (selectedRadio) {
        socket.emit('ptt_off');
        stopTXAudio();
    }
});

function updatePTTVisual(isOn) {
    const pttPush = document.getElementById('pttPushBtn');
    const pttToggle = document.getElementById('pttToggleBtn');

    if (isOn) {
        pttPush.classList.add('ptt-on');
        pttPush.classList.remove('ptt-off');
        pttToggle.classList.add('ptt-on');
        pttToggle.classList.remove('ptt-off');
    } else {
        pttPush.classList.add('ptt-off');
        pttPush.classList.remove('ptt-on');
        pttToggle.classList.add('ptt-off');
        pttToggle.classList.remove('ptt-on');
    }
}

function togglePTT() {
    if (selectedRadio) {
        socket.emit('toggle_ptt');

        if (isTransmitting) {
            stopTXAudio();
            isTransmitting = false;
        } else {
            startTXAudio();
            isTransmitting = true;
        }
    }
}

function updateSignalMeter(value) {
    const cover = document.getElementById('sMeterCover');

    const clamped = Math.max(-60, Math.min(60, value));
    const percent = 100 - ((clamped + 60) / 120) * 100;

    cover.style.width = percent + "%";  // překrytí zprava
}

let audioContext;
let processor;
let input;

function startTXAudio() {
    navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
        audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
        input = audioContext.createMediaStreamSource(stream);

        processor = audioContext.createScriptProcessor(2048, 1, 1);
        input.connect(processor);
        processor.connect(audioContext.destination);

        processor.onaudioprocess = function (e) {
            const floatData = e.inputBuffer.getChannelData(0); // Float32Array
            const int16 = new Int16Array(floatData.length);

            for (let i = 0; i < floatData.length; i++) {
                int16[i] = Math.max(-1, Math.min(1, floatData[i])) * 32767;
            }

            socket.emit('audio_pcm', int16.buffer);
        };
    });
}

function stopTXAudio() {
    if (processor) processor.disconnect();
    if (input) input.disconnect();
    if (audioContext) audioContext.close();

    processor = null;
    input = null;
    audioContext = null;
}
