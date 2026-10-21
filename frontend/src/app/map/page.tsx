// [이 파일이 하는 일]
//   "/map" 주소의 페이지입니다. 실제 화면 내용은 components/MapScreen.tsx에 있고, 여기서는 그것을 감싸기만 합니다.
//   Suspense: 안쪽 내용이 준비될 때까지 fallback("불러오는 중…")을 대신 보여 주는 React 기능.
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
