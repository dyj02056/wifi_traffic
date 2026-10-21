// contracts/schemas/*.schema.json → src/lib/types.ts (plan.md §9.1, npm run gen:types)
// $ref의 https://wifisafe.local/schemas/... 는 네트워크가 아니라 로컬 contracts/schemas에서 읽는다.
//
// [이 파일이 하는 일]
//   백엔드와 프론트엔드가 약속한 데이터 모양(contracts/schemas/*.schema.json)을 읽어
//   TypeScript 타입 정의 파일(src/lib/types.ts)을 자동으로 만듭니다.
//   그래서 types.ts는 손으로 고치지 않고, 스키마를 고친 뒤 `npm run gen:types`로 다시 만듭니다.
//   (타입: "이 데이터에는 이런 칸이 있고 이 칸은 숫자다"를 코드에 적어 두어 실수를 미리 잡게 해 주는 표시)
//   파일 이름이 _로 시작하는 스키마(_common)는 다른 스키마가 참조하는 공용 조각이라 따로 만들지 않는다.
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { compile } from "json-schema-to-typescript";

const here = path.dirname(fileURLToPath(import.meta.url));
const schemaDir = path.resolve(here, "../../contracts/schemas");
const out = path.resolve(here, "../src/lib/types.ts");

const localResolver = {
  order: 1,
  canRead: /^https:\/\/wifisafe\.local\/schemas\//,
  read: (file) => readFileSync(path.join(schemaDir, path.basename(new URL(file.url).pathname)), "utf8"),
};

const names = readdirSync(schemaDir).filter((f) => f.endsWith(".schema.json") && !f.startsWith("_")).sort();
let ts = "/* 자동 생성 파일 — 직접 고치지 말 것. contracts/schemas를 고친 뒤 npm run gen:types */\n";
for (const f of names) {
  const schema = JSON.parse(readFileSync(path.join(schemaDir, f), "utf8"));
  const name = f.replace(".schema.json", "");
  // 파일 이름 → 타입 이름. 예) "key_index" → "KeyIndexDoc"
  const typeName = name.replace(/(^|_)(\w)/g, (_, __, c) => c.toUpperCase()) + "Doc";
  schema.title = typeName;
  ts += "\n" + (await compile(schema, typeName, {
    bannerComment: "", cwd: schemaDir, additionalProperties: false, declareExternallyReferenced: true,
    $refOptions: { resolve: { wifisafe: localResolver, http: false } },
  }));
}
writeFileSync(out, ts);
console.log(`types: ${names.length} schemas → ${path.relative(process.cwd(), out)}`);
