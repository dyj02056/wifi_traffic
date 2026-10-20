"use client";
// 장소 검색: 와이파이 지점(장소명·주소) + 📍 주소·장소 위치(카카오). 같은 이름이 많아 주소·지역을 함께 보여 준다.
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

  useEffect(() => {
    const close = (e: MouseEvent) => { if (!boxRef.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

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
