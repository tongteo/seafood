const express = require("express");
const http = require("http");
const socketIO = require("socket.io");
const axios = require("axios");

const app = express();
const server = http.createServer(app);
const io = socketIO(server);

const BOT_SERVER_URL = "http://localhost:5000/generate";
const NEW_CONVERSATION_URL = "http://localhost:5000/new_conversation";

app.get("/", (req, res) => {
  res.sendFile(__dirname + "/index.html");
});

io.on("connection", (socket) => {
  console.log("Một người dùng đã kết nối");

  socket.on("chat message", async (data) => {
    const { message, username, userId, model } = data;

    if (message.startsWith("@bot")) {
      try {
        const prompt = message.substring(4).trim();
        const response = await axios.post(BOT_SERVER_URL, {
          user_id: userId,
          prompt: prompt,
          model: model,
          stream: true, // Request streaming from backend
        }, {
          responseType: "stream"
        });

        let fullBotResponse = "";
        response.data.on("data", (chunk) => {
          const textChunk = chunk.toString();
          fullBotResponse += textChunk;
          io.emit("chat message", { username: "Bot", message: textChunk, askedBy: username, streaming: true });
        });

        response.data.on("end", () => {
          io.emit("chat message", { username: "Bot", message: fullBotResponse, askedBy: username, streaming: false });
        });

      } catch (error) {
        console.error("Lỗi khi giao tiếp với bot:", error.message);
        io.emit("chat message", { username: "Bot", message: `Lỗi: ${error.message}`, askedBy: username });
      }
    } else {
      io.emit("chat message", data);
    }
  });

  socket.on("new conversation", async (userId) => {
    try {
      await axios.post(NEW_CONVERSATION_URL, { user_id: userId });
      io.emit("new conversation started", userId);
    } catch (error) {
      console.error("Lỗi khi tạo cuộc trò chuyện mới:", error.message);
    }
  });

  socket.on("disconnect", () => {
    console.log("Một người dùng đã ngắt kết nối");
  });
});

server.listen(3000, () => {
  console.log("Server đang chạy trên cổng 3000");
});


