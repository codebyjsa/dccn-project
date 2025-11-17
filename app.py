from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_socketio import SocketIO, join_room, leave_room, emit, disconnect
import os
import sys
from datetime import datetime
from collections import defaultdict

# Determine the best async mode
if sys.platform == 'win32':
    async_mode = 'threading'
else:
    try:
        import eventlet
        async_mode = 'eventlet'
    except ImportError:
        try:
            from gevent import monkey
            async_mode = 'gevent'
        except ImportError:
            async_mode = 'threading'

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, async_mode=async_mode)

# Store connected users: {socket_id: {'username': str, 'rooms': set, 'sid': str}}
users = {}
# Store user socket mappings: {username: socket_id}
user_sockets = {}
# Store private messages: {(user1, user2): [messages]}
private_messages = defaultdict(list)

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('chat'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    print("\n=== DEBUG: Login route hit ===")
    print(f"Form data: {request.form}")
    
    username = request.form.get('username')
    print(f"DEBUG: Username from form: {username}")
    
    if not username:
        print("DEBUG: No username provided, redirecting to index")
        return redirect(url_for('index'))
    
    # Get the client's IP address
    if request.headers.get('X-Forwarded-For'):
        ip = request.headers.get('X-Forwarded-For').split(',')[0]  # For when behind a proxy
    else:
        ip = request.remote_addr
    
    print("\n" + "="*50)
    print(f"🔔 NEW LOGIN DETECTED")
    print(f"👤 Username: {username}")
    print(f"🌐 IP Address: {ip}")
    print(f"🕒 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📱 User Agent: {request.user_agent}")
    print("="*50 + "\n")
    
    session['username'] = username
    print(f"DEBUG: Session set for user: {session.get('username')}")
    return redirect(url_for('chat'))

@app.route('/api/online_users')
def get_online_users():
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    online_users = [{'username': user_data['username']} 
                   for user_data in users.values() 
                   if user_data['username'] != session['username']]
    
    return jsonify({'users': online_users})

@app.route('/chat')
def chat():
    if 'username' not in session:
        return redirect(url_for('index'))
    return render_template('chat.html', username=session['username'])

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))

@socketio.on('connect')
def handle_connect():
    if 'username' in session:
        username = session['username']
        users[request.sid] = {
            'username': username,
            'rooms': {'general'},
            'sid': request.sid
        }
        user_sockets[username] = request.sid
        join_room('general')
        emit('user_joined', 
             {'username': username, 'message': f'{username} has joined the chat'}, 
             room='general')
        emit('update_users', 
             {'users': [u['username'] for u in users.values()]}, 
             room='general')

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in users:
        user_data = users[request.sid]
        username = user_data['username']
        
        # Remove user from tracking
        users.pop(request.sid, None)
        user_sockets.pop(username, None)
        
        # Notify others
        emit('user_left', 
             {'username': username, 'message': f'{username} has left the chat'}, 
             room='general')
        emit('update_users', 
             {'users': [u['username'] for u in users.values()]}, 
             room='general')

@socketio.on('send_message')
def handle_send_message(data):
    print("\n=== NEW MESSAGE RECEIVED ===")
    print(f"Session data: {dict(session)}")
    print(f"Message data: {data}")
    
    if 'username' not in session:
        print("No username in session, ignoring message")
        return {'status': 'error', 'message': 'Not authenticated'}
    
    username = session['username']
    message = data.get('message', '').strip()
    recipient = data.get('recipient')  # None for public messages
    timestamp = data.get('timestamp') or datetime.now().strftime('%H:%M:%S')
    
    if not message:
        print("Empty message, ignoring")
        return {'status': 'error', 'message': 'Message cannot be empty'}
    
    message_data = {
        'sender': username,
        'message': message,
        'timestamp': timestamp,
        'is_private': bool(recipient)
    }
    
    print(f"Processing message: {message_data}")
    
    if recipient:
        # Private message
        print(f"Processing private message to {recipient}")
        if recipient in user_sockets:
            # Store message in the conversation history
            key = tuple(sorted([username, recipient]))
            private_messages.setdefault(key, []).append(message_data)
            
            # Send to recipient
            print(f"Sending private message to {recipient} (socket: {user_sockets[recipient]})")
            emit('private_message', {
                'from': username,
                'message': message,
                'timestamp': timestamp,
                'is_private': True
            }, room=user_sockets[recipient])
            
            # Send confirmation to sender
            print(f"Sending confirmation to sender {username}")
            emit('private_message', {
                'from': username,
                'to': recipient,
                'message': message,
                'timestamp': timestamp,
                'is_private': True
            }, room=request.sid)
            
            return {
                'status': 'delivered',
                'is_private': True,
                'to': recipient,
                'message': message,
                'timestamp': timestamp
            }
        else:
            print(f"Recipient {recipient} not found in user_sockets")
            return {'status': 'error', 'message': 'Recipient not found'}
    else:
        # Public message
        print(f"Broadcasting public message to room 'general'")
        emit('new_message', {
            'username': username,
            'message': message,
            'timestamp': timestamp,
            'is_private': False
        }, room='general')
        
        print("Message broadcasted successfully")
        return {'status': 'broadcasted', 'timestamp': timestamp}

@socketio.on('get_private_messages')
def handle_get_private_messages(data):
    if 'username' not in session:
        return
    
    other_user = data.get('with_user')
    if not other_user:
        return
    
    username = session['username']
    key = tuple(sorted([username, other_user]))
    messages = private_messages.get(key, [])
    
    emit('private_messages', {
        'with_user': other_user,
        'messages': messages
    })

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in users:
        username = users[request.sid]
        del users[request.sid]
        leave_room('general')
        emit('user_left', {'username': username, 'message': f'{username} has left the chat'}, room='general')
        emit('update_users', list(users.values()), room='general')

@socketio.on('send_message')
def handle_send_message(data):
    if 'username' in session:
        message = data.get('message', '').strip()
        if message:
            timestamp = datetime.now().strftime('%I:%M %p')
            emit('new_message', {
                'username': session['username'],
                'message': message,
                'timestamp': timestamp
            }, room='general')

def find_available_port(start_port=3000, max_attempts=10):
    """Find an available port starting from start_port"""
    import socket
    
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return port
        except OSError:
            continue
    return start_port  # Fallback to start_port if no port is available

if __name__ == '__main__':
    import socket
    
    # Try to find an available port starting from 3000
    port = find_available_port(3000)
    
    # Disable socket reuse to avoid 'Address already in use' errors
    import socket
    socket.socket._bind = socket.socket.bind
    def socket_bind(self, *args, **kwargs):
        self.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return socket.socket._bind(self, *args, **kwargs)
    socket.socket.bind = socket_bind
    
    # Get the local IP address
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except:
        local_ip = 'localhost'
    
    print("\n" + "="*60)
    print("🚀 DCCN Web Chat Server")
    print("="*60)
    print(f"\n🌐 Local Access:    http://localhost:{port}")
    print(f"🌍 Network Access: http://{local_ip}:{port}")
    print("\n🔗 To access from other devices:")
    print("1. Connect to the same WiFi/network")
    print(f"2. Open a web browser and go to: http://{local_ip}:{port}")
    print("\n💡 Tip: If you can't connect, check your firewall settings")
    print("      or try temporarily disabling it for testing")
    print("\n🛑 Press Ctrl+C to stop the server")
    print("="*60 + "\n")
    
    # Run the app with error handling
    try:
        print(f"\n🔄 Starting server on port {port}...")
        socketio.run(app, 
                   host='0.0.0.0', 
                   port=port, 
                   debug=True,
                   allow_unsafe_werkzeug=True,
                   use_reloader=False)
    except Exception as e:
        print("\n" + "!"*60)
        print("ERROR: Could not start the server. Common solutions:")
        print(f"1. Try a different port by editing the code: port = 3000")
        print(f"2. Check if port {port} is in use: lsof -i :{port}")
        print(f"3. Try temporarily disabling your firewall: sudo ufw disable")
        print("\nError details:", str(e))
        print("!"*60 + "\n")
