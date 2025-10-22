# client.py
import socket
import threading
import sys

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000

def receive_messages(sock):
    """Thread: receive messages and print them"""
    try:
        while True:
            data = sock.recv(2048)
            if not data:
                print("[*] Disconnected from server.")
                break
            # Print incoming message
            print("\n" + data.decode('utf-8').rstrip() + "\n> ", end='', flush=True)
    except Exception:
        print("\n[*] Connection closed.")
    finally:
        try:
            sock.close()
        except:
            pass
        # Exit the program
        sys.exit(0)

def main():
    host = DEFAULT_HOST
    port = DEFAULT_PORT
    # Optional: parse host/port from argv
    if len(sys.argv) >= 2:
        host = sys.argv[1]
    if len(sys.argv) >= 3:
        port = int(sys.argv[2])

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    name = input("Enter your display name: ").strip()
    if not name:
        name = "Anonymous"
    # Send name as first message
    sock.sendall(name.encode('utf-8'))

    # Start receiver thread
    threading.Thread(target=receive_messages, args=(sock,), daemon=True).start()

    # Main loop: read input and send
    try:
        while True:
            msg = input("> ").strip()
            if not msg:
                continue
            if msg.lower() == "/quit":
                sock.sendall("/quit".encode('utf-8'))
                break
            sock.sendall(msg.encode('utf-8'))
    except KeyboardInterrupt:
        try:
            sock.sendall("/quit".encode('utf-8'))
        except:
            pass
    finally:
        sock.close()
        print("Disconnected.")

if __name__ == "__main__":
    main()
