// [이 파일이 하는 일] Next.js(화면을 만드는 프레임워크)의 동작 설정
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  // 다녀간 화면을 숨겨 둔 채 보관해서 메뉴를 오가도 빠르게 다시 보여 준다(lib/usePlayOnView.ts가 이 점을 고려함)
  cacheComponents: true,
  // 링크에 마우스를 올리기 전부터 다음 화면 일부를 미리 받아 둔다
  partialPrefetching: true,
  // turbopack(빠른 개발용 빌드 도구): CSS 파일을 Tailwind로 처리하도록 지정
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
