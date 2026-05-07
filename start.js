// 採用 whisper-webui start.js + URL capture pattern
module.exports = {
  daemon: true,
  run: [
    {
      method: "shell.run",
      params: {
        venv: "env",
        path: "app",
        message: [
          "python app.py"
        ],
        on: [{
          // 擷取 Gradio 啟動後印出的 URL
          "event": "/http:\\/\\/\\S+/",
          "done": true
        }]
      }
    },
    {
      // 儲存 URL 至 local 變數，供 pinokio.js 顯示「開啟 Web UI」按鈕
      method: "local.set",
      params: {
        url: "{{input.event[0]}}"
      }
    }
  ]
}
