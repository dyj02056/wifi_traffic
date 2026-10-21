// [이 파일이 하는 일] ESLint(코드의 실수·나쁜 습관을 찾아 주는 검사 도구) 설정. `npm run lint`로 실행한다.
// Next.js 권장 규칙(웹 성능·TypeScript)을 쓰고, 자동 생성 폴더(.next, out, build)는 검사에서 뺀다.
import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
