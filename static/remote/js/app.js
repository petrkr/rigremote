let selectedRadio = null;

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
    document.getElementById('freq').innerText = data.freq;
    document.getElementById('ptt').innerText = data.ptt ? 'ON' : 'OFF';
    document.getElementById('signal').innerText = data.signal;
    updatePTTVisual(data.ptt);
});

socket.on('ptt_toggled', function(data) {
    if (data.id !== selectedRadio) return;
    document.getElementById('ptt').innerText = data.ptt ? 'ON' : 'OFF';
    updatePTTVisual(data.ptt);
});

const pttBtn = document.getElementById('pttPushBtn');
pttBtn.addEventListener('mousedown', () => {
    if (selectedRadio) socket.emit('ptt_on');
});
pttBtn.addEventListener('mouseup', () => {
    if (selectedRadio) socket.emit('ptt_off');
});
pttBtn.addEventListener('touchstart', (e) => {
    e.preventDefault();
    if (selectedRadio) socket.emit('ptt_on');
});
pttBtn.addEventListener('touchend', (e) => {
    e.preventDefault();
    if (selectedRadio) socket.emit('ptt_off');
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
    }
}
