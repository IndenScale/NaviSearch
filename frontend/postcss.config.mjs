import tailwindcss from '@tailwindcss/postcss';
import autoprefixer from 'autoprefixer';

export default {
  plugins: [ // <--- 注意这里，是一个数组，而不是对象字面量
    tailwindcss(), // <--- 直接调用插件函数
    autoprefixer(), // <--- 直接调用插件函数
  ],
};