// 採用 whisper-webui install.js 模式（無 git clone，程式碼已就位）
module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        venv: "env",
        path: "app",
        message: [
          "uv pip install -r requirements.txt"
        ]
      }
    }
  ]
}
