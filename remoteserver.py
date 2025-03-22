import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, rooms
from fakerig import FakeRadio
import threading
import time

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
socketio = SocketIO(app)

radios = {
    "R1": FakeRadio("R1"),
    "R2": FakeRadio("R2"),
    "R3": FakeRadio("R3"),
}

clients = {}
prev_state = {}

def start_radio_monitor(radio_id, radio):
    prev_state = {}

    def monitor():
        nonlocal prev_state
        while True:
            state = {
                'id': radio.id,
                'freq': radio.get_freq(),
                'ptt': radio.get_ptt(),
                'signal': radio.get_signal_strength()
            }
            if state != prev_state:
                # Poslat všem klientům, kteří sledují právě toto rádio
                for sid, r_id in clients.items():
                    if r_id == radio_id:
                        socketio.emit('radio_status', state, to=sid)
                prev_state = state
            time.sleep(0.5)

    threading.Thread(target=monitor, daemon=True).start()


@app.route('/')
def index():
    return render_template('remote/index.html')


@socketio.on('connect')
def handle_connect():
    sid = request.sid
    print(f"Client {sid} connected")
    radio_list = list(radios.keys())
    socketio.emit('radio_list', radio_list, to=sid)


@socketio.on('select_radio')
def handle_select_radio(data):
    sid = request.sid
    radio_id = data.get('id')
    if radio_id in radios:
        clients[sid] = radio_id
        print(f"Client {sid} is now watching radio {radio_id}")
        socketio.emit('radio_selected', {'id': radio_id}, to=sid)


@socketio.on('toggle_ptt')
def handle_toggle_ptt():
    sid = request.sid
    radio_id = clients.get(sid)
    if radio_id and radio_id in radios:
        radios[radio_id].toggle_ptt()
        socketio.emit('ptt_toggled', {
            'id': radio_id,
            'ptt': radios[radio_id].get_ptt()
        }, to=sid)


@socketio.on('ptt_on')
def handle_ptt_on():
    sid = request.sid
    radio_id = clients.get(sid)
    if radio_id and radio_id in radios:
        radios[radio_id].set_ptt(True)
        socketio.emit('ptt_toggled', {
            'id': radio_id,
            'ptt': True
        }, to=sid)

@socketio.on('ptt_off')
def handle_ptt_off():
    sid = request.sid
    radio_id = clients.get(sid)
    if radio_id and radio_id in radios:
        radios[radio_id].set_ptt(False)
        socketio.emit('ptt_toggled', {
            'id': radio_id,
            'ptt': False
        }, to=sid)


@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in clients:
        print(f"Client {sid} disconnected (was watching {clients[sid]})")
        del clients[sid]


if __name__ == '__main__':
    for radio_id, radio in radios.items():
        start_radio_monitor(radio_id, radio)

    socketio.run(app, host='0.0.0.0', port=5000)
