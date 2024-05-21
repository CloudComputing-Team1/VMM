# VMM_AutoScaling.py
import asyncio
import docker
from VIM import send_message_to_specific_vm

async def auto_scale_vmm(signal, target_ip):
    # 시그널이 특정 조건을 만족하면 오토스케일링 시작
    if signal == "scale_up":
        message = "Create container"
        await send_message_to_specific_vm(target_ip, message)

async def listen_for_signals():
    # 시그널을 기다리는 함수 (테스트 목적으로 간단히 구현)
    while True:
        # 10초마다 오토스케일링 시그널을 발생시킴
        await asyncio.sleep(10)
        await auto_scale_vmm("scale_up", "192.168.1.100")  # 타겟 IP는 실제 VMM의 IP로 설정해야 함.

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
                container = client.containers.run("nginx", detach=True)  # Nginx 컨테이너 생성
                print(f"Created container: {container.short_id}")

    except Exception as e:
        print(f"Error: {e}")

    print("Closing the connection")
    writer.close()

async def start_server(host, port):
    server = await asyncio.start_server(handle_container_creation_signal, host, port)
    print(f'Serving on {host}:{port}')
    async with server:
        await server.serve_forever()

async def main():
    host = '0.0.0.0'
    port = 8888  # VMM에서 컨테이너 생성 시그널을 받을 포트

    await asyncio.gather(
        start_server(host, port),
        listen_for_signals()
    )

# 이벤트 루프 시작
asyncio.run(main())
