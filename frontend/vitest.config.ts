// [이 파일이 하는 일] Vitest(테스트 실행 도구) 설정. `npm test`를 실행하면 tests/ 폴더의 *.test.ts 파일을 돌린다.
import { defineConfig } from "vitest/config";

export default defineConfig({ test: { include: ["tests/**/*.test.ts"] } });
