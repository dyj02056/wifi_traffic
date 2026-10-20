"use client";
// 데이터와 한계 (plan.md §9.3 /about) — web-draft/about.html과 같은 내용
import { DocShell } from "@/components/DocShell";
import { useMeta, useRules } from "@/lib/queries";

export default function AboutPage() {
  const { data: meta } = useMeta();
  const { data: rules } = useRules();
  return (
    <DocShell>
      <h1>데이터와 한계</h1>
      <section>
        <h2>왜 &apos;위험요인 지표&apos;인가</h2>
        <p>지점 단위의 공공와이파이 해킹 사건을 기록한 공공데이터는 없습니다(확인 기준일 2026-10-20).
          최근 60일 동안 국내 공공와이파이 해킹 보도도 확인되지 않았습니다. 그래서 이 지도는 사건이 아니라,
          공개된 설치 정보에서 계산할 수 있는 <strong>위험요인</strong>을 점수로 보여줍니다.</p>
      </section>
      <section>
        <h2>데이터 출처</h2>
        <table>
          <thead><tr><th>ID</th><th>데이터</th><th>데이터셋</th><th>수집일</th></tr></thead>
          <tbody>
            {meta?.sources.map((s) => (
              <tr key={s.id}>
                <td>{s.id}</td>
                <td>{s.url.startsWith("http") ? <a href={s.url} target="_blank" rel="noopener noreferrer">{s.name}</a> : s.name}</td>
                <td>{s.dataset_id ?? "—"}</td><td>{s.retrieved_at ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {meta && <p>데이터 기준일 {meta.data_reference_date ?? "–"} · 스냅샷 {meta.snapshot_count}회 수집 · 계약 버전 {meta.contract_version}</p>}
        <p>지도: 카카오맵 (점수 계산에 쓰지 않는 표시용)</p>
      </section>
      <section>
        <h2>가정에 기반한 규칙</h2>
        <p>아래 규칙은 데이터로 직접 확인되지 않은 가정을 포함합니다. 화면에서 <span className="badge assumption">가정</span> 배지로 표시합니다.</p>
        <ul>{rules?.rules.filter((r) => r.is_assumption).map((r) => <li key={r.id}>{r.id} {r.name} — {r.one_liner}</li>)}</ul>
      </section>
      <section>
        <h2>알려진 한계</h2>
        <ul>
          <li><strong>시군구 경계 한계:</strong> R5(개방형 AP 밀집도)는 같은 시군구 안의 AP만 셉니다.
            시군구 경계 근처 지점은 이웃 시군구 AP가 빠져 밀집도가 낮게 나올 수 있으며, 해당 지점에는 &apos;시군구 경계 근처&apos; 표시가 붙습니다.</li>
          <li><strong>SSID 판정:</strong> 보안접속 여부(R1)는 SSID 이름을 팀이 직접 분류한 목록으로 판단합니다.
            분류가 불명확한 SSID는 중간값(가정)을 적용합니다. 지역마다 SSID가 있는 지점 중 분류가 확정된 비율이 90% 미만이면
            그 지역 화면에 &apos;임시(무효)&apos; 표시가 나옵니다. 원본에 SSID가 아예 없는 지역은 &apos;SSID 정보 없음&apos; 표시와 함께 보안접속 항목을 가정값으로 계산합니다.</li>
          <li><strong>범죄·침해사고 통계는 점수에 넣지 않습니다.</strong> 지역 통계는 와이파이 지점과 직접 연결되지 않기 때문에 배경 정보로만 보여줍니다.</li>
          <li><strong>행 수와 설치 장소 수:</strong> 표준데이터의 &apos;행 수&apos;와 국회 제출 자료의 &apos;설치 장소 수&apos;는 다른 숫자이며 섞어 쓰지 않습니다.</li>
          <li>원본 데이터는 매일 갱신되며 공개 시점 기준 이틀 전 자료입니다. 현장 상태와 다를 수 있습니다.</li>
        </ul>
      </section>
    </DocShell>
  );
}
