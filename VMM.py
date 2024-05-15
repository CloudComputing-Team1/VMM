import asyncio
import psutil
import netifaces as ni

def get_default_gateway():
    gws = ni.gateways()
    return gws['default'][ni.AF_INET][0]

async def tcp_echo_client(port):
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

            if message == 'Check status':
                cpu_usage = psutil.cpu_percent(interval=1)
                response = 'CPU usage: ' + str(cpu_usage)
                writer.write(response.encode())
                await writer.drain()
                print(response)

    finally:
        print('Close the connection')
        writer.close()

async def main():
    port = 9999  # 서버의 포트 번호
    await tcp_echo_client(port)

# 이벤트 루프 시작
asyncio.run(main())
