const express = require('express');
const http = require('http');
const { Server } = require('socket.io');

const app = express();
const server = http.createServer(app);
const io = new Server(server);
const PORT = process.env.PORT || 3000;

const messages = [];

app.use(express.static('public'));

app.get('/admin/messages', (req, res) => {
  res.json(messages);
});

io.on('connection', (socket) => {
  socket.emit('chat history', messages);
  socket.on('chat message', (msg) => {
    const message = { text: msg, time: Date.now() };
    messages.push(message);
    io.emit('chat message', message);
  });
});

server.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});
