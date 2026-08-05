import i18n from "i18next";
import { initReactI18next } from "react-i18next";

i18n.use(initReactI18next).init({
  resources: {
    en: {
      translation: {
        app: { title: "diec-gui", subtitle: "Detect It Easy" },
        scan: {
          select: "Select a file to scan...",
          browse: "Browse",
          scan: "Scan",
          scanning: "Scanning...",
          no_detections: "No detections.",
        },
      },
    },
    "zh-CN": {
      translation: {
        app: { title: "diec-gui", subtitle: "Detect It Easy" },
        scan: {
          select: "选择要扫描的文件...",
          browse: "浏览",
          scan: "扫描",
          scanning: "扫描中...",
          no_detections: "无检测结果。",
        },
      },
    },
  },
  lng: "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export default i18n;
