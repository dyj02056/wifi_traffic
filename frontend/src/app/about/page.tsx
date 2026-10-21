"use client";
// 데이터와 한계 (plan.md §9.3 /about) — web-draft/about.html과 같은 내용
//
// [이 파일이 하는 일]
//   "/about" 화면: 이 지도가 어떤 공공데이터로 만들어졌는지(출처 표), 어떤 규칙이 '가정'인지, 알려진 한계가 무엇인지 설명합니다.
//   출처 표와 가정 규칙 목록은 meta.json·rules.json에서 자동으로 채우고, 한계 목록(LIMITS)은 아래에 직접 적어 둡니다.
import { DocShell } from "@/components/DocShell";
import { useMeta, useRules } from "@/lib/queries";

// 알려진 한계 카드 목록 (아이콘, 제목, 본문)
const LIMITS = [
  { icon: "🗺️", title: "시군구 경계 한계",
    body: <>R5(개방형 AP 밀집도)는 같은 시군구 안의 AP만 셉니다. 시군구 경계 근처 지점은 이웃 시군구 AP가 빠져 밀집도가 낮게 나올 수 있으며,
      해당 지점에는 &apos;시군구 경계 근처&apos; 표시가 붙습니다.</> },
  { icon: "📶", title: "SSID 판정",
    body: <>보안접속 여부(R1)는 SSID 이름을 팀이 직접 분류한 목록으로 판단합니다. 분류가 불명확한 SSID는 중간값(가정)을 적용합니다.
      지역마다 SSID가 있는 지점 중 분류가 확정된 비율이 90% 미만이면 그 지역 화면에 &apos;임시(무효)&apos; 표시가 나옵니다.
      원본에 SSID가 아예 없는 지역은 &apos;SSID 정보 없음&apos; 표시와 함께 보안접속 항목을 가정값으로 계산합니다.</> },
  { icon: "📊", title: "범죄·침해사고 통계는 점수에 넣지 않습니다",
    body: <>지역 통계는 와이파이 지점과 직접 연결되지 않기 때문에 배경 정보로만 보여줍니다.</> },
  { icon: "🔢", title: "행 수와 설치 장소 수",
    body: <>표준데이터의 &apos;행 수&apos;와 국회 제출 자료의 &apos;설치 장소 수&apos;는 다른 숫자이며 섞어 쓰지 않습니다.</> },
  { icon: "🕒", title: "현장 상태와 다를 수 있음",
    body: <>원본 데이터는 매일 갱신되며 공개 시점 기준 이틀 전 자료입니다. 현장 상태와 다를 수 있습니다.</> },
];

export default function AboutPage() {
  const { data: meta } = useMeta();
  const { data: rules } = useRules();
  return (
    <DocShell>
      <header className="rules-hero">
        <h1>데이터와 한계</h1>
        <p>이 지도가 어떤 공공데이터로 만들어졌는지, 어떤 부분이 가정이고 무엇을 알 수 없는지 정리했습니다.
          점수를 읽기 전에 한 번 살펴보세요.</p>
      </header>
      <div className="about">
        <section className="about-why">
          <h2 className="subhead">왜 &apos;위험요인 지표&apos;인가</h2>
          <p>지점 단위의 공공와이파이 해킹 사건을 기록한 공공데이터는 없습니다(확인 기준일 2026-10-20).
            최근 60일 동안 국내 공공와이파이 해킹 보도도 확인되지 않았습니다. 그래서 이 지도는 사건이 아니라,
            공개된 설치 정보에서 계산할 수 있는 <strong>위험요인</strong>을 점수로 보여줍니다.</p>
        </section>
        <section>
          <h2 className="subhead">데이터 출처</h2>
          <div className="about-table">
            <table>
              <thead><tr><th>ID</th><th>데이터</th><th>데이터셋</th><th>수집일</th></tr></thead>
              <tbody>
                {meta?.sources.map((s) => (
                  <tr key={s.id}>
                    <td><span className="about-id">{s.id}</span></td>
                    <td>{s.url.startsWith("http") ? <a href={s.url} target="_blank" rel="noopener noreferrer">{s.name}</a> : s.name}</td>
                    <td>{s.dataset_id ?? "—"}</td><td>{s.retrieved_at ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {meta && (
            <ul className="about-facts">
              <li>데이터 기준일 <b>{meta.data_reference_date ?? "–"}</b></li>
              <li>스냅샷 <b>{meta.snapshot_count}회</b> 수집</li>
              <li>계약 버전 <b>{meta.contract_version}</b></li>
              <li>지도: 카카오맵 (점수 계산에 쓰지 않는 표시용)</li>
            </ul>
          )}
        </section>
        <section>
          <h2 className="subhead">가정에 기반한 규칙</h2>
          <p>아래 규칙은 데이터로 직접 확인되지 않은 가정을 포함합니다. 화면에서 <span className="badge assumption">가정</span> 배지로 표시합니다.</p>
          <div className="about-cards">
            {rules?.rules.filter((r) => r.is_assumption).map((r) => (
              <div key={r.id} className="about-card">
                <h3><span className="about-id">{r.id}</span> {r.name}</h3>
                <p>{r.one_liner}</p>
              </div>
            ))}
          </div>
        </section>
        <section>
          <h2 className="subhead">알려진 한계</h2>
          <div className="about-limits">
            {LIMITS.map((l) => (
              <div key={l.title} className="about-limit">
                <span className="about-icon" aria-hidden="true">{l.icon}</span>
                <div><h3>{l.title}</h3><p>{l.body}</p></div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </DocShell>
  );
}
