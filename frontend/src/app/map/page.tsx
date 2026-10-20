import { Suspense } from "react";
import { MapScreen } from "@/components/MapScreen";

// 주소의 ?region을 읽는 클라이언트 화면이라 Suspense 경계 안에서 렌더링한다
export default function MapPage() {
  return (
    <Suspense fallback={<p className="loading">불러오는 중…</p>}>
      <MapScreen />
    </Suspense>
  );
}
