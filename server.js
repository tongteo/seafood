const express = require('express');
const http = require('http');
const socketIO = require('socket.io');
const axios = require('axios');

const app = express();
const server = http.createServer(app);
const io = socketIO(server);

const BOT_SERVER_URL = 'http://localhost:5000/generate'; 

app.get('/', (req, res) => {
  res.sendFile(__dirname + '/index.html');
});

io.on('connection', (socket) => {
  console.log('Một người dùng đã kết nối');

  socket.on('chat message', async (data) => {
    if (data.message.startsWith('@bot')) {
      // Xử lý yêu cầu gửi đến bot
      try {
        const botResponse = await axios.post(BOT_SERVER_URL, {
          prompt_parts: [data.message.substring(4).trim()]
        });

        if (botResponse.data && botResponse.data.generated_content) {
          // Gửi phản hồi từ bot kèm theo thông tin người dùng yêu cầu
          io.emit('chat message', { username: 'Bot', message: botResponse.data.generated_content, askedBy: data.username });
        }
      } catch (error) {
        console.error('Lỗi khi giao tiếp với bot:', error);
      }
    } else {
      // Gửi tin nhắn thông thường
      io.emit('chat message', data);
    }
  });

  socket.on('disconnect', () => {
    console.log('Một người dùng đã ngắt kết nối');
  });
});

server.listen(3000, () => {
  console.log('Server đang chạy trên cổng 3000');
});
