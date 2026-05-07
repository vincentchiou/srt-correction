// 採用 whisper-webui 動態 UI 結構
module.exports = {
  version: "7.0",
  title: "SRT 字幕校正",
  description: "使用 Claude AI 智慧校正課程字幕",
  menu: async (kernel, info) => {
    let installed = info.exists("app/env")
    let running = {
      install: info.running("install.js"),
      start: info.running("start.js"),
      update: info.running("update.js"),
      reset: info.running("reset.js"),
    }

    if (running.install) {
      return [{
        default: true,
        icon: "fa-solid fa-plug",
        text: "安裝中...",
        href: "install.js",
      }]
    } else if (installed) {
      if (running.start) {
        let local = info.local("start.js")
        if (local && local.url) {
          return [{
            default: true,
            icon: "fa-solid fa-rocket",
            text: "開啟 Web UI",
            href: local.url,
          }, {
            icon: "fa-solid fa-terminal",
            text: "終端機",
            href: "start.js",
          }]
        } else {
          return [{
            default: true,
            icon: "fa-solid fa-terminal",
            text: "啟動中...",
            href: "start.js",
          }]
        }
      } else if (running.update) {
        return [{
          default: true,
          icon: "fa-solid fa-terminal",
          text: "更新中...",
          href: "update.js",
        }]
      } else if (running.reset) {
        return [{
          default: true,
          icon: "fa-solid fa-terminal",
          text: "重置中...",
          href: "reset.js",
        }]
      } else {
        return [{
          default: true,
          icon: "fa-solid fa-power-off",
          text: "啟動",
          href: "start.js",
        }, {
          icon: "fa-solid fa-arrows-rotate",
          text: "更新套件",
          href: "update.js",
        }, {
          icon: "fa-regular fa-circle-xmark",
          text: "<div><strong>重置</strong><div>清除虛擬環境，重新安裝</div></div>",
          href: "reset.js",
          confirm: "確定要重置嗎？這將刪除虛擬環境並需要重新安裝。"
        }]
      }
    } else {
      return [{
        default: true,
        icon: "fa-solid fa-plug",
        text: "安裝",
        href: "install.js",
      }]
    }
  }
}
