// frontend/vite.config.js
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');

  return {
    plugins: [react()],
    server: {
      // 从环境变量中获取端口，如果未设置则使用默认值 5173
      port: env.VITE_PORT ? parseInt(env.VITE_PORT) : 5173,
      // 监听所有地址，方便局域网访问，根据需要设置
      host: '0.0.0.0'
    },
    build: {
      outDir: '../dist/frontend', // 如果你需要将前端构建到后端可访问的目录，可以这样设置
    }
  };
});