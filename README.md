# DaumMovie.bundle

다음(Daum) 통합검색에서 한국 영화 및 TV 프로그램(드라마/예능 등)의 메타데이터를 가져오는 Plex Media Server용 Metadata Agent입니다.

## 주요 변경 및 개선 사항

* **다음(Daum) 검색 개편 완벽 대응**
  * 구 `movie.daum.net` API 및 구 `movieEColl` 구조 폐지에 따라, 개편된 다음 통합검색(`em1Coll` 영화 컬렉션 및 내장 JSON 데이터 `RAW_CASTS`, `RAW_CREWS`, `RAW_COMPANIES`, `RAW_SERIES`, `dataSource`) 기반으로 영화 검색 및 상세 메타데이터 수집 로직 전면 개편
  * 영화 검색 시 메인 결과, 시리즈물, 동명영화 및 카카오 자동완성 API 연동을 통한 정확한 매칭 및 중복 제거 지원
* **TV 프로그램(드라마/예능) 메타데이터 수집 고도화**
  * 시즌제 TV 프로그램 지원 및 최신 시즌 포스터를 대표 포스터로 자동 설정
  * 드라마(배역/배우 분리 구조) 및 예능(출연진 구조)의 출연/제작진(`w=tv` 전체 목록) 자동 판별 및 프로필 사진 추출
  * 장르, 방송사(제작사), 첫 방영일, 방송 시간, 방영 상태(`완결`/`방송중`) 및 회차별 에피소드 제목·줄거리·방영일·썸네일 추출 정확도 개선
  * 동명프로그램 및 하단 추천 영역과의 XPath 충돌 방지 처리
* **레거시 불필요 코드 정리**
  * 사용되지 않는 상수 및 도달 불가능한(dead code) 구버전 로직 일괄 정리

---

## 설정 안내

1. **Maximum Number of Posters / Arts**
   * 다운로드할 최대 포스터 및 배경 아트(스틸컷) 수를 지정합니다. (기본값: `5`)
2. **Override metadata id for Movie (영화 ID 덮어쓰기)**
   * `None`: 다음 영화 ID를 유지합니다.
   * `IMDB`: [IMDB](http://www.imdb.com) ID로 덮어씁니다. (OpenSubtitles 등 외부 에이전트 연동 시 사용)
3. **Override metadata id for TV shows (드라마 ID 덮어쓰기)**
   * `None`: 다음 TV ID를 유지합니다.
   * `TVDB`: [TheTVDB](http://www.thetvdb.com) ID로 덮어씁니다.
4. **Use MPAA film rating system (MPAA 영화 등급 사용)**
   * 체크 시 미국영화협회(MPAA) 등급(`G`, `PG`, `PG-13`, `R`, `NC-17`)으로 변환하여 표시합니다.
   * 체크 해제 시 영상물등급위원회(KMRB) 등급(`kr/A`, `kr/12`, `kr/15`, `kr/R`, `kr/X`)을 사용합니다. (기본값)
5. **Index titles by decomposed Hangul syllables (초성 기준 색인)**
   * 체크 시 한글 자모 분해(NFKD)를 통해 초성/음소 기준으로 정렬합니다. (기본값)
   * 체크 해제 시 완성형 음절(NFKC) 기준으로 정렬합니다.
6. **Use https for image download (이미지를 https로 다운로드)**
   * 이미지 URL 요청 시 `https://` 프로토콜을 사용합니다.
7. **Web proxy (http / https)**
   * 프록시 서버를 경유하여 요청해야 하는 환경일 경우 설정합니다. (변경 후 PMS 재시작 필요)

---

## 설치 위치

운영체제별 Plex `Plug-ins` 폴더 하위에 `DaumMovie.bundle` 폴더를 위치시킵니다.

| OS | 설치 경로 |
| :--- | :--- |
| **Windows** | `%LOCALAPPDATA%\Plex Media Server\Plug-ins\DaumMovie.bundle` |
| **macOS** | `~/Library/Application Support/Plex Media Server/Plug-ins/DaumMovie.bundle` |
| **Linux / NAS** | `$PLEX_HOME/Library/Application Support/Plex Media Server/Plug-ins/DaumMovie.bundle` |

---

## OpenSubtitles 연동 방법

1. Plex `Plug-ins` 폴더에서 `OpenSubtitles.bundle`을 찾습니다.
2. `Contents/Code/__init__.py` 파일을 열어 아래와 같이 `com.plexapp.agents.daum_movie`를 추가합니다.
   ```python
   contributes_to = ['com.plexapp.agents.imdb', 'com.plexapp.agents.daum_movie']
   contributes_to = ['com.plexapp.agents.thetvdb', 'com.plexapp.agents.daum_movie']
   ```
3. `DaumMovie.bundle` 설정에서 영화 ID 덮어쓰기를 `IMDB`, 드라마 ID 덮어쓰기를 `TVDB`로 선택합니다. (`FanartTV.bundle` 등에도 동일하게 적용 가능)
