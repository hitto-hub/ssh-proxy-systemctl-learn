# Systemctl On-Demand SSH VM Startup

このREADME.mdは、Chat-GPT o3-mini-highによって生成されました。

```log
$ ssh -p 2222 hitto@192.168.0.48
...
  IPv4 address for eth0: 192.168.0.57
...
hitto@ssh:~$ ip a
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host noprefixroute
       valid_lft forever preferred_lft forever
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
...
    inet 192.168.0.57/24 metric 100 brd 192.168.0.255 scope global dynamic eth0
       valid_lft 55284sec preferred_lft 55284sec
...
hitto@ssh:~$
```

# 概要

このプロジェクトは、systemd のソケットアクティベーション機能を利用して、SSH 接続要求を受けた際にバックエンドの仮想マシン（VM）をオンデマンドで起動し、起動後に SSH 接続を転送する仕組みを実現するサンプルです。

## 構成ファイル

- **ssh-on-demand.socket**
  SSH 接続要求を待ち受けるソケットユニットです。
  - `ListenStream` でポート 22 をリッスンし、`Accept=yes` により各接続ごとに新しいサービスインスタンスが起動されます。

- **ssh-on-demand@.service**
  テンプレート化されたサービスユニットです。
  - 接続があると、`/usr/local/bin/vm_startup.py` を実行し、受信したソケットを標準入力経由で渡します。
  - `StandardOutput` および `StandardError` は `journal` にリダイレクトして、SSH クライアントにログが流れ込まないようにしています。

- **vm_startup.py**
  Python スクリプトで、以下の処理を行います:
  - API エンドポイントに対して VM の起動要求を送信し、レスポンスから VM の IP アドレスを取得する。
  - 取得した IP アドレスの VM の SSH ポート（通常 22）が接続可能になるまでポーリングで待機する。
  - クライアントからの接続（標準入力経由のソケット）と、VM の SSH 接続との間で双方向のデータ転送（プロキシ）を実施する。

## 事前条件

- **systemd** が動作する環境
- **Python 3**
  必要なライブラリ: `requests`
  （例: `pip install requests`）
- **ネットワーク設定**
  VM の SSH ポート（通常 22）が利用可能であること

## インストール手順

1. **ファイルの配置**
   - `ssh-on-demand.socket` と `ssh-on-demand@.service` を `/etc/systemd/system/` に配置します。
   - `vm_startup.py` を `/usr/local/bin/` に配置し、実行権限を付与します:
     ```bash
     sudo cp vm_startup.py /usr/local/bin/
     sudo chmod +x /usr/local/bin/vm_startup.py
     ```

2. **systemd の再読み込みとソケットユニットの有効化・起動**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable ssh-on-demand.socket
   sudo systemctl start ssh-on-demand.socket
   ```

## 使用方法

SSH クライアントからプロキシサーバに接続すると、systemd により自動的に `ssh-on-demand@.service` のインスタンスが起動します。
サービスは以下の処理を行います:

1. **API 呼び出し**
   指定した API エンドポイント（例: `http://192.168.0.58:5000/start_vm`）に POST リクエストを送信し、VM の IP アドレス（例: `192.168.0.57`）を取得します。
   API のレスポンスは JSON 形式またはプレーンテキストで、VM の IP アドレスを返す必要があります。

2. **VM の起動待ち**
   取得した IP の VM の SSH ポートが接続可能になるまで待機します。

3. **SSH 接続の転送**
   クライアントから渡されたソケットと、VM の SSH 接続ソケットとの間でデータを双方向に転送します。

### 接続例

```bash
ssh -p 22 <username>@<proxy-host>
```

※ `<username>` と `<proxy-host>` は適宜置き換えてください。

## API エンドポイントについて

- **API_ENDPOINT**
  `vm_startup.py` 内の変数 `API_ENDPOINT` で指定された URL へ POST リクエストを送信します。
  - 例: `{"vm_ip": "192.168.0.57"}` またはプレーンテキストで `192.168.0.57` を返す

## ログの確認

サービスのログは systemd の journal に出力されます。
以下のコマンドでログを確認できます:
```bash
sudo journalctl -u ssh-on-demand@<instance>.service
```
※ `<instance>` はテンプレートインスタンス名（例: `7-192.168.0.48:2222-192.168.0.41:62129` など）

## タイムアウト対策

- **API_TIMEOUT の調整**
  `vm_startup.py` 内の `API_TIMEOUT` を適切な秒数（例: 30秒以上）に設定してください。

- **systemd ユニットのタイムアウト設定**
  必要に応じて、`ssh-on-demand@.service` に `TimeoutStartSec` オプションを追加し、サービスの起動完了までの待機時間を延長してください。

- **SSH クライアント側キープアライブ**
  SSH 接続が切断されないよう、クライアントで `ServerAliveInterval` や `ServerAliveCountMax` のオプションを設定することも検討してください。

## 注意事項

- **標準出力と SSH プロトコル**
  ログ出力は `StandardOutput=journal` および `StandardError=journal` にリダイレクトしているため、クライアントには SSH プロトコルに必要なデータのみが送信されます。

- **セキュリティ**
  このサンプルは概念実証用です。本番環境で使用する場合は、API の認証や VM のセキュリティ対策を十分に実施してください。
