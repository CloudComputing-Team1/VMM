import asyncio
import psutil
import netifaces as ni
import subprocess
import signal
import sys
import time
import threading

port_number = None
running_containers = []
container_cpu_usages = {}

def get_default_gateway():
    gws = ni.gateways()
    return gws['default'][ni.AF_INET][0]

def run_docker_container(port):
    global running_containers
    command = ["docker", "run", "-d", "-p", f"{port}:{port}", "-e", f"PORT={port}", "--cpus", "0.6", "fog1234/cpu_load_web:3.0"]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    container_id = process.stdout.readline().decode().strip()
    running_containers.append(container_id)
    container_cpu_usages[port] = []
    
    stderr = process.stderr.read()
    if stderr:
        print("Error:", stderr.decode())
    
    # Start monitoring CPU usage for this container
    monitoring_thread = threading.Thread(target=monitor_container_cpu_usage, args=(container_id, port))
    monitoring_thread.start()

def monitor_container_cpu_usage(container_id, port):
    while container_id in running_containers:
        try:
            command = ["docker", "stats", "--no-stream", "--format", "{{.CPUPerc}}", container_id]
            result = subprocess.run(command, stdout=subprocess.PIPE)
            cpu_usage_str = result.stdout.decode().strip().replace('%', '')
            cpu_usage = float(cpu_usage_str)
            container_cpu_usages[port].append(cpu_usage)
            if len(container_cpu_usages[port]) > 5:  # keep only the latest 5 entries to avoid memory overflow
                container_cpu_usages[port].pop(0)
        except Exception as e:
            print(f"Error monitoring CPU usage for container {container_id}: {e}")
        time.sleep(5)  # Adjust the interval as needed

async def tcp_echo_client(port):
    global port_number
    host = get_default_gateway()  # 기본 게이트웨이를 호스트 IP로 사용
    reader, writer = await asyncio.open_connection(host, port)

    try:
        while True:
            data = await reader.read(100)  # 서버로부터 데이터 읽기
            if not data:
                # 데이터가 비어 있다면 서버와의 연결이 끊겼다고 간주
                print('Connection closed by the server')
                break  # 루프를 빠져나와 연결 종료

            message = data.decode()
            print(f'Received: {message}')
            
            if 'Connection order' in message:
                order_number = int(message.split('Connection order: ')[1])
                port_number = 12220 + (3 * order_number)
                print(f'Order number: {order_number}, Port number: {port_number}')
                run_docker_container(port_number)
                port_number += 1

            if message == 'Check status':
                cpu_usage = psutil.cpu_percent(interval=1)
                response = 'CPU usage: ' + str(cpu_usage)
                writer.write(response.encode())
                await writer.drain()
                print(response)
            
            if 'Get container with min CPU usage' in message:
                min_port = get_min_cpu_usage_container()
                response = f'Min CPU usage container port: {min_port}, ports: {container_cpu_usages.keys()}'
                writer.write(response.encode())
                await writer.drain()
                print(response)
    finally:
        print('Close the connection')
        writer.close()

def get_min_cpu_usage_container():
    print(container_cpu_usages)
    min_port = min(container_cpu_usages, key=lambda port: sum(container_cpu_usages[port]) / len(container_cpu_usages[port]) if container_cpu_usages[port] else float('inf'))
    return min_port

def monitor_cpu_and_scale():
    """CPU 사용량을 모니터링하고 필요시 컨테이너를 추가합니다."""
    global port_number
    
    over_threshold_duration = 0
    threshold = 30.0
    duration_to_trigger_scaling = 5  # 초

    while True:
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > threshold:
            over_threshold_duration += 1
        else:
            over_threshold_duration = 0

        if over_threshold_duration >= duration_to_trigger_scaling:
            print("Start container scaling")
            run_docker_container(port_number)
            port_number += 1
            over_threshold_duration = 0
            if threshold == 60.0:
                print("container 스케일 최대치")
                break
            else:
                threshold = 60.0
        time.sleep(1)

async def main():
    port = 9999  # 서버의 포트 번호
    await tcp_echo_client(port)

def signal_handler(sig, frame):
    print('You pressed Ctrl+C!')
    stop_all_containers()
    sys.exit(0)

def stop_all_containers():
    global running_containers
    for container_id in running_containers:
        subprocess.run(["docker", "stop", container_id])
    running_containers = []

if __name__ == "__main__":
    # 초기 부팅 시 잠시 대기(부팅 시 cpu 사용량이 매우 높은것을 감안하기 위해)
    time.sleep(10)

    signal.signal(signal.SIGINT, signal_handler)
    monitoring_thread = threading.Thread(target=monitor_cpu_and_scale)
    monitoring_thread.start()
    time.sleep(2)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        stop_all_containers()
