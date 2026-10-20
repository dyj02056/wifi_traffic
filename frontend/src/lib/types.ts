/* 자동 생성 파일 — 직접 고치지 말 것. contracts/schemas를 고친 뒤 npm run gen:types */

export interface BackgroundDoc {
  included_in_score: false;
  notice: "이 통계는 지점 점수에 반영하지 않습니다";
  datasets: {
    id: string;
    title: string;
    unit: string;
    note: string | null;
    source: SourceRef;
    series: {
      label: string;
      value: number;
      group?: string | null;
    }[];
  }[];
}
export interface SourceRef {
  name: string;
  dataset_id?: string | null;
  url: string;
  published_at?: string | null;
  retrieved_at: string;
}

export interface CasesDoc {
  label: "같은 원리 사례 — 국내 공공와이파이 사건 아님";
  cases: {
    id: string;
    title: string;
    summary: string;
    principle: string;
    related_rules: ("R1" | "R2" | "R3" | "R4" | "R5" | "R6" | "R7" | "R8")[];
    source: SourceRef & {
      published_at: string;
    };
  }[];
}
export interface SourceRef {
  name: string;
  dataset_id?: string | null;
  url: string;
  published_at?: string | null;
  retrieved_at: string;
}

export interface ChangesDoc {
  region_id: string;
  /**
   * 비교에 쓴 수집일 목록(오름차순). 발표 표기: 'N회 수집, 기간 X~Y'
   */
  snapshots: string[];
  collection_count: number;
  changes: {
    key: string;
    change: "added" | "removed";
    snapshot_from: string;
    snapshot_to: string;
    place_name: string | null;
    ssid: string | null;
    lat: number;
    lng: number;
  }[];
}

export interface DetailDoc {
  [k: string]: Detail;
}
export interface Detail {
  key: string;
  region_id: string;
  name: string;
  score: number;
  grade: "낮음" | "주의" | "높음";
  evidence: {
    ssid: string | null;
    facility_type: string | null;
    place_detail: string | null;
    /**
     * YYYY-MM
     */
    install_ym: string | null;
    provider: string | null;
    manager: string | null;
    manager_tel: string | null;
    data_date: string | null;
    address: string | null;
    /**
     * R5: 반경 내 개방형 AP 수(자신 제외)
     */
    open_ap_within_radius: number | null;
  };
  /**
   * @minItems 8
   * @maxItems 8
   */
  breakdown: [
    {
      id: "R1" | "R2" | "R3" | "R4" | "R5" | "R6" | "R7" | "R8";
      name: string;
      ratio: number;
      /**
       * 기본 가중치 기준 ratio × max_points
       */
      points: number;
      max_points: number;
      is_assumption: boolean;
      reason: string;
    },
    {
      id: "R1" | "R2" | "R3" | "R4" | "R5" | "R6" | "R7" | "R8";
      name: string;
      ratio: number;
      /**
       * 기본 가중치 기준 ratio × max_points
       */
      points: number;
      max_points: number;
      is_assumption: boolean;
      reason: string;
    },
    {
      id: "R1" | "R2" | "R3" | "R4" | "R5" | "R6" | "R7" | "R8";
      name: string;
      ratio: number;
      /**
       * 기본 가중치 기준 ratio × max_points
       */
      points: number;
      max_points: number;
      is_assumption: boolean;
      reason: string;
    },
    {
      id: "R1" | "R2" | "R3" | "R4" | "R5" | "R6" | "R7" | "R8";
      name: string;
      ratio: number;
      /**
       * 기본 가중치 기준 ratio × max_points
       */
      points: number;
      max_points: number;
      is_assumption: boolean;
      reason: string;
    },
    {
      id: "R1" | "R2" | "R3" | "R4" | "R5" | "R6" | "R7" | "R8";
      name: string;
      ratio: number;
      /**
       * 기본 가중치 기준 ratio × max_points
       */
      points: number;
      max_points: number;
      is_assumption: boolean;
      reason: string;
    },
    {
      id: "R1" | "R2" | "R3" | "R4" | "R5" | "R6" | "R7" | "R8";
      name: string;
      ratio: number;
      /**
       * 기본 가중치 기준 ratio × max_points
       */
      points: number;
      max_points: number;
      is_assumption: boolean;
      reason: string;
    },
    {
      id: "R1" | "R2" | "R3" | "R4" | "R5" | "R6" | "R7" | "R8";
      name: string;
      ratio: number;
      /**
       * 기본 가중치 기준 ratio × max_points
       */
      points: number;
      max_points: number;
      is_assumption: boolean;
      reason: string;
    },
    {
      id: "R1" | "R2" | "R3" | "R4" | "R5" | "R6" | "R7" | "R8";
      name: string;
      ratio: number;
      /**
       * 기본 가중치 기준 ratio × max_points
       */
      points: number;
      max_points: number;
      is_assumption: boolean;
      reason: string;
    }
  ];
  explanation: {
    text: string;
    source: "ai" | "template";
    model: string | null;
    generated_at: string;
  };
  /**
   * @minItems 1
   */
  safety_tips: [string, ...string[]];
  report_contact: {
    manager: string | null;
    tel: string | null;
  };
  flags: string[];
}

export interface KeyIndexDoc {
  [k: string]: string;
}

export interface MetaDoc {
  contract_version: string;
  disclaimer: "이 점수는 실제 해킹 확률이 아니라 위험요인 지표입니다.";
  /**
   * true면 프론트엔드는 '샘플 데이터' 배지를 띄운다
   */
  is_mock: boolean;
  /**
   * 번들의 모든 지역이 provisional이 아니면 true (요약값). 화면 표시는 regions[].r1_status로 지역별 판단(1.1.0~)
   */
  r1_confirmed: boolean;
  app_mode: "dev" | "final" | "mock";
  /**
   * 원본 데이터기준일자(최댓값)
   */
  data_reference_date: string | null;
  snapshot_collected_at: string | null;
  snapshot_count: number;
  /**
   * ISO 8601 번들 생성 시각
   */
  generated_at: string;
  regions_in_bundle: string[];
  sources: {
    id: string;
    name: string;
    dataset_id: string | null;
    url: string;
    retrieved_at: string | null;
  }[];
}

/**
 * @minItems 8
 * @maxItems 8
 */
export type RVector = [number, number, number, number, number, number, number, number];

export interface PointsDoc {
  region_id: string;
  count: number;
  points: {
    key: string;
    name: string;
    lat: number;
    lng: number;
    r: RVector;
    /**
     * 기본 가중치 기준
     */
    score: number;
    grade: "낮음" | "주의" | "높음";
    flags: string[];
  }[];
}

export interface RegionsDoc {
  default_region_id: string;
  sido: {
    sido_code: string;
    sido: string;
    count: number;
  }[];
  regions: {
    region_id: string;
    sido_code: string;
    sido: string;
    sigungu: string;
    count: number;
    /**
     * true면 points/detail/changes/sensitivity 파일이 번들에 있음
     */
    available: boolean;
    /**
     * provisional이면 이 지역을 볼 때 '임시(무효)' 배지·워터마크, no_ssid면 'SSID 정보 없음 — 보안접속 항목(R1)은 가정값' 배지만
     */
    r1_status: "confirmed" | "provisional" | "no_ssid";
    /**
     * SSID 있는 행 중 확정 라벨 비율. no_ssid면 null. 기준은 rules.params.R1_REGION_COVERAGE_MIN
     */
    r1_coverage: number | null;
    center: {
      lat: number;
      lng: number;
    };
    /**
     * [minLng, minLat, maxLng, maxLat] — 위·경도 각각 양쪽 1%씩(바깥 2%) 제외한 범위. 동떨어진 좌표(COORD_suspect)에 끌려가지 않게
     *
     * @minItems 4
     * @maxItems 4
     */
    bbox: [number, number, number, number];
  }[];
}

export interface RulesDoc {
  /**
   * 배열 순서 = points[].r 배열 순서(R1~R8 고정)
   *
   * @minItems 8
   * @maxItems 8
   */
  rules: [
    {
      id: "R1" | "R2" | "R3" | "R4" | "R5" | "R6" | "R7" | "R8";
      name: string;
      max_points: number;
      is_assumption: boolean;
      /**
       * @minItems 1
       */
      source_fields: [string, ...string[]];
      one_liner: string;
    },
    {
      id: "R1" | "R2" | "R3" | "R4" | "R5" | "R6" | "R7" | "R8";
      name: string;
      max_points: number;
      is_assumption: boolean;
      /**
       * @minItems 1
       */
      source_fields: [string, ...string[]];
      one_liner: string;
    },
    {
      id: "R1" | "R2" | "R3" | "R4" | "R5" | "R6" | "R7" | "R8";
      name: string;
      max_points: number;
      is_assumption: boolean;
      /**
       * @minItems 1
       */
      source_fields: [string, ...string[]];
      one_liner: string;
    },
    {
      id: "R1" | "R2" | "R3" | "R4" | "R5" | "R6" | "R7" | "R8";
      name: string;
      max_points: number;
      is_assumption: boolean;
      /**
       * @minItems 1
       */
      source_fields: [string, ...string[]];
      one_liner: string;
    },
    {
      id: "R1" | "R2" | "R3" | "R4" | "R5" | "R6" | "R7" | "R8";
      name: string;
      max_points: number;
      is_assumption: boolean;
      /**
       * @minItems 1
       */
      source_fields: [string, ...string[]];
      one_liner: string;
    },
    {
      id: "R1" | "R2" | "R3" | "R4" | "R5" | "R6" | "R7" | "R8";
      name: string;
      max_points: number;
      is_assumption: boolean;
      /**
       * @minItems 1
       */
      source_fields: [string, ...string[]];
      one_liner: string;
    },
    {
      id: "R1" | "R2" | "R3" | "R4" | "R5" | "R6" | "R7" | "R8";
      name: string;
      max_points: number;
      is_assumption: boolean;
      /**
       * @minItems 1
       */
      source_fields: [string, ...string[]];
      one_liner: string;
    },
    {
      id: "R1" | "R2" | "R3" | "R4" | "R5" | "R6" | "R7" | "R8";
      name: string;
      max_points: number;
      is_assumption: boolean;
      /**
       * @minItems 1
       */
      source_fields: [string, ...string[]];
      one_liner: string;
    }
  ];
  /**
   * @minItems 1
   */
  grades: [
    {
      min: number;
      max: number;
      label: "낮음" | "주의" | "높음";
      emoji: string;
      color: string;
    },
    ...{
      min: number;
      max: number;
      label: "낮음" | "주의" | "높음";
      emoji: string;
      color: string;
    }[]
  ];
  params: {
    [k: string]: number;
  };
  formula: {
    score: string;
    rounding: string;
    grade: string;
    errors: string;
    low_maxsum_basis: string;
  };
}

export interface SensitivityDoc {
  region_id: string;
  scenario_a: Scenario;
  scenario_b: Scenario;
  summary: {
    count: number;
    top_n: number;
    top_overlap: number;
    spearman: number | null;
    grade_moves: number;
  };
  /**
   * rank_A 오름차순
   */
  rows: {
    key: string;
    place_name: string | null;
    rank_A: number;
    rank_B: number;
    /**
     * rank_A - rank_B (양수 = 기준 B에서 순위 상승)
     */
    delta: number;
    score_A: number;
    score_B: number;
    grade_A: "낮음" | "주의" | "높음";
    grade_B: "낮음" | "주의" | "높음";
  }[];
}
export interface Scenario {
  label: string;
  /**
   * @minItems 8
   * @maxItems 8
   */
  weights: [number, number, number, number, number, number, number, number];
}
