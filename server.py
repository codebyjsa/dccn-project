# server.py
import socket
import threading
import time
import sys
import select
from datetime import datetime
import os
import tkinter as tk
from tkinter import filedialog

HOST = "0.0.0.0"   # listen on all interfaces
PORT = 5000

# Global shutdown flag
shutdown_flag = threading.Event()

# Global variables
clients = {}  # Dictionary to store connected clients: {socket: name}
clients_lock = threading.Lock()  # Thread lock for clients dictionary
shutdown_flag = threading.Event()  # Event to signal server shutdown
chat_messages = []  # Store chat messages for history
suspended_users = set()  # Set to track suspended users
kicked_users = {}  # Dictionary to store kicked users: {name: (ip, port)}

def get_timestamp():
    """Return current time in hh:mm:ss AM/PM format."""
    return datetime.now().strftime("%I:%M:%S %p")

def save_chat_log(client_sock):
    """Save chat messages to a user-selected text file."""
    try:
        # Create a hidden root window for the file dialog
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        
        # Open file dialog to choose save location
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Save Chat Log As",
            initialfile=f"chat_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        
        if not file_path:  # User cancelled the dialog
            return False
            
        # Save the chat log
        with open(file_path, 'w') as f:
            f.write("=== Chat Log ===\n\n")
            for msg in chat_messages:
                if msg['type'] == 'system':
                    f.write(f"{msg['content']}\n")
                else:
                    f.write(f"[{msg['timestamp']}] {msg['content']}\n")
        
        # Notify the client
        client_sock.sendall(f"[{get_timestamp()}] [SERVER] Chat log saved to: {file_path}\n".encode('utf-8'))
        return True
        
    except Exception as e:
        error_msg = f"[{get_timestamp()}] [SERVER] Failed to save chat log: {str(e)[:50]}...\n"
        client_sock.sendall(error_msg.encode('utf-8'))
        return False
    finally:
        if 'root' in locals():
            root.destroy()  # Clean up the Tkinter window

def list_online_users(exclude_sock=None):
    """Return a formatted string of online users"""
    with clients_lock:
        user_list = [name for sock, name in clients.items() if sock is not exclude_sock]
        return "\n".join([f"{i+1}. {name}" for i, name in enumerate(user_list)])

def send_private_message(sender_sock, recipient_name, message):
    """Send a private message to a specific user"""
    with clients_lock:
        for sock, name in clients.items():
            if name == recipient_name and sock != sender_sock:
                try:
                    sender_name = clients.get(sender_sock, "Unknown")
                    timestamp = get_timestamp()
                    sock.sendall(f"[{timestamp}] [PM from {sender_name}]: {message}\n".encode('utf-8'))
                    return True
                except:
                    return False
    return False

def broadcast(message, exclude_sock=None, is_system_message=False, sender_name=None):
    """Send message to all connected clients (optionally exclude one)."""
    timestamp = get_timestamp()
    content = message.strip()
    
    # Don't process empty messages
    if not content:
        return
    
    # Format the message with timestamp and sender
    if is_system_message:
        formatted_message = f"\033[92m[{timestamp}] {content}\033[0m"
    elif sender_name:
        formatted_message = f"[{timestamp}] {sender_name}: {content}"
    else:
        formatted_message = f"[{timestamp}] {content}"
    
    # Add to chat log if it's a regular message or a system message that's not from the server console
    if not is_system_message or (is_system_message and 'SERVER' not in content):
        # Don't log join/leave messages in the chat history
        if "has joined the chat" not in content and "has left the chat" not in content:
            chat_messages.append({
                'timestamp': timestamp,
                'type': 'system' if is_system_message else 'message',
                'content': f"{sender_name}: {content}" if sender_name else content
            })
    
    # Send to all connected clients
    with clients_lock:
        clients_to_remove = []
        
        for client_sock in list(clients.keys()):
            if client_sock is exclude_sock or shutdown_flag.is_set():
                continue
                
            try:
                # Send the formatted message with timestamp and sender
                client_sock.sendall(f"{formatted_message}\n".encode('utf-8'))
            except (ConnectionError, OSError) as e:
                # Queue for removal
                clients_to_remove.append(client_sock)
            except Exception as e:
                if not shutdown_flag.is_set():
                    print(f"[SERVER] Error sending to client: {e}")
                clients_to_remove.append(client_sock)
        
        # Remove dead clients
        for client_sock in clients_to_remove:
            remove_client(client_sock, silent=True)

def remove_client(client_sock, silent=False, was_kicked=False, server_shutdown=False):
    """Remove client from the clients dictionary.
    
    Args:
        client_sock: The client socket to remove
        silent: If True, don't broadcast leave message (used during shutdown)
        was_kicked: If True, this is a forced removal due to kick
        server_shutdown: If True, this is part of a server shutdown
    """
    global clients
    with clients_lock:
        if client_sock in clients:
            name = clients[client_sock]
            del clients[client_sock]
            
            # Only broadcast leave message if not silent and not kicked
            if not silent and not was_kicked and not server_shutdown:
                leave_msg = f"{name} has left the chat."
                broadcast(leave_msg, is_system_message=True)
                
            # Add to chat history if not a server shutdown
            if not server_shutdown:
                chat_messages.append({
                    'type': 'system',
                    'content': f"{name} has left the chat.",
                    'timestamp': get_timestamp()
                })
            
            # Remove from suspended users if they were suspended
            if name in suspended_users:
                suspended_users.remove(name)
                
            print(f"Client disconnected: {name} ({client_sock.getpeername()[0]})")
            
            # Close the socket
            try:
                if not server_shutdown:
                    client_sock.shutdown(socket.SHUT_RDWR)
                client_sock.close()
            except:
                pass

def handle_client(client_sock, addr):
    """Handle a single client: read name first, then incoming messages."""
    name = None
    try:
        # Set initial socket timeout for handshake
        client_sock.settimeout(5.0)  # Give more time for initial connection
        
        # Get client's name with timeout
        try:
            name_data = client_sock.recv(1024).decode('utf-8').strip()
            if not name_data:
                return
            name = name_data
            
            # Check if user is kicked
            if name in kicked_users:
                client_sock.sendall("\033[91mYou have been kicked from the server.\033[0m\n".encode('utf-8'))
                client_sock.close()
                return
                
        except socket.timeout:
            print(f"[SERVER] Timeout waiting for name from {addr}")
            return
        except Exception as e:
            print(f"[SERVER] Error getting name from {addr}: {e}")
            return
            
        # Disable timeout after successful connection
        client_sock.settimeout(None)
            
        # Add client to the clients dictionary
        with clients_lock:
            clients[client_sock] = name
            
        # Get connection info for server logs
        client_host, client_port = client_sock.getpeername()
        print(f"[SERVER] New connection from {client_host}:{client_port} as '{name}'")
        
        # Send welcome message to client
        welcome = f"Welcome to the chat! Type /q or /quit to exit."
        try:
            client_sock.sendall(f"\033[92m[{get_timestamp()}] {welcome}\033[0m".encode('utf-8'))
            # Notify others (without connection details)
            broadcast("A new user has joined the chat.\n", 
                     exclude_sock=client_sock, 
                     is_system_message=True)
        except:
            with clients_lock:
                clients.pop(client_sock, None)
            return

        # Listen for further messages
        while True:
            data = client_sock.recv(2048)
            if not data:
                break
            text = data.decode('utf-8').strip()
            
            # Check if user is suspended
            with clients_lock:
                if name in suspended_users and not text.lower() in ('/q', '/quit'):
                    client_sock.sendall("\033[91m[ERROR] You are suspended and cannot send messages.\033[0m\n".encode('utf-8'))
                    continue
                    
            # Handle commands
            if text == '/list_users':
                # Send list of online users to the client
                users_list = list_online_users(client_sock)
                client_sock.sendall(users_list.encode('utf-8'))
                continue
                
            elif text.startswith('/dm'):
                # Check if this is a DM user selection
                if ' ' in text:
                    parts = text.split(' ', 1)
                    if len(parts) == 2 and parts[1].isdigit():
                        try:
                            user_num = int(parts[1]) - 1
                            with clients_lock:
                                user_list = [name for sock, name in clients.items() if sock is not client_sock]
                            
                            if 0 <= user_num < len(user_list):
                                recipient = user_list[user_num]
                                client_sock.sendall(f"[SERVER] DM session started with {recipient}. Type /back to exit.\n".encode('utf-8'))
                                
                                while True:
                                    try:
                                        # Wait for message
                                        message_data = client_sock.recv(1024).decode('utf-8').strip()
                                        if not message_data:
                                            break
                                            
                                        if message_data.lower() == '/back':
                                            client_sock.sendall("[SERVER] Exited DM mode.\n".encode('utf-8'))
                                            break
                                            
                                        if send_private_message(client_sock, recipient, message_data):
                                            # Send confirmation to sender
                                            timestamp = get_timestamp()
                                            client_sock.sendall(f"[{timestamp}] [PM to {recipient}]: {message_data}\n".encode('utf-8'))
                                        else:
                                            client_sock.sendall("[SERVER] Failed to send private message. User may have disconnected.\n".encode('utf-8'))
                                            break
                                    except Exception as e:
                                        print(f"Error in DM session: {e}")
                                        break
                            else:
                                client_sock.sendall("[SERVER] Invalid user number.\n".encode('utf-8'))
                        except (ValueError, IndexError):
                            client_sock.sendall("[SERVER] Invalid selection. Use /dm to try again.\n".encode('utf-8'))
                        except Exception as e:
                            client_sock.sendall(f"[SERVER] Error: {str(e)}\n".encode('utf-8'))
                    continue
                
                # If just /dm was sent, show user list
                users_list = list_online_users(client_sock)
                client_sock.sendall(users_list.encode('utf-8'))
                    
            elif text.startswith('/save'):
                save_chat_log(client_sock)
            elif text.lower() in ("/q", "/quit"):
                break
                
            # Only broadcast if it's not a command that was already handled
            if not text.startswith(('/pm', '/save')):
                broadcast(f"{text}\n", sender_name=name)
    except Exception as e:
        # print for server-side debugging
        print(f"Error with {addr}: {e}")
    finally:
        remove_client(client_sock)

def accept_connections(server_sock):
    print(f"[SERVER] Listening on {HOST}:{PORT}")
    try:
        while not shutdown_flag.is_set():
            try:
                # Set a timeout to check the shutdown flag periodically
                server_sock.settimeout(1.0)
                client_sock, addr = server_sock.accept()
                # Don't set timeout here, let handle_client manage it
                client_thread = threading.Thread(target=handle_client, args=(client_sock, addr))
                client_thread.daemon = True
                client_thread.start()
            except socket.timeout:
                continue
            except OSError as e:
                if not shutdown_flag.is_set():
                    print(f"[SERVER] Error accepting connection: {e}")
                break
    except Exception as e:
        if not shutdown_flag.is_set():
            print(f"[SERVER] Error in accept_connections: {e}")
    finally:
        print("\n[SERVER] Shutting down...")
        with clients_lock:
            for client_sock in list(clients.keys()):
                try:
                    client_sock.shutdown(socket.SHUT_RDWR)
                    client_sock.close()
                except:
                    pass
        try:
            server_sock.shutdown(socket.SHUT_RDWR)
        except:
            pass
        server_sock.close()
        print("[SERVER] Server socket closed.")

def server_console():
    """Handle server console input for server commands and chat mode"""
    in_chat_mode = False
    
    def color_text(text, color):
        """Wrap text in ANSI color codes."""
        colors = {
            'YELLOW': '\033[93m',
            'LIGHT_RED': '\033[91m',
            'LIGHT_GREEN': '\033[92m',
            'LIGHT_BLUE': '\033[94m',
            'PURPLE': '\033[95m',
            'GRAY': '\033[90m',
            'RESET': '\033[0m',
            'BOLD': '\033[1m'
        }
        return f"{colors.get(color, '')}{text}{colors['RESET']}"
    
    def format_chat_message(timestamp, sender, message, is_system=False):
        """Format a chat message with colors."""
        if is_system:
            return f"{color_text(f'[{timestamp}]', 'GRAY')} {color_text(message, 'LIGHT_GREEN')}"
        
        colored_timestamp = color_text(f"[{timestamp}]", 'GRAY')
        colored_sender = color_text(sender, 'YELLOW')
        
        # Check for mentions
        if '@SERVER' in message.upper():
            message = message.replace('@server', color_text('@SERVER', 'BOLD'))
            message = message.replace('@SERVER', color_text('@SERVER', 'BOLD'))
        
        return f"{colored_timestamp} {colored_sender}: {message}"
    
    def print_help():
        print("\n" + color_text("Server Commands:", 'BOLD'))
        print(f"{color_text('/chat', 'LIGHT_BLUE')}    - Enter chat mode")
        print(f"{color_text('/users', 'LIGHT_BLUE')}   - Show connected users")
        print(f"{color_text('/list', 'LIGHT_BLUE')}    - List all connected clients (detailed)")
        print(f"{color_text('/kick <user>', 'LIGHT_RED')}    - Disconnect a user")
        print(f"{color_text('/kick -ls', 'LIGHT_BLUE')}      - List all kicked users")
        print(f"{color_text('/revive <user>', 'LIGHT_GREEN')} - Allow a kicked user to reconnect")
        print(f"{color_text('/suspend <user>', 'LIGHT_RED')} - Suspend a user from sending messages")
        print(f"{color_text('/suspend -ls', 'LIGHT_BLUE')}   - List all suspended users")
        print(f"{color_text('/!suspend <user>', 'LIGHT_GREEN')} - Unsuspend a user")
        print(f"{color_text('/help', 'LIGHT_BLUE')}    - Show this help")
        print(f"{color_text('/q', 'LIGHT_BLUE')}       - Shutdown server")
        print()
    
    print_help()
    
    while not shutdown_flag.is_set():
        try:
            # Get input with timeout
            try:
                prompt = color_text("server> " if not in_chat_mode else "chat> ", 'LIGHT_BLUE')
                user_input = input(prompt).strip()
            except (select.error, KeyboardInterrupt):
                if in_chat_mode:
                    print("\n" + color_text("Type /back to exit chat mode", 'YELLOW'))
                    continue
                print("\n" + color_text("Type /q to shutdown the server", 'YELLOW'))
                continue
                
            if not user_input:
                continue
                
            # Handle commands in both modes
            cmd = user_input.lower()
            
            # Toggle chat mode
            if cmd == '/chat' and not in_chat_mode:
                print("\n" + color_text("Entering chat mode. Type /back to return to server console.", 'LIGHT_GREEN'))
                print(color_text("Chat history (last 10 messages):", 'BOLD'))
                
                # Show recent chat history with proper formatting
                if not chat_messages:
                    print(color_text("No recent messages.", 'GRAY'))
                else:
                    for msg in chat_messages[-10:]:
                        if msg['type'] == 'system':
                            print(format_chat_message(msg['timestamp'], "SYSTEM", msg['content'], is_system=True))
                        else:
                            sender, content = msg['content'].split(': ', 1) if ': ' in msg['content'] else ("UNKNOWN", msg['content'])
                            print(format_chat_message(msg['timestamp'], sender, content))
                
                in_chat_mode = True
                continue
                
            elif cmd == '/back' and in_chat_mode:
                print("\nExiting chat mode.")
                in_chat_mode = False
                continue
                
            # Helper function to find client by name
            def find_client_by_name(target_name):
                with clients_lock:
                    for sock, name in clients.items():
                        if name.lower() == target_name.lower():
                            return sock, name
                    return None, None

            # Handle server commands (only in server mode)
            if not in_chat_mode:
                if cmd in ('/q', '/quit'):
                    print("\n" + color_text("Shutting down server...", 'LIGHT_RED'))
                    shutdown_flag.set()
                    break
                
                # List connected clients (detailed)
                elif cmd == '/list':
                    print("\n" + color_text("Connected Clients:", 'BOLD'))
                    print("-" * 50)
                    with clients_lock:
                        if not clients:
                            print(color_text("  No users connected.", 'GRAY'))
                        else:
                            for i, (sock, name) in enumerate(clients.items(), 1):
                                try:
                                    addr = sock.getpeername()
                                    status = color_text("SUSPENDED", 'LIGHT_RED') if name in suspended_users else color_text("ACTIVE", 'LIGHT_GREEN')
                                    print(f"  {i}. {color_text(name, 'YELLOW')} ({color_text(f'{addr[0]}:{addr[1]}', 'GRAY')}) - {status}")
                                except:
                                    print(f"  {i}. {color_text(name, 'YELLOW')} {color_text('(disconnected)', 'GRAY')}")
                    print()
                
                # Show basic user list
                elif cmd == '/users':
                    print("\n" + color_text("Connected users:", 'BOLD'))
                    with clients_lock:
                        if not clients:
                            print(color_text("  No users connected.", 'GRAY'))
                        else:
                            for i, (sock, name) in enumerate(clients.items(), 1):
                                status = "(suspended)" if name in suspended_users else ""
                                print(f"  {i}. {color_text(name, 'YELLOW')} {color_text(status, 'LIGHT_RED')}")
                    print()
                
                # Kick a user or list kicked users
                elif cmd.startswith('/kick '):
                    args = user_input.split(' ')[1:]
                    
                    # Handle list command
                    if args and args[0] == '-ls':
                        if not kicked_users:
                            print(color_text("\nNo users have been kicked.", 'LIGHT_YELLOW'))
                        else:
                            print("\n" + color_text("Kicked Users:", 'BOLD') + " (use /revive <user> to allow reconnection)")
                            print("-" * 60)
                            for i, (name, (host, port)) in enumerate(kicked_users.items(), 1):
                                print(f"  {i}. {color_text(name, 'YELLOW')} - {color_text(f'{host}:{port}', 'GRAY')}")
                        continue
                        
                    target_name = ' '.join(args).strip()
                    if not target_name:
                        print(color_text("\nError: Please specify a username to kick or use '/kick -ls' to list kicked users", 'LIGHT_RED'))
                        print(color_text("  /kick <username> - Kick a user", 'GRAY'))
                        print(color_text("  /kick -ls       - List all kicked users", 'GRAY'))
                        continue
                        
                    target_sock, target_name = find_client_by_name(target_name)
                    if target_sock:
                        try:
                            # Get client info before removing
                            client_host, client_port = target_sock.getpeername()
                            # Store kicked user info for potential revival
                            kicked_users[target_name] = (client_host, client_port)
                            
                            target_sock.sendall("\033[91mYou have been kicked by the server admin.\033[0m\n".encode('utf-8'))
                            print(color_text(f"\nKicked user: {target_name}", 'LIGHT_RED'))
                            # Remove from suspended users if they were suspended
                            if target_name in suspended_users:
                                suspended_users.remove(name)
                            # Close the connection with was_kicked flag
                            remove_client(target_sock, was_kicked=True)
                        except Exception as e:
                            print(color_text(f"\nError kicking user {target_name}: {e}", 'LIGHT_RED'))
                    else:
                        print(color_text(f"\nUser '{target_name}' not found or already kicked", 'LIGHT_RED'))
                
                # Revive a kicked user
                elif cmd.startswith('/revive '):
                    target_name = ' '.join(user_input.split(' ')[1:]).strip()
                    if not target_name:
                        print(color_text("\nError: Please specify a username to revive", 'LIGHT_RED'))
                        continue
                        
                    if target_name in kicked_users:
                        del kicked_users[target_name]
                        print(color_text(f"\nUser '{target_name}' can now reconnect", 'LIGHT_GREEN'))
                        
                        # Notify the user if they're currently connected
                        target_sock, _ = find_client_by_name(target_name)
                        if target_sock:
                            try:
                                target_sock.sendall("\033[92mYou have been revived by the server admin. You can now send messages.\033[0m\n".encode('utf-8'))
                            except:
                                pass
                    else:
                        print(color_text(f"\nUser '{target_name}' was not found in the kicked users list", 'LIGHT_YELLOW'))
                
                # Suspend a user or list suspended users
                elif cmd.startswith('/suspend '):
                    args = user_input.split(' ')[1:]
                    
                    # Handle list command
                    if args and args[0] == '-ls':
                        if not suspended_users:
                            print(color_text("\nNo users are currently suspended.", 'LIGHT_YELLOW'))
                        else:
                            print("\n" + color_text("Suspended Users:", 'BOLD') + " (use /!suspend <user> to unsuspend)")
                            print("-" * 60)
                            for i, name in enumerate(sorted(suspended_users), 1):
                                print(f"  {i}. {color_text(name, 'YELLOW')}")
                        continue
                        
                    target_name = ' '.join(args).strip()
                    if not target_name:
                        print(color_text("\nError: Please specify a username to suspend or use '/suspend -ls' to list suspended users", 'LIGHT_RED'))
                        print(color_text("  /suspend <username> - Suspend a user", 'GRAY'))
                        print(color_text("  /suspend -ls       - List all suspended users", 'GRAY'))
                        continue
                        
                    _, target_name = find_client_by_name(target_name)
                    if target_name:
                        if target_name in suspended_users:
                            print(color_text(f"\nUser '{target_name}' is already suspended. Use /!suspend to unsuspend.", 'LIGHT_YELLOW'))
                        else:
                            suspended_users.add(target_name)
                            print(color_text(f"\nSuspended user: {target_name}", 'LIGHT_RED'))
                            try:
                                # Find the socket to send the suspend message
                                target_sock, _ = find_client_by_name(target_name)
                                if target_sock:
                                    target_sock.sendall("\033[91mYou have been suspended by the server admin and cannot send messages.\033[0m\n".encode('utf-8'))
                            except:
                                pass
                    else:
                        print(color_text(f"\nUser '{target_name}' not found", 'LIGHT_RED'))
                
                # Unsuspend a user
                elif cmd.startswith('/!suspend '):
                    target_name = ' '.join(user_input.split(' ')[1:]).strip()
                    if not target_name:
                        print(color_text("\nError: Please specify a username to unsuspend", 'LIGHT_RED'))
                        continue
                        
                    _, target_name = find_client_by_name(target_name)
                    if target_name:
                        if target_name in suspended_users:
                            suspended_users.remove(target_name)
                            print(color_text(f"\nRemoved suspension for user: {target_name}", 'LIGHT_GREEN'))
                            try:
                                # Find the socket to send the unsuspend message
                                target_sock, _ = find_client_by_name(target_name)
                                if target_sock:
                                    target_sock.sendall("\033[92mYou have been unsuspended by the server admin.\033[0m\n".encode('utf-8'))
                            except:
                                pass
                        else:
                            print(color_text(f"\nUser '{target_name}' is not currently suspended", 'LIGHT_YELLOW'))
                    else:
                        print(color_text(f"\nUser '{target_name}' not found", 'LIGHT_RED'))
                
                elif cmd in ['/h', '/help']:
                    print_help()
                else:
                    print("\n" + color_text("Unknown command. Type /help for available commands.", 'LIGHT_RED'))
            # Handle chat mode input
            elif in_chat_mode:
                # Check for commands in chat mode
                if user_input.startswith('/'):
                    print(color_text("\nCommands are not supported in chat mode. Type /back to return to server console.", 'LIGHT_RED'))
                    continue
                    
        except Exception as e:
            if not shutdown_flag.is_set():
                print(f"Error: {e}")
            continue

def main():
    global shutdown_flag
    
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.settimeout(1.0)  # Set timeout for socket operations
    
    try:
        server_sock.bind((HOST, PORT))
        server_sock.listen(5)  # Allow queue of up to 5 pending connections

        print("\n" + "="*50)
        print("Server started successfully!")
        print(f"Listening on {HOST}:{PORT}")
        print("Type /help for available commands")
        print("="*50 + "\n")

        # Start accepting connections in a separate thread
        accept_thread = threading.Thread(target=accept_connections, args=(server_sock,))
        accept_thread.daemon = True
        accept_thread.start()
        
        # Start the server console in the main thread
        server_console()
        
    except KeyboardInterrupt:
        print("\nShutting down server...")
        
        # Set a short timeout for the final operations
        timeout = time.time() + 2.0  # 2 second timeout for cleanup
        
        # Wait for threads to notice the shutdown flag
        while time.time() < timeout and (accept_thread.is_alive() or console_thread.is_alive()):
            time.sleep(0.1)
        
        # Close all client connections without sending leave messages
        with clients_lock:
            for client_sock in list(clients.keys()):
                try:
                    client_sock.shutdown(socket.SHUT_RDWR)
                except:
                    pass
                try:
                    client_sock.close()
                except:
                    pass
        
        # Clear clients list
        with clients_lock:
            clients.clear()
        
        # Close server socket
        try:
            server_sock.shutdown(socket.SHUT_RDWR)
        except:
            pass
        server_sock.close()
        
        print("Server has been shut down.")
        sys.exit(0)

if __name__ == "__main__":
    main()
