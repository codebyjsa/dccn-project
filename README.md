# Real-Time CLI Chat Application

A command-line based real-time chat application that allows multiple users to communicate over a local network. Built with Python's socket programming and multithreading with enhanced user experience features.

## ✨ Features

- Real-time messaging with instant updates
- Multiple client support with unique usernames
- Intuitive CLI interface with colored output
- Timestamped messages (12-hour format with AM/PM)
- Graceful connection handling
- Cross-platform compatibility (Windows, macOS, Linux)
- Save chat history with file dialog
- Privacy-focused (no chat content in server logs)
- Color-coded messages for better readability
- @mentions to notify specific users
- @everyone tag for group notifications
- Server console with interactive chat mode
- Server operator can participate in chat as "SERVER"
- View last 10 messages when entering chat mode
- Direct Messages (DMs) with `/dm` command
- `/back` command to exit DM mode or cancel actions
- Admin commands for user management

## 🛠️ Technologies Used

- **Python 3.x** - Core programming language
- **Socket Programming** - For network communication
- **Threading** - For handling multiple clients simultaneously
- **DateTime** - For message timestamps
- **Tkinter** - For file dialogs (save functionality)
- **OS** - For file operations

## 📋 Prerequisites

- Python 3.6 or higher
- Basic understanding of command line/terminal
- Network connectivity (for multi-machine communication)

## 🚀 Getting Started

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd dccn-project
   ```

2. **Set up a virtual environment (optional but recommended)**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
   
3. **No additional dependencies needed**
   - The project uses Python's standard library only

## 🖥️ How to Run

### Starting the Server
1. Open a terminal window
2. Navigate to the project directory
3. Run the server:
   ```bash
   python3 server.py
   ```
   - The server will start on `0.0.0.0:5000` by default
   - You should see: `[SERVER] Listening on 0.0.0.0:5000`
   - The server console is now interactive - type messages and press Enter to broadcast to all clients
   - Type `/q` or `/quit` to shut down the server gracefully

### Connecting Clients
1. Open a new terminal window for each client
2. Navigate to the project directory
3. Run the client:
   ```bash
   python3 client.py
   ```
4. When prompted, enter a display name
5. Start chatting!

## 📝 Usage

### Basic Commands
- Type your message and press Enter to send
- To disconnect, use either:
  - `/q` - Quick quit
  - `/quit` - Full quit command
- Save chat history:
  - `/save` - Opens a file dialog to save chat log
- Direct Messages:
  - `/dm` - Start a private conversation
  - `/back` - Exit DM mode or cancel current action
- Note: Commands are case-insensitive

### Server Console

#### Admin Commands
- `/list` or `/users` - Show all connected clients
- `/kick <username>` - Disconnect a client
- `/suspend <username>` - Prevent a user from sending messages
- `/revive <username>` - Allow a kicked user to reconnect
- `/!suspend <username>` - Unsuspend a user
- `/kick -ls` - List all kicked users
- `/suspend -ls` - List all suspended users
- `/q` or `/quit` - Shut down the server gracefully
- `/help` - Show available commands

Server messages appear in green with `[SERVER MESSAGE]` prefix

#### Chat Mode
- Type `/chat` to enter chat mode
  - View the last 10 messages in the chat
  - Your messages will appear as `[timestamp] You: message` (in red)
  - Other users see your messages as `[timestamp] SERVER: message`
  - Type `/back` to exit chat mode and return to server console
- In chat mode, you can:
  - See real-time messages from all users
  - Participate in group conversations
  - Use @mentions to notify specific users (e.g., `@username`)
  - Use @everyone to notify all users
- Server console commands (except `/back`) are not available in chat mode

### Messaging Features

#### Direct Messages
- Use `/dm` to start a private conversation
- Select a user from the online users list
- Type your message to send it privately
- Use `/back` at any time to cancel the DM or exit DM mode
- Private messages are highlighted in the interface
- Only the sender and recipient can see the message content
- If a user disconnects while in DM, you'll be notified

#### Public Messages
- **Colored Messages**: 
  - Your name appears in red
  - Other users' names appear in yellow
  - Server messages in green
  - Server announcements in green with `[SERVER MESSAGE]` prefix
  - Server operator messages appear as `[timestamp] SERVER: message`
  - Commands in blue
  - Timestamps in dark gray
  - Server console input prompt in blue

- **Mentions**:
  - Use `@username` to mention a specific user
  - Use `@everyone` to notify all users
  - Use `@server` to get the server operator's attention
  - Mentioned users see the message highlighted in yellow
  - Only the mentioned user sees the highlight
  - Server operator sees all mentions in the server console

### Multi-User Chat
- Each user gets a unique display name
- All messages are broadcast to all connected users
- Timestamps show when each message was sent
- Clean, organized message formatting

## 💾 Saving Chat History

1. Type `/save` in the chat
2. A file dialog will appear (on the server side)
3. Choose where to save the chat log (saved as .txt)
4. The log will be saved in a clean, readable format with:
   - All messages in chronological order
   - Timestamps for each message
   - System messages (joins/leaves)
   - Clear section headers
   - Mentions are preserved in the saved log

## 🔧 Troubleshooting

### Common Issues

#### Port Already in Use
If you see `[Errno 98] Address already in use`:
1. Find the process using port 5000:
   ```bash
   lsof -i :5000
   # or
   netstat -tuln | grep 5000
   ```
2. Kill the process:
   ```bash
   kill <PID>
   ```
   or forcefully:
   ```bash
   kill -9 <PID>
   ```

#### Save Dialog Not Appearing
- Ensure you have a graphical environment running (X11/Wayland on Linux)
- If running on a headless server, you'll need to set up X11 forwarding or use a different save method
- The server must have display access to show the file dialog

### Connection Issues
- Ensure the server is running before starting clients
- Check if you can ping the server's IP address
- Verify the port number matches in both server and client

## 🧩 Project Structure

```
dccn-project/
├── server.py        # Main server implementation
├── client.py        # Client application
└── README.md        # This documentation file
```

### server.py
- Handles multiple client connections
- Manages message broadcasting
- Tracks connected users
- Handles user disconnections

### client.py
- Connects to the chat server
- Provides command-line interface
- Handles message sending/receiving

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details

## 👥 Team

- Jai Kishan Soni
- Jasdeep Singh
- Krishna Bansal

D2 IT B

---

## 🔄 Restarting the Server

After making changes to the server code:
1. Stop the server with `Ctrl+C`
2. Restart it with:
   ```bash
   python3 server.py
   ```
3. Clients will need to reconnect after server restart
