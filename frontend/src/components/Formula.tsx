// KaTeX 수식 블록 (채점 기준 페이지). 서버·브라우저 모두 같은 HTML을 만든다.
import katex from "katex";
import "katex/dist/katex.min.css";

export function Formula({ tex, block = false }: { tex: string; block?: boolean }) {
  const html = katex.renderToString(tex, { displayMode: block, throwOnError: false, output: "htmlAndMathml" });
  return block
    ? <div className="math-block" dangerouslySetInnerHTML={{ __html: html }} />
    : <span className="math-inline" dangerouslySetInnerHTML={{ __html: html }} />;
}
