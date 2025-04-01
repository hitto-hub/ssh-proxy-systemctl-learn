#!/usr/bin/env python3
import os
import sys
import socket
import time
import select
import requests
import logging
import traceback

# --- ログの設定 ---
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# --- 設定値 ---
API_ENDPOINT = "http://your-api.example.com/start_vm"  # VM 起動用の API エンドポイント
VM_SSH_PORT = 22            # VM の SSH ポート（通常 22）
API_TIMEOUT = 10            # API 呼び出しのタイムアウト（秒）
POLL_INTERVAL = 2           # VM 起動待ちのポーリング間隔（秒）

# --- VM 起動の API 呼び出し ---
def start_vm():
    logging.debug("start_vm: APIエンドポイントにリクエストを送信します。")
    try:
        response = requests.post(API_ENDPOINT, timeout=API_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        vm_ip = data.get("vm_ip")
        if not vm_ip:
            logging.error("API のレスポンスに vm_ip が含まれていません。")
            sys.exit(1)
        logging.info("VM 起動要求完了、IP: %s", vm_ip)
        return vm_ip
    except Exception as e:
        logging.exception("start_vm: VM の起動に失敗しました。")
        sys.exit(1)

# --- VM の SSH 接続可能状態を待つ ---
def wait_for_vm(vm_ip):
    logging.debug("wait_for_vm: %s の SSH ポート %d の接続可能状態を待ちます。", vm_ip, VM_SSH_PORT)
    while True:
        try:
            with socket.create_connection((vm_ip, VM_SSH_PORT), timeout=5):
                logging.info("VM が起動し、%s:%d で接続可能になりました。", vm_ip, VM_SSH_PORT)
                return
        except Exception as e:
            logging.debug("wait_for_vm: まだ VM は起動していません。再試行します… (%s)", e)
            time.sleep(POLL_INTERVAL)

# --- ソケット間の双方向データ転送 ---
def forward_data(src, dst):
    logging.debug("forward_data: 双方向のデータ転送を開始します。")
    src.setblocking(0)
    dst.setblocking(0)
    sockets = [src, dst]
    while True:
        try:
            r, _, x = select.select(sockets, [], sockets, 1)
            if x:
                logging.debug("forward_data: エラーが検出されました。転送を中断します。")
                break
            if not r:
                continue
            for sock in r:
                data = sock.recv(4096)
                if not data:
                    logging.debug("forward_data: データがなくなりました。")
                    return
                if sock is src:
                    dst.sendall(data)
                else:
                    src.sendall(data)
        except Exception as e:
            logging.exception("forward_data: 例外が発生しました。")
            return

def main():
    # systemd により、接続されたソケットは標準入力 (fd 0) 経由で渡される
    logging.debug("main: systemd から渡されたソケットを取得します。")
    try:
        sock_in = socket.socket(fileno=sys.stdin.fileno())
        peer = sock_in.getpeername()
        logging.info("main: 接続元の情報: %s", peer)
    except Exception as e:
        logging.exception("main: 受け取ったソケットのオープンに失敗しました。")
        sys.exit(1)

    # API を呼び出して VM を起動し、IP アドレスを取得
    vm_ip = start_vm()

    # VM の SSH ポートが接続可能になるまで待機
    wait_for_vm(vm_ip)

    # VM の SSH に接続
    logging.debug("main: VM (%s) の SSH に接続を試みます。", vm_ip)
    try:
        sock_out = socket.create_connection((vm_ip, VM_SSH_PORT))
        logging.info("main: VM の SSH への接続に成功しました。")
    except Exception as e:
        logging.exception("main: VM の SSH 接続に失敗しました。")
        sys.exit(1)

    # 受け取ったソケット (クライアントからの接続) と VM の SSH ソケット間でデータを転送
    forward_data(sock_in, sock_out)
    sock_in.close()
    sock_out.close()
    logging.info("main: 接続をクローズしました。")

if __name__ == "__main__":
    main()
