"use client";
// 장소 검색: 와이파이 지점(장소명·주소) + 📍 주소·장소 위치(카카오). 같은 이름이 많아 주소·지역을 함께 보여 준다.
//
// [이 파일이 하는 일]
//   지도 화면 위쪽의 검색창입니다. 글자를 입력하면 두 가지를 동시에 찾아 목록으로 보여 줍니다.
//     1) 와이파이 지점: 우리 API(전국) 또는 지금 지역의 지점 이름에서 찾기 → 누르면 그 지점 상세를 연다
//     2) 📍 위치: 카카오 주소·장소 검색 → 누르면 그 위치로 지도를 옮기고, 필요하면 지역도 바꾼다
//   Enter를 누르면 첫 번째 결과를 고르고, Esc나 바깥을 누르면 목록을 닫습니다.
import { useEffect, useRef, useState } from "react";
import { searchPoints, type SearchHit } from "@/lib/api";
import { searchPlaces, type Place } from "@/lib/geo";
import type { PointsDoc } from "@/lib/types";

interface Props {
  regionId: string | null;
  region?: { sido: string; sigungu: string };
  points: PointsDoc["points"];
  onPickPoint: (hit: SearchHit) => void;
  onPickPlace: (place: Place) => void;
}

export function SearchBox({ regionId, region, points, onPickPoint, onPickPlace }: Props) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [res, setRes] = useState<{ q: string; hits: SearchHit[]; scope: string; places: Place[] } | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  // 검색 타이머 안에서 최신 지역·지점 목록을 쓰려고 ref에 담아 매번 갱신한다(검색은 q가 바뀔 때만 다시 시작)
  const ctx = useRef({ regionId, region, points });
  useEffect(() => { ctx.current = { regionId, region, points }; });

  // 입력이 멈추고 0.25초 뒤에 검색 (결과는 비동기 콜백에서만 상태로 반영)
  useEffect(() => {
    const term = q.trim();
    if (!term) return;
    let alive = true;
    const t = setTimeout(async () => {
      const { regionId: rid, region: rg, points: pts } = ctx.current;
      const [{ hits, scope }, places] = await Promise.all([searchPoints(term, rid, pts, rg), searchPlaces(term)]);
      if (alive) setRes({ q: term, hits, scope, places });
    }, 250);
    return () => { alive = false; clearTimeout(t); };
  }, [q]);

  // 검색 상자 바깥을 누르면 결과 목록을 닫는다
  useEffect(() => {
    const close = (e: MouseEvent) => { if (!boxRef.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  // 지금 입력한 글자에 대한 결과만 보여 준다(이전 검색어의 결과가 늦게 와도 무시)
  const shown = q.trim() && res?.q === q.trim() ? res : null;
  const pickPoint = (h: SearchHit) => { setOpen(false); setQ(h.name); onPickPoint(h); };
  const pickPlace = (p: Place) => { setOpen(false); setQ(p.label); onPickPlace(p); };

  return (
    <div className="search-box" ref={boxRef}>
      <input type="search" value={q} placeholder="장소명·주소를 입력하세요 (예: 서초구민체육센터, 둔산동)" aria-label="장소 검색"
        onChange={(e) => { setQ(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "Escape") setOpen(false);
          if (e.key === "Enter" && shown) {
            if (shown.hits[0]) pickPoint(shown.hits[0]);
            else if (shown.places[0]) pickPlace(shown.places[0]);
          }
        }} />
      {open && q.trim() && (
        <div className="search-results" role="listbox">
          {!shown ? <p className="empty">검색 중…</p> : (
            <>
              <p className="group">와이파이 지점 · {shown.scope}{shown.scope === "지금 지역" && " (장소명만)"}</p>
              {shown.hits.length ? shown.hits.map((h) => (
                <button key={h.key} type="button" role="option" aria-selected={false} onClick={() => pickPoint(h)}>
                  <b>{h.name}</b>
                  <span>{[h.address, h.place_detail && !h.address?.includes(h.place_detail) ? h.place_detail : null, `${h.sido} ${h.sigungu}`].filter(Boolean).join(" · ")}</span>
                </button>
              )) : <p className="empty">이 이름·주소로 등록된 공공와이파이가 없습니다.</p>}
              {shown.places.length > 0 && (
                <>
                  <p className="group">📍 위치로 이동 (카카오 주소·장소 검색)</p>
                  {shown.places.map((p) => (
                    <button key={`${p.label}-${p.lat}`} type="button" role="option" aria-selected={false} onClick={() => pickPlace(p)}>
                      <b>📍 {p.label}</b><span>{p.sub} · 근처 와이파이 보기</span>
                    </button>
                  ))}
                </>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
