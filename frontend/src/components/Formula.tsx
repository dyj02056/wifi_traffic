// KaTeX 수식 블록 (채점 기준 페이지). 서버·브라우저 모두 같은 HTML을 만든다.
//
// [이 파일이 하는 일]
//   점수 공식 같은 수학식을 교과서처럼 예쁘게 보여 줍니다. KaTeX는 수식 표기(TeX)를 HTML로 바꿔 주는 도구입니다.
//   예) <Formula tex="\frac{a}{b}" block /> → 분수 모양으로 표시
//   - block=true: 한 줄을 통째로 차지하는 큰 수식, false: 문장 안에 들어가는 작은 수식
//   - throwOnError: false → 수식에 오타가 있어도 화면이 깨지지 않고 빨간 글씨로 표시
import katex from "katex";
import "katex/dist/katex.min.css";

export function Formula({ tex, block = false }: { tex: string; block?: boolean }) {
  const html = katex.renderToString(tex, { displayMode: block, throwOnError: false, output: "htmlAndMathml" });
  return block
    ? <div className="math-block" dangerouslySetInnerHTML={{ __html: html }} />
    : <span className="math-inline" dangerouslySetInnerHTML={{ __html: html }} />;
}
