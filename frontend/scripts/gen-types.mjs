// contracts/schemas/*.schema.json → src/lib/types.ts (plan.md §9.1, npm run gen:types)
// $ref의 https://wifisafe.local/schemas/... 는 네트워크가 아니라 로컬 contracts/schemas에서 읽는다.
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
  const typeName = name.replace(/(^|_)(\w)/g, (_, __, c) => c.toUpperCase()) + "Doc";
  schema.title = typeName;
  ts += "\n" + (await compile(schema, typeName, {
    bannerComment: "", cwd: schemaDir, additionalProperties: false, declareExternallyReferenced: true,
    $refOptions: { resolve: { wifisafe: localResolver, http: false } },
  }));
}
writeFileSync(out, ts);
console.log(`types: ${names.length} schemas → ${path.relative(process.cwd(), out)}`);
