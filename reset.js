module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        message: [
          "{{platform === 'win32' ? 'rmdir /s /q app\\env' : 'rm -rf app/env'}}"
        ]
      }
    }
  ]
}
