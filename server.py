# server.py
import socket
import threading

HOST = "0.0.0.0"   # listen on all interfaces
PORT = 5000

# Maps client socket -> client name
clients = {}
clients_lock = threading.Lock()

def broadcast(message, exclude_sock=None):
    """Send message to all connected clients (optionally exclude one)."""
    with clients_lock:
        for client_sock in list(clients.keys()):
            if client_sock is exclude_sock:
                continue
            try:
                client_sock.sendall(message)
            except Exception:
                # If send fails, remove client
                remove_client(client_sock)

def remove_client(client_sock):
    with clients_lock:
        name = clients.pop(client_sock, None)
    try:
        client_sock.close()
    except:
        pass
    if name:
        msg = f"[SERVER] {name} has left the chat.\n".encode('utf-8')
        broadcast(msg)

def handle_client(client_sock, addr):
    """Handle a single client: read name first, then incoming messages."""
    try:
        # Expect first message to be the client's name
        raw = client_sock.recv(1024)
        if not raw:
            remove_client(client_sock)
            return
        name = raw.decode('utf-8').strip()
        with clients_lock:
            clients[client_sock] = name
        welcome = f"[SERVER] Welcome {name}! There are {len(clients)} users online.\n"
        client_sock.sendall(welcome.encode('utf-8'))
        broadcast(f"[SERVER] {name} has joined the chat.\n".encode('utf-8'), exclude_sock=client_sock)

        # Listen for further messages
        while True:
            data = client_sock.recv(2048)
            if not data:
                break
            text = data.decode('utf-8').strip()
            # If client typed "/quit", disconnect politely
            if text.lower() == "/quit":
                break
            broadcast(f"{name}: {text}\n".encode('utf-8'))
    except Exception as e:
        # print for server-side debugging
        print(f"Error with {addr}: {e}")
    finally:
        remove_client(client_sock)

def accept_connections(server_sock):
    print(f"[SERVER] Listening on {HOST}:{PORT}")
    try:
        while True:
            client_sock, addr = server_sock.accept()
            print(f"[SERVER] Connection from {addr}")
            threading.Thread(target=handle_client, args=(client_sock, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down.")
    finally:
        with clients_lock:
            for c in list(clients.keys()):
                try:
                    c.close()
                except:
                    pass
        server_sock.close()

def main():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT))
    server_sock.listen(5)
    accept_connections(server_sock)

if __name__ == "__main__":
    main()
