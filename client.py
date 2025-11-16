# client.py
import socket
import threading
import sys
import os
import time
import select

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000

# ANSI color codes
COLORS = {
    'YELLOW': '\033[93m',
    'LIGHT_RED': '\033[91m',
    'LIGHT_GREEN': '\033[92m',
    'LIGHT_BLUE': '\033[94m',
    'RESET': '\033[0m',
    'BOLD': '\033[1m',
}

def color_text(text, color):
    """Wrap text in ANSI color codes."""
    return f"{COLORS[color]}{text}{COLORS['RESET']}"

def format_message(message, client_name):
    """Format message with appropriate colors."""
    # Server messages in green
    if '[SERVER]' in message:
        return f"\033[92m{message}\033[0m"
        
    # Private messages - format sender/receiver info
    if '[PM from' in message or '[PM to' in message:
        # Split the message into parts
        parts = message.split('] ', 1)
        if len(parts) == 2:
            timestamp, rest = parts
            if ': ' in rest:
                # Color the timestamp and sender info
                colored_timestamp = f"\033[90m{timestamp}]\033[0m"
                info, content = rest.split(': ', 1)
                colored_info = f"\033[95m{info}\033[0m"
                return f"{colored_timestamp} {colored_info}: {content}"
        return message
        
    # Commands in blue
    if any(cmd in message.lower() for cmd in ['/q', '/quit', '/save']):
        return f"\033[94m{message}\033[0m"
    
    # Check for mentions (only check if the message is from someone else)
    is_mentioned = False
    if ': ' in message:
        sender = message.split('] ')[1].split(':')[0] if '] ' in message else ''
        if sender != client_name:  # Only check mentions in messages from others
            is_mentioned = (f"@{client_name}" in message or "@everyone" in message) and client_name != "SERVER"
    
    # Extract the sender's name (part after timestamp and before ':')
    parts = message.split('] ', 1)
    if len(parts) == 2:
        timestamp, rest = parts
        if ': ' in rest:
            sender, content = rest.split(': ', 1)
            # Color the timestamp
            colored_timestamp = f"\033[90m{timestamp}]\033[0m"  # Dark gray timestamp
            
            # If this message is from the current user (sender's view)
            if sender == client_name:
                # Show own name in red
                colored_sender = f"\033[91m{sender}\033[0m"
                return f"{colored_timestamp} {colored_sender}: {content}"
            
            # For messages from others
            colored_sender = f"\033[93m{sender}\033[0m"  # Other senders in yellow
            
            # If this message mentions the current user, highlight the mention
            if is_mentioned:
                # Highlight the mention in the content
                content = content.replace(f"@{client_name}", f"\033[1;93m@{client_name}\033[0m")
                return f"{colored_timestamp} {colored_sender}: \033[93m{content}\033[0m"
            
            # Regular received message (white text)
            return f"{colored_timestamp} {colored_sender}: {content}"
    
    return message

def handle_server_messages(sock, name):
    """Handle incoming messages from the server with DM support."""
    shutdown_flag = threading.Event()
    while not shutdown_flag.is_set():
        try:
            data = sock.recv(4096)
            if not data:
                print("\n\033[91m[!] Disconnected from server.\033[0m")
                shutdown_flag.set()
                os._exit(1)  # Exit the entire program
                
            # Split multiple messages (in case they were buffered together)
            messages = data.decode('utf-8').split('\n')
            
            for message in messages:
                if not message.strip():
                    continue
                    
                message = message.strip()
                
                # Check for server shutdown message
                if "shutting down" in message.lower() or "server is shutting down" in message.lower():
                    print("\n\033[91m[!] Server is shutting down. Disconnecting...\033[0m")
                    shutdown_flag.set()
                    os._exit(0)
                    
                # Format the message with colors
                formatted_message = format_message(message, name)
                
                # Handle different message types
                if message.startswith("DM_FROM:"):
                    # Handle incoming DM
                    parts = message.split(':', 2)
                    if len(parts) == 3:
                        sender = parts[1]
                        dm_content = parts[2]
                        print(f"\n{color_text('[DM from ', 'LIGHT_MAGENTA')}{color_text(sender, 'LIGHT_CYAN')}{color_text(']: ', 'LIGHT_MAGENTA')}{dm_content}")
                    else:
                        print(f"\n{formatted_message}")
                elif message == "USER_LEFT":
                    continue  # Handled elsewhere
                else:
                    # Print the formatted message with proper prompt
                    print(f"\r{formatted_message}")
                    print(f"{name}: ", end='', flush=True)
            
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            if not shutdown_flag.is_set():
                print("\n\033[91m[!] Lost connection to server. Please restart the client.\033[0m")
                shutdown_flag.set()
                os._exit(1)
            break
        except Exception as e:
            if not shutdown_flag.is_set():
                print(f"\n\033[91m[!] Error: {e}. Disconnected from server.\033[0m")
                shutdown_flag.set()
                os._exit(1)
            break

def handle_private_message(sock):
    """Handle private message flow with back command support"""
    try:
        # Request the user list from the server
        try:
            sock.sendall("/list_users\n".encode('utf-8'))
        except Exception as e:
            print(f"\nError requesting user list: {e}")
            return
            
        # Get list of users from server
        users_list = ''
        sock.settimeout(5.0)
        try:
            data = sock.recv(4096).decode('utf-8')
            if not data:
                print("\nConnection to server lost.")
                return
            users_list = data.strip()
        except socket.timeout:
            print("\nTimed out waiting for user list.")
            return
        except Exception as e:
            print(f"\nError getting user list: {e}")
            return
        
        if not users_list:
            print("\nNo other users available for DM.")
            return
            
        # Display users list
        print("\n" + "-" * 40)
        print("Select a user to message (or /back to cancel):")
        print(users_list)
        print("-" * 40)
        
        # Get user selection
        while True:
            try:
                selection = input("\nEnter user number (or /back): ").strip()
                
                # Handle back command
                if selection.lower() == '/back':
                    print("\nDM cancelled.")
                    return
                    
                # Validate input
                if not selection.isdigit():
                    print("\nPlease enter a valid user number or /back")
                    continue
                    
                # Send DM command with selected user
                try:
                    sock.sendall(f"/dm {selection}\n".encode('utf-8'))
                except:
                    print("\nError communicating with server.")
                    return
                
                # Get server response
                try:
                    sock.settimeout(5.0)
                    response = ''
                    while not response:
                        data = sock.recv(4096).decode('utf-8')
                        if data:
                            response = data.strip()
                            
                    if 'invalid' in response.lower():
                        print(f"\n{response}")
                        continue
                        
                    # If we get here, we're in DM mode
                    print(f"\n{'-'*40}\nDM Mode (type /back to exit DM)\n{'-'*40}")
                    
                    while True:
                        try:
                            # Get message content
                            message = input("You: ").strip()
                            
                            # Handle back command in DM mode
                            if message.lower() == '/back':
                                print("\nExited DM mode.")
                                return
                                
                            # Send message to server
                            try:
                                sock.sendall(f"{message}\n".encode('utf-8'))
                            except:
                                print("\nError sending message. Connection lost.")
                                return
                            
                            # Wait for message confirmation
                            try:
                                sock.settimeout(5.0)
                                data = sock.recv(4096).decode('utf-8')
                                if not data:
                                    print("\nConnection to server lost.")
                                    return
                                if data.strip() == "USER_LEFT":
                                    print("\nRecipient has left the chat. Exiting DM mode.")
                                    return
                            except socket.timeout:
                                print("\nNo response from server. Message may not have been delivered.")
                                continue
                            except Exception as e:
                                print(f"\nError: {e}")
                                return
                                
                        except KeyboardInterrupt:
                            print("\nUse /back to exit DM mode or /q to quit.")
                            continue
                        except Exception as e:
                            print(f"\nError in DM: {e}")
                            return
                            
                except socket.timeout:
                    print("\nTimed out waiting for server response.")
                    return
                except Exception as e:
                    print(f"\nError: {e}")
                    return
                    
            except KeyboardInterrupt:
                print("\nUse /back to cancel or /q to quit.")
                continue
            except Exception as e:
                print(f"\nError: {e}")
                return
                
    except Exception as e:
        print(f"\n{color_text('Error in private message:', 'LIGHT_RED')} {e}")
    finally:
        # Make sure to clear any pending messages
        sock.settimeout(0.1)
        try:
            while True:
                data = sock.recv(4096)
                if not data:
                    break
        except:
            pass
        sock.settimeout(None)

def handle_user_input(sock, name):
    """Handle user input and send messages to the server."""
    shutdown_flag = threading.Event()
    
    def send_safe(sock, message):
        """Safely send a message to the server"""
        try:
            sock.sendall((message + '\n').encode('utf-8'))
            return True
        except Exception as e:
            print(f"\nError sending message: {e}")
            return False
    
    try:
        while not shutdown_flag.is_set():
            try:
                # Print prompt and get input
                prompt = f"{name}: "
                message = input(prompt).strip()
                
                if not message:
                    continue
                    
                # Handle quit commands
                if message.lower() in ('/q', '/quit'):
                    if send_safe(sock, message):
                        print("Disconnecting...")
                    shutdown_flag.set()
                    break
                    
                # Handle DM command
                if message.lower() == '/dm':
                    handle_private_message(sock)
                    continue
                    
                # Send regular message
                if not send_safe(sock, message):
                    print("Failed to send message. Connection may be lost.")
                    shutdown_flag.set()
                    break
                    
            except KeyboardInterrupt:
                print("\nUse /q or /quit to exit properly.")
            except Exception as e:
                print(f"\nError: {e}")
                shutdown_flag.set()
                break
                
    finally:
        # Only close the socket and exit when we're completely done
        try:
            sock.close()
        except:
            pass

def connect_to_server(host, port, name, retries=3, delay=2):
    """Attempt to connect to the server with retries"""
    for attempt in range(retries):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            sock.settimeout(5.0)  # 5 second timeout for connection
            sock.connect((host, port))
            
            # Set keepalive options (works on Linux, may need adjustment for other OS)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 5)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
            
            # Send name first
            sock.settimeout(10.0)  # 10 second timeout for initial handshake
            sock.sendall(name.encode('utf-8'))
            
            # Verify connection is still alive
            try:
                # Try to receive a small amount of data to verify connection
                ready = select.select([sock], [], [], 1.0)
                if ready[0]:
                    data = sock.recv(1, socket.MSG_PEEK)
                    if not data:  # Connection closed by server
                        raise ConnectionError("Server closed the connection")
            except (socket.timeout, BlockingIOError):
                pass  # No data available is fine, connection is still alive
                
            return sock
            
        except socket.timeout:
            print(f"\rConnection attempt {attempt + 1}/{retries} timed out")
            if attempt < retries - 1:
                time.sleep(delay)
        except Exception as e:
            print(f"\rConnection attempt {attempt + 1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
    return None

def main():
    host = DEFAULT_HOST
    port = DEFAULT_PORT
    # Optional: parse host/port from argv
    if len(sys.argv) >= 2:
        host = sys.argv[1]
    if len(sys.argv) >= 3:
        port = int(sys.argv[2])

    # Get user's name
    name = input("Enter your name: ").strip()
    while not name:
        name = input("Name cannot be empty. Enter your name: ").strip()

    # Connect to server with retries
    print(f"Connecting to {host}:{port}...")
    sock = connect_to_server(host, port, name)
    if not sock:
        print("Failed to connect to server after several attempts. Please try again later.")
        sys.exit(1)
    
    print("Connected to server!")
    sock.settimeout(None)  # Disable timeout after successful connection

    try:
        # Start receiving thread
        threading.Thread(target=handle_server_messages, args=(sock, name), daemon=True).start()

        # Start input handling in main thread
        handle_user_input(sock, name)
    except KeyboardInterrupt:
        print(color_text("\nDisconnecting...", 'LIGHT_BLUE'))
    finally:
        try:
            sock.sendall("/quit".encode('utf-8'))
        except:
            pass
        sock.close()
        print("Disconnected.")

if __name__ == "__main__":
    main()
