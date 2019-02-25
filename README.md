[다음영화](http://movie.daum.net)에서 영화/드라마 정보를 가져오는 Plex용 Metadata Agent입니다.

[드라마를 위한 Metadata Agent](https://github.com/hojel/DaumMovieTv.bundle)가 따로 있었으나 통합됨.

설정
==============

1. 영화 ID 덮어쓰기
   - _None_: 다음영화 ID를 유지
   - _IMDB_: [IMDB](http://www.imdb.com) ID를 대신 넘겨줌. OpenSubtitles Agent와 연결에 필요.
2. 드라마 ID 덮어쓰기
   - _None_: 다음영화 ID를 유지
   - _TVDB_: [TVDB](http://www.thetvdb.com) ID를 대신 넘겨줌. OpenSubtitles Agent와 연결에 필요.
3. MPAA 영화 등급 사용
   - [x] 미국영화협회(MPAA) 등급으로 변경해서 표시 (G, PG, PG-13, R, NC-17)
   - [ ] 영상물등급위원회(KMRB) 등급 사용 (A, 12, 15, R, X) (default). [KMRB 등급 아이콘](https://www.dropbox.com/s/kbk4f0t7u6dpjoo/pms-content-rating-icons-kr.zip?dl=0)을 PLEX 어플리케이션 내에 설치하면 영화 등급이 아이콘으로 표시된다.
4. 영화/드라마 제목을 초성 기준으로 색인
   - [x] 초성 기준으로 색인 (ㄱㄴㄷ...ㅎ) (default)
   - [ ] 음절 기준으로 색인 (가각간...힣)
5. 이미지를 https로 다운로드
   - [x] https 사용
   - [ ] http 사용 (default)

## KMRB 등급 아이콘 설치 위치
OS | 설치 위치
---|---
macOS | `/Applications/Plex Media Server.app/Contents/Resources/Plug-ins-*********/Media-Flags.bundle/Contents/Resources/Content Rating`
QNAP | `/share/CACHEDEV1_DATA/.qpkg/PlexMediaServer/Resources/Plug-ins-*********/Media-Flags.bundle/Contents/Resources/Content Rating`
Synology | `/volume2/@appstore/Plex Media Server/Resources/Plug-ins-*********/Media-Flags.bundle/Contents/Resources/Content Rating`

OpenSubtitles과의 연결
==============

1. Plex Plug-in folder에서 OpenSubtitles.bundle 을 찾는다.
2. Contents/Code/__init__.py 를 다음과 같이 수정한다.

    \- contributes_to = ['com.plexapp.agents.imdb']  
    \+ contributes_to = ['com.plexapp.agents.imdb', 'com.plexapp.agents.daum_movie']  

    \- contributes_to = ['com.plexapp.agents.thetvdb']  
    \+ contributes_to = ['com.plexapp.agents.thetvdb', 'com.plexapp.agents.daum_movie']  

3. DaumMovie.bundle의 설정에서 영화 ID 덮어쓰기로 _IMDB_, 드라마 ID 덮어쓰기로 _TVDB_를 각각 선택한다.

FanartTV.bundle 에도 사용가능하다.
