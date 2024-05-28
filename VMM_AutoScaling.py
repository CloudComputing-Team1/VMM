from flask import Flask, render_template
from flask_socketio import SocketIO
import psutil
import threading
import time
import asyncio
import docker

app = Flask(__name__)
socketio = SocketIO(app)

cpu_load_thread = None
stop_thread = False
connected_clients = 0
auto_scaling_threshold = 50  # CPU 사용량 임계치
scaling_interval = 30  # 30초마다 오토스케일링 체크
target_ip = "192.168.1.100"  # 실제 VMM의 IP

def increase_cpu_load():
    global stop_thread
    result = 0
    while not stop_thread:
        for _ in range(1000000):
            result += 1

def monitor_cpu_load():
    while True:
        cpu_percent = psutil.cpu_percent(interval=1)
        socketio.emit('cpu_update', {'cpu': cpu_percent})
        time.sleep(1)

        if cpu_percent > auto_scaling_threshold:
            asyncio.run(auto_scale_vmm("scale_up", target_ip))

async def auto_scale_vmm(signal, target_ip):
    if signal == "scale_up":
        message = "Create container"
        await send_message_to_specific_vm(target_ip, message)

async def send_message_to_specific_vm(target_ip, message):
    reader, writer = await asyncio.open_connection(target_ip, 8888)
    writer.write(message.encode())
    await writer.drain()
    writer.close()
    await writer.wait_closed()

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    global cpu_load_thread, stop_thread, connected_clients
    connected_clients += 1
    stop_thread = False

    if connected_clients == 1:
        cpu_load_thread = threading.Thread(target=increase_cpu_load)
        cpu_load_thread.start()

@socketio.on('disconnect')
def handle_disconnect():
    global stop_thread, connected_clients
    connected_clients -= 1
    if connected_clients == 0:
        stop_thread = True

@app.route('/containers')
def list_containers():
    client = docker.from_env()
    containers = client.containers.list()
    container_info = []
    for container in containers:
        container_info.append({
            'id': container.short_id,
            'image': container.image.tags[0],
            'status': container.status
        })
    return render_template('containers.html', containers=container_info)


async def handle_container_creation_signal(reader, writer):
    addr = writer.get_extra_info('peername')
    print(f"Connected with {addr}")

    try:
        while True:
            data = await reader.read(100)
            if not data:
                break

            message = data.decode()
            print(f"Received: {message} from {addr}")

            if message == "Create container":
                client = docker.from_env()
                container = client.containers.run("fog1234/cpu_load_web:3.0", detach=True)
                print(f"Created container: {container.short_id}")

                # 새 컨테이너 정보 로깅
                with open('container_creation.log', 'a') as f:
                    f.write(f"Created container ID: {container.short_id}, Image: fog1234/cpu_load_web:3.0\n")

    except Exception as e:
        print(f"Error: {e}")

    print("Closing the connection")
    writer.close()

async def listen_for_signals():
    while True:
        await asyncio.sleep(10)
        print("Sending scale up signal")
        await auto_scale_vmm("scale_up", "192.168.1.100")  # 타겟 IP는 실제 VMM의 IP로 설정해야 함.


async def start_server(host, port):
    server = await asyncio.start_server(handle_container_creation_signal, host, port)
    print(f'Serving on {host}:{port}')
    async with server:
        await server.serve_forever()

async def main():
    host = '0.0.0.0'
    port = 8888

    await asyncio.gather(
        start_server(host, port)
    )

if __name__ == '__main__':
    monitor_thread = threading.Thread(target=monitor_cpu_load)
    monitor_thread.start()
    socketio.run(app, debug=True, host='0.0.0.0')

    # 이벤트 루프 시작
    asyncio.run(main())
