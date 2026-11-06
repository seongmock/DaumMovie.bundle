# -*- coding: utf-8 -*-
# Daum Movie

import urllib, unicodedata, os, httplib, socket, time

# 로컬(127.0.0.1) Plex 서버와의 통신 시 Connection: close로 인한 Windows 소켓 리셋(Errno 10054) 방지 및 재시도 처리
if 'KeepAliveHTTPConnection' not in str(httplib.HTTPConnection):
  OrigHTTPConnection = httplib.HTTPConnection
  OrigHTTPSConnection = httplib.HTTPSConnection

  class KeepAliveHTTPConnection(OrigHTTPConnection):
    def request(self, method, url, body=None, headers={}):
      if self.host == '127.0.0.1':
        headers = dict(headers)
        headers['Connection'] = 'keep-alive'
      self.last_method = method
      self.last_url = url
      self.last_body = body
      self.last_headers = headers
      return OrigHTTPConnection.request(self, method, url, body, headers)

    def getresponse(self, buffering=False):
      if self.host == '127.0.0.1':
        for attempt in range(5):
          try:
            r = OrigHTTPConnection.getresponse(self, buffering=buffering)
            if r.status >= 500 and attempt < 4:
              self.close()
              time.sleep(0.25)
              self.connect()
              OrigHTTPConnection.request(self, self.last_method, self.last_url, self.last_body, self.last_headers)
              continue
            return r
          except socket.error:
            if attempt == 4:
              raise
            self.close()
            time.sleep(0.25)
            self.connect()
            OrigHTTPConnection.request(self, self.last_method, self.last_url, self.last_body, self.last_headers)
      return OrigHTTPConnection.getresponse(self, buffering=buffering)

  class KeepAliveHTTPSConnection(OrigHTTPSConnection, KeepAliveHTTPConnection):
    pass

  httplib.HTTPConnection = KeepAliveHTTPConnection
  httplib.HTTPSConnection = KeepAliveHTTPSConnection

DAUM_MOVIE_SRCH   = "https://search.daum.net/search?w=tot&q=%s&rtmaxcoll=EM1"
DAUM_MOVIE_SGST   = "https://dapi.kakao.com/suggest-hub/v1/search.json?service=movie-v2&cate=movie&multiple=1&q=%s"
DAUM_MOVIE_INFO   = "https://search.daum.net/search?w=cin&q=%s&coll=movie-main&spId=%s&spt=movie-info&DA=EM1&rtmaxcoll=EM1"
DAUM_MOVIE_CAST   = "https://search.daum.net/search?w=cin&q=%s&coll=movie-main&spId=%s&spt=movie-casting&DA=EM1&rtmaxcoll=EM1"
DAUM_MOVIE_PHOTO  = "https://search.daum.net/search?w=cin&q=%s&coll=movie-main&spId=%s&spt=movie-photo&DA=EM1&rtmaxcoll=EM1"

DAUM_TV_SRCH      = "https://search.daum.net/search?w=tot&q=%s&rtmaxcoll=TVP"
DAUM_TV_DETAIL    = "https://search.daum.net/search?w=%s&q=%s&spId=%s&spt=tv-info&DA=TVP"
DAUM_TV_EPISODE   = "https://search.daum.net/search?w=%s&q=%s&spId=%s&coll=tv-episode&spt=tv-episode&DA=TVP"

IMDB_TITLE_SRCH   = "http://www.google.com/search?q=site:imdb.com+%s"
TVDB_TITLE_SRCH   = "http://thetvdb.com/api/GetSeries.php?seriesname=%s"

RE_IMDB_ID        = Regex("/(tt\d+)/")

DAUM_CR_TO_MPAA_CR = {
    u'전체관람가': {
        'KMRB': 'kr/A',
        'MPAA': 'G'
    },
    u'12세이상관람가': {
        'KMRB': 'kr/12',
        'MPAA': 'PG'
    },
    u'15세이상관람가': {
        'KMRB': 'kr/15',
        'MPAA': 'PG-13'
    },
    u'청소년관람불가': {
        'KMRB': 'kr/R',
        'MPAA': 'R'
    },
    u'제한상영가': {
        'KMRB': 'kr/X',
        'MPAA': 'NC-17'
    }
}

def Start():
  HTTP.CacheTime = CACHE_1HOUR * 12
  HTTP.Headers['Accept'] = 'text/html, application/json'
  HTTP.Headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

  if Prefs['http_proxy']:
    os.environ['http_proxy'] = Prefs['http_proxy'].strip()
  if Prefs['https_proxy']:
    os.environ['https_proxy'] = Prefs['https_proxy'].strip()

def downloadImage(url, fetchContent=True):
  if not url:
    return None
  if Prefs['use_https_for_image']:
    url = url.replace('http://', 'https://')

  try:
    result = HTTP.Request(url, timeout=60, cacheTime=0, immediate=fetchContent)
  except Ex.HTTPError as e:
    Log('HTTPError %s: %s' % (e.code, e.message))
    return None
  except Exception as e:
    Log('Problem with the request: %s' % e.message)
    return None

  if fetchContent:
    try:
      result = result.content
    except Exception as e:
      Log('Content Error (%s) - %s' % (e, e.message))

  return result

def originalImageUrlFromCdnUrl(url):
  if not url or url == 'thumb_noimg':
    return None
  if 'daumcdn.net' in url or 'kakaocdn.net' in url:
    fname_match = Regex('fname=([^&]*)').search(url)
    if fname_match:
      url = urllib.unquote(fname_match.group(1))

  if url.startswith('//'):
    url = ('http:', 'https:')[Prefs['use_https_for_image']] + url

  return url

def levenshteinRatio(first, second):
  if not first or not second:
    return 0.0
  return 1 - (Util.LevenshteinDistance(first, second) / float(max(len(first), len(second))))

def containsHangul(text):
  for c in list(text):
    if ord(c) >= 44032 and ord(c) <= 55203:
      return True
  return False

####################################################################################################
def searchDaumMovie(results, media, lang):
  items = []
  id_hist = []

  def add_movie_item(m_id, m_title, m_year=None, m_eng_title=''):
    if not m_id or not m_title:
      return
    m_id_str = str(m_id).strip()
    if m_id_str in id_hist:
      return
    yr_str = None
    if m_year:
      yr_match = Regex('^\s*(\d{4})\s*$').search(str(m_year))
      if yr_match:
        yr_str = yr_match.group(1)
    id_hist.append(m_id_str)
    items.append({
      'id': m_id_str,
      'title': m_title.strip(),
      'year': yr_str,
      'eng_title': m_eng_title.strip() if m_eng_title else ''
    })

  # 1. 영화 검색 (다음 통합검색 EM1 컬렉션)
  media_name = unicodedata.normalize('NFKC', unicode(media.name)).strip()
  media_words = media_name.split(' ') if containsHangul(media_name) else [media_name]
  while media_words:
    search_name = ' '.join(media_words)
    Log.Debug("Movie search: %s (%s)" % (search_name, media.year))
    try:
      html = HTML.ElementFromURL(DAUM_MOVIE_SRCH % urllib.quote(search_name.encode('utf8')))
      em1Coll = html.xpath('//div[@id="em1Coll"]')
      if em1Coll:
        em1 = em1Coll[0]
        # (1) 메인 검색 결과
        try:
          tit_a = em1.xpath('.//div[@class="area_tit"]//strong//a')
          if not tit_a:
            tit_a = em1.xpath('.//div[@class="area_tit"]//a')
          if tit_a:
            href = tit_a[0].get('href') or ''
            id_match = Regex('[?&]spId=(\d+)').search(href)
            if id_match:
              m_id = id_match.group(1)
              m_title = ''.join(tit_a[0].xpath('.//text()')).strip()
              m_year = None
              m_eng = ''
              sub_texts = em1.xpath('.//div[@class="sub_header"]//span[@class="txt_split"]/text()')
              if sub_texts:
                sub_str = sub_texts[0].strip()
                yr_match = Regex('(\d{4})\s*$').search(sub_str)
                if yr_match:
                  m_year = yr_match.group(1)
                  m_eng = Regex('^(.*?)(?:,\s*\d{4})?\s*$').search(sub_str).group(1).strip()
                else:
                  m_eng = sub_str
              add_movie_item(m_id, m_title, m_year, m_eng)
        except Exception as e:
          Log.Debug('Error parsing movie base match: %s' % e)

        # (2) 시리즈 영화 (시리즈 탭 내 RAW_SERIES JSON 추출)
        try:
          series_a = em1.xpath(u'.//div[@class="c-section-tab"]//a[text()="시리즈"]')
          if series_a:
            s_href = series_a[0].get('href')
            s_html = HTML.ElementFromURL('https://search.daum.net/search%s' % s_href)
            for sc in s_html.xpath('//div[@id="em1Coll"]//script/text()'):
              raw_match = Regex('const\s+RAW_SERIES\s*=\s*(\[.*?\]);').search(sc)
              if raw_match:
                series_data = JSON.ObjectFromString(raw_match.group(1))
                for s in series_data:
                  add_movie_item(
                    s.get('movieId'),
                    s.get('koreanTitle'),
                    s.get('productionYear'),
                    s.get('englishTitle')
                  )
        except Exception as e:
          Log.Debug('Error parsing movie series: %s' % e)

        # (3) 동명영화
        try:
          dm_items = em1.xpath(u'.//strong[text()="동명영화"]/following-sibling::div[1]//div[@class="c-item-content"]')
          for item in dm_items:
            links = item.xpath('.//a')
            target_a = None
            for a in links:
              href = a.get('href') or ''
              if 'spId=' in href and ''.join(a.xpath('.//text()')).strip():
                target_a = a
                break
            if target_a is None:
              continue
            id_match = Regex('[?&]spId=(\d+)').search(target_a.get('href'))
            if id_match:
              m_id = id_match.group(1)
              m_title = ''.join(target_a.xpath('.//text()')).strip()
              m_year = None
              sub_descs = item.xpath('.//span[contains(@class, "conts-subdesc")]/text()')
              if sub_descs:
                yr_match = Regex('(\d{4})').search(sub_descs[0])
                if yr_match:
                  m_year = yr_match.group(1)
              add_movie_item(m_id, m_title, m_year)
        except Exception as e:
          Log.Debug('Error parsing same-name movies: %s' % e)

        if items:
          break
    except Exception as e:
      Log.Debug('Error in movie HTML search: %s' % e)

    if containsHangul(media_words.pop()):
      break

  # 2. 영화 검색 (자동완성 API - 보조 및 추가 매칭)
  media_name = unicodedata.normalize('NFKC', unicode(media.name)).strip()
  media_words = media_name.split(' ') if containsHangul(media_name) else [media_name]
  while media_words:
    search_name = ' '.join(media_words)
    try:
      data = JSON.ObjectFromURL(
        url=DAUM_MOVIE_SGST % urllib.quote(search_name.encode('utf8')),
        headers={'authorization': 'KakaoAK eef996dbcc900b7c164d80b6653565b3'}
      )
      movies = data.get('items', {}).get('movie', [])
      if movies:
        for movie in movies:
          parts = movie['item'].split('|')
          if len(parts) >= 6:
            add_movie_item(parts[1], parts[2], parts[5], parts[3])
          elif len(parts) >= 3:
            add_movie_item(parts[1], parts[2])
        break
    except Exception as e:
      Log.Debug('Error in movie suggest search: %s' % e)

    if containsHangul(media_words.pop()):
      break

  if not items:
    Log.Debug('No movie matches found')
    return

  orig_name = unicodedata.normalize('NFKC', unicode(media.name)).strip()
  for item in items:
    title = item['title']
    year = item['year']
    eng_title = item['eng_title']

    norm_media = orig_name.replace(' ', '').lower()
    norm_title = title.replace(' ', '').lower()

    base_ratio = max(
      levenshteinRatio(orig_name, title),
      levenshteinRatio(orig_name, eng_title)
    )
    if norm_media == norm_title:
      score = 80
    else:
      score = int(base_ratio * 80)

    if media.year and year:
      try:
        score += (2 - min(2, abs(int(media.year) - int(year)))) * 10
      except: pass
    elif norm_media == norm_title:
      score = 95

    score = max(1, min(100, score))
    Log.Debug('Movie Match: ID=%s, media_name=%s, title=%s, year=%s, score=%d' % (item['id'], orig_name, title, year, score))
    results.Append(MetadataSearchResult(id=item['id'], name=title, year=year, score=score, lang=lang))

def searchDaumTV(results, media, lang):
  media_name = unicodedata.normalize('NFKC', unicode(media.show)).strip()
  media_year = media.year
  Log.Debug("TV search: %s (%s)" % (media_name, media_year))

  html = HTML.ElementFromURL(DAUM_TV_SRCH % urllib.quote(media_name.encode('utf8')))
  try:
    tvp = html.xpath('//div[@id="tvpColl"]')[0]
  except:
    Log.Debug('No TV matches found')
    return

  items = []

  # 1. 메인 검색 결과 추출
  try:
    tit_links = tvp.xpath('.//div[@class="area_tit"]//a')
    if tit_links:
      title_a = tit_links[0]
      title_href = title_a.get('href') or ''
      title = ''.join(title_a.xpath('.//text()')).strip()
      if not title:
        q_match = Regex('[?&]q=([^&]*)').search(title_href)
        if q_match:
          title = urllib.unquote(q_match.group(1))
      id_match = Regex('[?&]spId=(\d+)').search(title_href) or Regex('[?&]irk=(\d+)').search(title_href)
      if id_match and title:
        id = id_match.group(1)
        year = None
        try:
          texts = tvp.xpath('.//div[@class="sub_header"]//span[@class="txt-split"]')
          for text in texts:
            if text.text:
              year_match = Regex('(\d{2,4})\.\d+\.\d+\.\s*~').search(text.text)
              if year_match:
                y = year_match.group(1)
                year = '20' + y if len(y) == 2 else y
                break
        except: pass
        items.append({'id': id, 'title': title, 'year': year})
  except Exception as e:
    Log.Debug('Error extracting TV base match: %s' % e)

  # 2. TV검색 > 시리즈
  more_a = tvp.xpath(u'.//a[text()="시리즈"]')
  if more_a:
    try:
      series_html = HTML.ElementFromURL('https://search.daum.net/search%s' % more_a[0].get('href'))
      season_items = series_html.xpath(u'.//div[@class="pdt2"]//li')
      for li in season_items:
        try:
          links = li.xpath(u'.//a')
          a = links[1] if len(links) >= 2 else links[0]
          href = a.get('href') or ''
          id_match = Regex('[?&]spId=(\d+)').search(href) or Regex('[?&]irk=(\d+)').search(href)
          if not id_match:
            continue
          id = id_match.group(1)
          title = ''.join(a.xpath('.//text()')).strip()
          year = None
          try:
            spans = li.xpath(u'.//span')
            if spans and spans[0].text:
              year = Regex('(\d{4})\.\d+').search(spans[0].text).group(1)
          except: pass
          items.append({'id': id, 'title': title, 'year': year})
        except: pass
    except Exception as e:
      Log.Debug('Error in TV series match: %s' % e)
  else:
    lis = tvp.xpath(u'//div[@id="tv_series"]//li')
    for li in lis:
      try:
        a_list = li.xpath(u'./a')
        if not a_list:
          continue
        a = a_list[0]
        href = a.get('href') or ''
        id_match = Regex('[?&]irk=(\d+)').search(href) or Regex('[?&]spId=(\d+)').search(href)
        if not id_match:
          continue
        id = id_match.group(1)
        title = ''.join(a.xpath('.//text()')).strip()
        year = None
        try:
          spans = li.xpath(u'./span')
          if spans and spans[0].text:
            year = Regex('(\d{4})\.\d+').search(spans[0].text).group(1)
        except: pass
        items.append({'id': id, 'title': title, 'year': year})
      except: pass

  # 3. TV검색 > 동명프로그램
  dm_items = tvp.xpath(u'.//div[contains(@class,"cont_pannel")]//strong[text()="동명프로그램"]/following-sibling::div[1]//div[@class="c-item-content"]')

  for item in dm_items:
    try:
      links = item.xpath(u'.//a')
      target_a = None
      for a in links:
        href = a.get('href') or ''
        if 'spId=' in href or 'irk=' in href:
          target_a = a
          break
      if target_a is None:
        continue

      href = target_a.get('href')
      id_match = Regex('[?&]spId=(\d+)').search(href) or Regex('[?&]irk=(\d+)').search(href)
      if not id_match:
        continue
      id = id_match.group(1)
      title = ''.join(target_a.xpath('.//text()')).strip()
      if not title:
        for a in links:
          t_str = ''.join(a.xpath('.//text()')).strip()
          if t_str:
            title = t_str
            break

      year = None
      try:
        program_texts = item.xpath(u'.//dd[contains(@class, "program")]//text()')
        for txt in program_texts:
          year_match = Regex('(\d{4})').search(txt)
          if year_match:
            year = year_match.group(1)
            break
      except: pass

      items.append({'id': id, 'title': title, 'year': year})
    except: pass

  id_hist = []
  for item in items:
    if item['id'] not in id_hist:
      norm_media = media_name.replace(' ', '').lower()
      norm_title = item['title'].replace(' ', '').lower()

      base_ratio = levenshteinRatio(media_name, item['title'])

      if norm_media == norm_title:
        score = 100
      elif norm_media in norm_title or norm_title in norm_media:
        score = 95
      else:
        score = int(base_ratio * 90)

      if media_year and item['year']:
        try:
          score += (2 - min(2, abs(int(media_year) - int(item['year'])))) * 5
        except: pass

      score = max(1, min(100, score))

      Log.Debug('TV Match: ID=%s, media_name=%s, title=%s, year=%s, score=%d' % (item['id'], media_name, item['title'], item['year'], score))
      results.Append(MetadataSearchResult(id=item['id'], name=item['title'], year=item['year'], score=score, lang=lang))
      id_hist.append(item['id'])

####################################################################################################
def updateDaumMovie(metadata):
  poster_url = None
  q_param = urllib.quote((metadata.title or u'영화').encode('utf8'))

  # (1) 영화 기본 정보 (통합검색 EM1 movie-info)
  try:
    html = HTML.ElementFromURL(DAUM_MOVIE_INFO % (q_param, metadata.id))
    em1_list = html.xpath('//div[@id="em1Coll"]/div[@class="card_comp"]')
    if not em1_list:
      Log.Debug('No em1Coll found for movie ID=%s' % metadata.id)
      return
    em1 = em1_list[0]

    # 제목
    tit_nodes = em1.xpath('.//div[@class="area_tit"]//strong//a/text()')
    if tit_nodes:
      metadata.title = tit_nodes[0].strip()
      metadata.title_sort = unicodedata.normalize('NFKD' if Prefs['use_title_decomposition'] else 'NFKC', metadata.title)
      q_param = urllib.quote(metadata.title.encode('utf8'))

    # 원제 및 제작년도
    sub_nodes = em1.xpath('.//div[@class="sub_header"]//span[@class="txt_split"]/text()')
    if sub_nodes:
      sub_str = sub_nodes[0].strip()
      yr_match = Regex('(\d{4})\s*$').search(sub_str)
      if yr_match:
        metadata.year = int(yr_match.group(1))
        orig_tit = Regex('^(.*?)(?:,\s*\d{4})?\s*$').search(sub_str).group(1).strip()
        if orig_tit:
          metadata.original_title = orig_tit
      else:
        metadata.original_title = sub_str

    # 개봉일
    rel_nodes = em1.xpath(u'.//dt[text()="개봉"]/following-sibling::dd[1]//text()')
    if rel_nodes:
      rel_match = Regex('(\d{4}\.\d{2}\.\d{2})').search(''.join(rel_nodes))
      if rel_match:
        metadata.originally_available_at = Datetime.ParseDate(rel_match.group(1), '%Y.%m.%d').date()
        if not metadata.year:
          metadata.year = metadata.originally_available_at.year

    # 국가
    country_nodes = em1.xpath(u'.//dt[text()="국가"]/following-sibling::dd[1]//text()')
    if country_nodes:
      metadata.countries.clear()
      for c in Regex('[,/]').split(''.join(country_nodes)):
        if c.strip():
          metadata.countries.add(c.strip())

    # 장르
    genre_nodes = em1.xpath(u'.//dt[text()="장르"]/following-sibling::dd[1]//text()')
    if genre_nodes:
      metadata.genres.clear()
      for g in Regex('[,/]').split(''.join(genre_nodes)):
        if g.strip():
          metadata.genres.add(g.strip())

    # 상영시간
    dur_nodes = em1.xpath(u'.//dt[text()="시간"]/following-sibling::dd[1]//text()')
    if dur_nodes:
      dur_match = Regex('(\d+)').search(''.join(dur_nodes))
      if dur_match:
        metadata.duration = int(dur_match.group(1)) * 60 * 1000

    # 관람등급
    cr_nodes = em1.xpath(u'.//dt[text()="등급"]/following-sibling::dd[1]//text()')
    if cr_nodes:
      cr_raw = ''.join(cr_nodes).strip()
      cr_str = cr_raw.replace(' ', '')
      if cr_str in DAUM_CR_TO_MPAA_CR:
        metadata.content_rating = DAUM_CR_TO_MPAA_CR[cr_str]['MPAA' if Prefs['use_mpaa'] else 'KMRB']
      else:
        metadata.content_rating = cr_raw

    # 평점
    rate_dd = em1.xpath(u'.//dt[text()="평점"]/following-sibling::dd[1]')
    if rate_dd:
      rate_txt = ''.join(rate_dd[0].xpath('.//text()'))
      net_match = Regex(u'네티즌\s*(\d+(?:\.\d+)?)').search(rate_txt)
      exp_match = Regex(u'전문가\s*(\d+(?:\.\d+)?)').search(rate_txt)
      if net_match:
        metadata.rating = float(net_match.group(1))
      elif exp_match:
        metadata.rating = float(exp_match.group(1))

    # 줄거리
    desc_nodes = em1.xpath('.//p[contains(@class, "desc_story")]/text()')
    if desc_nodes:
      metadata.summary = String.DecodeHTMLEntities(String.StripTags(desc_nodes[0])).strip()

    # 대표 포스터
    poster_imgs = em1.xpath('.//div[@class="c-item-exact"]//div[@class="wrap_thumb"]//img/@data-original-src')
    if not poster_imgs:
      poster_imgs = em1.xpath('.//div[@class="wrap_thumb"]//img/@data-original-src')
    if poster_imgs:
      poster_url = originalImageUrlFromCdnUrl(poster_imgs[0])

  except Exception as e:
    Log.Debug('Error in updateDaumMovie base info: %s' % repr(e))

  # (2) 출연 및 제작진 (movie-casting 내 RAW_CASTS, RAW_CREWS, RAW_COMPANIES JSON 추출)
  directors = []
  producers = []
  writers = []
  roles = []

  try:
    cast_html = HTML.ElementFromURL(DAUM_MOVIE_CAST % (q_param, metadata.id))
    for sc in cast_html.xpath('//div[@id="em1Coll"]//script/text()'):
      casts_match = Regex('const\s+RAW_CASTS\s*=\s*(\[.*?\]);').search(sc)
      if casts_match:
        raw_casts = JSON.ObjectFromString(casts_match.group(1))
        for group in raw_casts:
          for c in group.get('casts', []):
            person = c.get('person', {})
            name = person.get('koreanName') or person.get('englishName')
            if not name:
              continue
            cast_item = {'name': name}
            if person.get('imageUrl'):
              cast_item['photo'] = person['imageUrl']
            job_role = c.get('jobRole') or group.get('jobRole') or ''
            if c.get('isDirector') or job_role == u'감독':
              directors.append(cast_item)
            else:
              cast_item['role'] = c.get('playRole') or job_role
              roles.append(cast_item)

      crews_match = Regex('const\s+RAW_CREWS\s*=\s*(\[.*?\]);').search(sc)
      if crews_match:
        raw_crews = JSON.ObjectFromString(crews_match.group(1))
        for group in raw_crews:
          job_role = group.get('jobRole') or ''
          for c in group.get('crews', []):
            person = c.get('person', {})
            name = person.get('koreanName') or person.get('englishName')
            if not name:
              continue
            staff_item = {'name': name}
            if person.get('imageUrl'):
              staff_item['photo'] = person['imageUrl']
            c_role = c.get('jobRole') or job_role
            if c_role in [u'제작', u'기획', u'프로듀서', u'책임프로듀서']:
              producers.append(staff_item)
            elif c_role in [u'각본', u'원작', u'극본', u'각색']:
              writers.append(staff_item)

      comp_match = Regex('const\s+RAW_COMPANIES\s*=\s*(\[.*?\]);').search(sc)
      if comp_match:
        raw_comp = JSON.ObjectFromString(comp_match.group(1))
        for group in raw_comp:
          companies = group.get('companies', [])
          if companies:
            metadata.studio = companies[0].get('koreanName') or companies[0].get('englishName')
            break
  except Exception as e:
    Log.Debug('Error in updateDaumMovie cast info: %s' % repr(e))

  if directors:
    metadata.directors.clear()
    for director in directors:
      meta_director = metadata.directors.new()
      if 'name' in director:
        meta_director.name = director['name']
      if 'photo' in director:
        meta_director.photo = director['photo']
  if producers:
    metadata.producers.clear()
    for producer in producers:
      meta_producer = metadata.producers.new()
      if 'name' in producer:
        meta_producer.name = producer['name']
      if 'photo' in producer:
        meta_producer.photo = producer['photo']
  if writers:
    metadata.writers.clear()
    for writer in writers:
      meta_writer = metadata.writers.new()
      if 'name' in writer:
        meta_writer.name = writer['name']
      if 'photo' in writer:
        meta_writer.photo = writer['photo']
  if roles:
    metadata.roles.clear()
    for role in roles:
      meta_role = metadata.roles.new()
      if 'role' in role:
        meta_role.role = role['role']
      if 'name' in role:
        meta_role.name = role['name']
      if 'photo' in role:
        meta_role.photo = role['photo']

  # (3) 포스터 및 스틸컷 (movie-photo 내 dataSource JSON 추출)
  max_poster = int(Prefs['max_num_posters'])
  max_art = int(Prefs['max_num_arts'])
  idx_poster = 0
  idx_art = 0

  try:
    photo_html = HTML.ElementFromURL(DAUM_MOVIE_PHOTO % (q_param, metadata.id))
    for cp in photo_html.xpath('//div[@id="em1Coll"]//div[@class="cont_photo"]'):
      cat_list = cp.xpath('.//div[@data-category]/@data-category')
      sc_list = cp.xpath('.//script/text()')
      if not cat_list or not sc_list:
        continue
      cat = cat_list[0]
      photo_data = JSON.ObjectFromString(sc_list[0].strip())
      for item in photo_data.get('dataSource', []):
        img_url = item.get('src')
        if not img_url:
          continue
        if cat == 'steelCuts' and idx_art < max_art:
          idx_art += 1
          if img_url not in metadata.art:
            try:
              metadata.art[img_url] = Proxy.Preview(downloadImage(img_url), sort_order=idx_art)
            except Exception as e:
              Log(str(e))
        elif cat == 'posters' and idx_poster < max_poster:
          idx_poster += 1
          if img_url not in metadata.posters:
            try:
              metadata.posters[img_url] = Proxy.Preview(downloadImage(img_url), sort_order=idx_poster)
            except Exception as e:
              Log(str(e))
  except Exception as e:
    Log.Debug('Error in updateDaumMovie photo info: %s' % repr(e))

  if len(metadata.posters) == 0 and poster_url:
    try:
      metadata.posters[poster_url] = Proxy.Preview(downloadImage(poster_url), sort_order=100)
    except Exception as e:
      Log(str(e))

  Log.Debug('Total %d posters, %d artworks' % (len(metadata.posters), len(metadata.art)))

####################################################################################################
def updateDaumTV(metadata, media):
  html = HTML.ElementFromURL(DAUM_TV_DETAIL % ('tv', urllib.quote(media.title.encode('utf8')), metadata.id))
  try:
    tvp = html.xpath('//div[@id="tvpColl"]')[0]
    card0 = tvp.xpath('./div[@class="card_comp"]')[0]
  except:
    Log.Debug('No TV matches found')
    return

  # 1. TV 쇼 기본 정보 설정
  try:
    Log.Debug("TV Update: %s" % media.title)
    metadata.title = media.title
    metadata.title_sort = unicodedata.normalize('NFKD' if Prefs['use_title_decomposition'] else 'NFKC', metadata.title)
    metadata.original_title = ''
    metadata.rating = None
    metadata.genres.clear()

    # 줄거리 추출
    try:
      summary_nodes = card0.xpath(u'.//strong[.="줄거리"]/following-sibling::p/text()')
      if not summary_nodes:
        summary_nodes = card0.xpath('.//p[contains(@class, "desc_story")]/text()')
      if summary_nodes:
        metadata.summary = String.DecodeHTMLEntities(String.StripTags(summary_nodes[0]).strip())
    except: pass

    # 제작사(방송사) 및 장르 추출
    try:
      studio_nodes = card0.xpath(u'.//dt[.="제작"]/following-sibling::dd/text()') or card0.xpath('.//dd[@class="program"]//a/text()')
      if studio_nodes:
        metadata.studio = studio_nodes[0].strip()

      genre_nodes = card0.xpath(u'.//dt[.="장르"]/following-sibling::dd/text()')
      if not genre_nodes:
        genre_nodes = card0.xpath('.//div[@class="sub_header"]//span[@class="txt_info"][1]//a/text()')
      if genre_nodes:
        metadata.genres.clear()
        for g in genre_nodes[0].split(','):
          if g.strip():
            metadata.genres.add(g.strip())
            Log.Debug("Genre added: %s" % g.strip())
    except: pass

    # 첫 방영일 추출 (sub_header 내 'YY.MM.DD. ~' 형식)
    try:
      sub_texts = card0.xpath('.//div[@class="sub_header"]//span[@class="txt-split"]/text()')
      for txt in sub_texts:
        date_match = Regex('(\d{2,4})\.(\d{1,2})\.(\d{1,2})\.\s*~').search(txt)
        if date_match:
          y, m, d = date_match.group(1), date_match.group(2), date_match.group(3)
          year_str = '20' + y if len(y) == 2 else y
          metadata.originally_available_at = Datetime.ParseDate('%s.%s.%s' % (year_str, m, d), '%Y.%m.%d').date()
          break
    except: pass

    # 방송 시간 정보 추출 및 요약문에 추가
    try:
      air_time_nodes = card0.xpath(u'.//dt[.="방송시간"]/following-sibling::dd/text()')
      if not air_time_nodes:
        air_time_nodes = [t.strip() for t in card0.xpath('.//dd[@class="program"]/text()') if t.strip()]
      if air_time_nodes and metadata.summary:
        air_info = air_time_nodes[0].strip()
        if air_info:
          metadata.summary = u"%s (%s)\n\n%s" % (metadata.summary.split('\n\n')[0], air_info, metadata.summary.split('\n\n')[-1])
    except: pass

    # 포스터 추출 (첫 번째 대표 포스터만 가져오며 하단 OTT 아이콘은 제외)
    try:
      poster_imgs = card0.xpath('.//div[@class="c-item-exact"]//div[@class="wrap_thumb"]//img/@data-original-src')
      if not poster_imgs:
        poster_imgs = card0.xpath('.//div[@class="wrap_thumb"]//img/@data-original-src')
      if poster_imgs:
        poster_url = originalImageUrlFromCdnUrl(poster_imgs[0])
        if poster_url and poster_url not in metadata.posters:
          metadata.posters[poster_url] = Proxy.Preview(HTTP.Request(poster_url, cacheTime=0), sort_order=len(metadata.posters) + 1)
    except: pass

    # 배경 아트(Background Art) 추출 - 포토 섹션 활용 (존재할 경우)
    try:
      photo_links = card0.xpath(u'.//a[.="포토"]')
      if photo_links:
        photo_html = HTML.ElementFromURL('https://search.daum.net/search%s' % photo_links[0].get('href'))
        photo_items = photo_html.xpath('.//div[@class="pdt2"]//img/@data-original-src')
        for i, p_url in enumerate(photo_items):
          full_url = originalImageUrlFromCdnUrl(p_url)
          if full_url and full_url not in metadata.art:
            metadata.art[full_url] = Proxy.Preview(HTTP.Request(full_url, cacheTime=0), sort_order=i + 1)
            if i >= 5:
              break
    except: pass

    # 시청 등급 및 방영 상태 추출
    try:
      info_texts = card0.xpath(u'.//span[@class="txt_info"]//text()')
      for txt in info_texts:
        if u'세이상' in txt or u'전체관람가' in txt:
          metadata.content_rating = txt.strip()
          Log.Debug("Content Rating found: %s" % metadata.content_rating)
          break

      status_nodes = card0.xpath(u'.//span[contains(@class, "txt_status")]/text()')
      if not status_nodes:
        status_nodes = [t.strip() for t in info_texts if t.strip() in [u'완결', u'방송중', u'방송예정']]
      if status_nodes:
        status_txt = status_nodes[0].strip()
        if status_txt and metadata.summary:
          metadata.summary = u"[%s] %s" % (status_txt, metadata.summary)
          Log.Debug("Air status added to summary: %s" % status_txt)
    except: pass
  except Exception as e:
    Log.Debug('Error updating TV base info: %s' % e)

  # 2. 출연진 및 제작진 정보
  directors = []
  producers = []
  writers = []
  try:
    cast_links = card0.xpath(u'.//a[.="출연"]')
    if cast_links:
      cast_href = cast_links[0].get('href')
      # w=tot일 경우 제작진 탭이 생략되므로 w=tv로 요청하여 전체 출연/제작진 정보를 가져옴
      cast_href = cast_href.replace('?w=tot&', '?w=tv&')
      cast_html = HTML.ElementFromURL('https://search.daum.net/search%s' % cast_href)

      roles = []
      # 제작진 (감독, 연출, 작가 등)
      for item in cast_html.xpath(u'//div[@class="pdt2" and @data-tab="제작"]/ul/li'):
        try:
          role_txt = ''.join(item.xpath('.//div[@class="item-contents"]//text()')).strip().replace(u'이전 ', '')
          name_txt = ''.join(item.xpath('.//div[@class="item-title"]//text()')).strip()
          if not role_txt or not name_txt:
            continue

          img_nodes = item.xpath('.//img/@data-original-src')
          photo = originalImageUrlFromCdnUrl(img_nodes[0]) if img_nodes else None

          cast = {'name': name_txt, 'photo': photo}
          if role_txt in [u'감독', u'연출', u'조감독']:
            directors.append(cast)
          elif role_txt in [u'제작', u'프로듀서', u'책임프로듀서', u'기획']:
            producers.append(cast)
          elif role_txt in [u'극본', u'각본', u'원작', u'작가']:
            writers.append(cast)
        except: pass

      # 출연진 (드라마는 item-title에 배역명, item-contents에 배우명이 위치하며, 예능은 반대로 위치함)
      cast_items = cast_html.xpath(u'//div[@class="pdt2" and @data-tab="출연"]/ul/li')
      if not cast_items:
        cast_items = cast_html.xpath(u'//div[contains(@class, "cont_cast")]//div[@class="pdt2"]/ul/li')

      for item in cast_items:
        try:
          title_str = ' '.join(t.strip() for t in item.xpath('.//div[@class="item-title"]//text()') if t.strip())
          content_str = ' '.join(t.strip() for t in item.xpath('.//div[@class="item-contents"]//text()') if t.strip())

          if not title_str or title_str == u'인물관계도':
            continue

          title_links = item.xpath('.//div[@class="item-title"]//a/@href')
          content_links = item.xpath('.//div[@class="item-contents"]//a/@href')

          # 배우 프로필 링크(ppkey= 또는 rtmaxcoll=PRF)가 item-contents에 있으면 드라마 구조(title=배역, content=배우)
          if any('ppkey=' in h or 'rtmaxcoll=PRF' in h for h in content_links) or item.xpath('.//div[@class="item-title"]//span[@class="txt_role"]'):
            actor_name = content_str
            role_name = Regex(u'\s*역$').sub('', title_str).strip()
          else:
            actor_name = title_str
            role_name = content_str

          if not actor_name:
            continue

          cast = {'name': actor_name, 'role': role_name}
          img_nodes = item.xpath('.//img/@data-original-src')
          if img_nodes:
            photo_url = originalImageUrlFromCdnUrl(img_nodes[0])
            if photo_url:
              cast['photo'] = photo_url
          roles.append(cast)
        except: pass

      if roles:
        metadata.roles.clear()
        for r in roles:
          meta_role = metadata.roles.new()
          meta_role.name = r.get('name')
          meta_role.role = r.get('role')
          if r.get('photo'):
            meta_role.photo = r.get('photo')
  except Exception as e:
    Log.Debug('Error updating TV cast info: %s' % e)

  # 3. 시즌 정보 수집
  season_info = []
  try:
    more_links = card0.xpath(u'.//a[.="시리즈"]')
    if more_links:
      Log.Debug("Series link found: %s" % more_links[0].get('href'))
      epi_html = HTML.ElementFromURL('https://search.daum.net/search%s' % more_links[0].get('href'))
      season_items = epi_html.xpath('.//div[@class="pdt2"]//li')
      for s_item in season_items:
        try:
          a_tags = s_item.xpath('.//a')
          a = a_tags[1] if len(a_tags) >= 2 else a_tags[0]
          href = a.get('href') or ''
          s_id_match = Regex('[?&]spId=(\d+)').search(href) or Regex('[?&]irk=(\d+)').search(href)
          if not s_id_match:
            continue
          s_id = s_id_match.group(1)
          s_title = ''.join(a.xpath('.//text()')).strip()
          s_num_match = Regex('(\d+)\s*$').search(s_title)
          s_num = s_num_match.group(1) if s_num_match else '1'

          year = None
          span_nodes = s_item.xpath('.//span')
          if span_nodes and span_nodes[0].text:
            year_match = Regex('(\d{4})\.\d+').search(span_nodes[0].text)
            if year_match:
              year = year_match.group(1)

          season_info.append({
            'id': s_id,
            'title': s_title,
            'season': s_num,
            'year': year,
            'href': 'https://search.daum.net/search%s' % href.replace('?w=tot&', '?w=tv&')
          })
        except: pass

    if not season_info:
      year = None
      try:
        texts = card0.xpath('.//div[@class="sub_header"]//span[@class="txt-split"]')
        for t in texts:
          if t.text:
            y_match = Regex('(\d{2,4})\.\d+\.\d+\.\s*~').search(t.text)
            if y_match:
              y = y_match.group(1)
              year = '20' + y if len(y) == 2 else y
              break
      except: pass
      season_info.append({
        'id': metadata.id,
        'title': media.title,
        'season': '1',
        'year': year,
        'href': DAUM_TV_DETAIL % ('tv', urllib.quote(media.title.encode('utf8')), metadata.id)
      })
  except Exception as e:
    Log.Debug('Error collecting season info: %s' % e)

  # 최신 시즌의 포스터를 쇼의 대표 포스터로 추가
  max_season_num = -1
  latest_season_poster_href = None

  for s_item in season_info:
    try:
      s_num = int(s_item['season'])
      if s_num > max_season_num:
        max_season_num = s_num
        latest_season_poster_href = s_item['href']
    except: pass

  if max_season_num != -1 and latest_season_poster_href:
    try:
      Log.Debug("Fetching latest season (%d) poster as representative" % max_season_num)
      ls_html = HTML.ElementFromURL(latest_season_poster_href)
      ls_poster_imgs = ls_html.xpath(u'//div[@id="tvpColl"]//div[@class="c-item-exact"]//div[@class="wrap_thumb"]//img/@data-original-src')
      if not ls_poster_imgs:
        ls_poster_imgs = ls_html.xpath(u'//div[@id="tvpColl"]//div[@class="wrap_thumb"]//img/@data-original-src')
      if ls_poster_imgs:
        ls_poster_url = originalImageUrlFromCdnUrl(ls_poster_imgs[0])
        if ls_poster_url:
          metadata.posters[ls_poster_url] = Proxy.Preview(HTTP.Request(ls_poster_url, cacheTime=0), sort_order=0)
          Log.Debug("Latest season poster (Season %d) forced as primary: %s" % (max_season_num, ls_poster_url))
    except Exception as e:
      Log.Debug("Error setting latest season poster: %s" % e)

  # 4. 각 시즌 및 에피소드 정보 업데이트
  for season_num in media.seasons:
    for s_item in season_info:
      if s_item['season'] == str(season_num):
        try:
          Log.Debug("Updating Season: %s" % season_num)
          s_html = HTML.ElementFromURL(s_item['href'])
          s_title = s_item.get('title') or media.title

          # 시즌 포스터
          try:
            s_poster_imgs = s_html.xpath('//div[@id="tvpColl"]//div[@class="c-item-exact"]//div[@class="wrap_thumb"]//img/@data-original-src')
            if not s_poster_imgs:
              s_poster_imgs = s_html.xpath('//div[@id="tvpColl"]//div[@class="wrap_thumb"]//img/@data-original-src')
            if s_poster_imgs:
              s_poster_url = originalImageUrlFromCdnUrl(s_poster_imgs[0])
              if s_poster_url and s_poster_url not in metadata.seasons[season_num].posters:
                metadata.seasons[season_num].posters[s_poster_url] = Proxy.Preview(HTTP.Request(s_poster_url, cacheTime=0), sort_order=len(metadata.seasons[season_num].posters) + 1)
          except: pass

          # 에피소드 리스트 (회차 선택기)
          episode_map = {}
          try:
            tab_links = s_html.xpath(u'//div[@id="tvpColl"]//a[.="회차"]')
            if tab_links:
              epi_list_html = HTML.ElementFromURL('https://search.daum.net/search%s' % tab_links[0].get('href'))
              options = epi_list_html.xpath('//div[@id="tvpColl"]//q-select//option')
              episode_map = {opt.get('value').replace(u'회', '').strip(): opt.get('data-sp-id') for opt in options if opt.get('value') and opt.get('data-sp-id')}
          except: pass

          # 각 에피소드 정보 업데이트
          for epi_num in media.seasons[season_num].episodes:
            if str(epi_num) not in episode_map:
              continue
            try:
              Log.Debug("Updating Episode: %s" % epi_num)
              epi_query = urllib.quote(s_title.encode('utf8')) + urllib.quote(" " + str(epi_num) + "회")
              epi_page = HTML.ElementFromURL(DAUM_TV_EPISODE % ('tv', epi_query, episode_map[str(epi_num)]))
              episode = metadata.seasons[season_num].episodes[epi_num]

              # 에피소드 줄거리
              summary_nodes = epi_page.xpath('//div[@id="tvpColl"]//p[@class="desc_story"]/text()')
              if summary_nodes:
                episode.summary = summary_nodes[0].strip()

              # 에피소드 제목
              tit_nodes = epi_page.xpath('//div[@id="tvpColl"]//strong[@class="tit_story"]')
              if tit_nodes:
                ep_tit = ''.join(tit_nodes[0].xpath('.//text()')).strip()
                if ep_tit:
                  episode.title = ep_tit

              # 에피소드 썸네일 (영상 클립 영역 내 썸네일)
              thumb_nodes = epi_page.xpath('//div[@id="tvpColl"]//div[@class="player_sch"]//img/@data-original-src | //div[@id="tvpColl"]//div[@class="bundle_vclip"]//img/@data-original-src')
              if thumb_nodes:
                t_url = originalImageUrlFromCdnUrl(thumb_nodes[0])
                if t_url and t_url not in episode.thumbs:
                  episode.thumbs[t_url] = Proxy.Preview(HTTP.Request(t_url, cacheTime=0), sort_order=len(episode.thumbs) + 1)

              # 방영일
              try:
                date_nodes = epi_page.xpath(u'//div[@id="tvpColl"]//span[.="방영일"]/../text()')
                if date_nodes:
                  date_str = date_nodes[0].strip().rsplit('.', 1)[0]
                  episode.originally_available_at = Datetime.ParseDate(date_str, '%Y.%m.%d').date()
              except: pass

              # 감독 및 작가 설정
              if directors:
                episode.directors.clear()
                for d in directors:
                  meta_d = episode.directors.new()
                  meta_d.name = d.get('name')
                  if d.get('photo'):
                    meta_d.photo = d.get('photo')
              if writers:
                episode.writers.clear()
                for w in writers:
                  meta_w = episode.writers.new()
                  meta_w.name = w.get('name')
                  if w.get('photo'):
                    meta_w.photo = w.get('photo')
            except Exception as e:
              Log.Debug('Error updating episode %s: %s' % (epi_num, e))
        except Exception as e:
          Log.Debug('Error updating season %s: %s' % (season_num, e))

####################################################################################################
class DaumMovieAgent(Agent.Movies):
  name = "Daum Movie"
  languages = [Locale.Language.Korean]
  primary_provider = True
  accepts_from = ['com.plexapp.agents.localmedia']

  def search(self, results, media, lang, manual=False):
    return searchDaumMovie(results, media, lang)

  def update(self, metadata, media, lang):
    Log.Info("in update ID = %s" % metadata.id)
    updateDaumMovie(metadata)

    # override metadata ID
    if Prefs['override_movie_id'] != 'None':
      title = metadata.original_title if metadata.original_title else metadata.title
      if Prefs['override_movie_id'] == 'IMDB':
        url = IMDB_TITLE_SRCH % urllib.quote_plus("%s %d" % (title.encode('utf-8'), metadata.year))
        page = HTTP.Request(url).content
        match = RE_IMDB_ID.search(page)
        if match:
          metadata.id = match.group(1)
          Log.Info("override with IMDB ID, %s" % metadata.id)

class DaumMovieTvAgent(Agent.TV_Shows):
  name = "Daum Movie"
  primary_provider = True
  languages = [Locale.Language.Korean]
  accepts_from = ['com.plexapp.agents.localmedia']

  def search(self, results, media, lang, manual=False):
    return searchDaumTV(results, media, lang)

  def update(self, metadata, media, lang):
    Log.Info("in update ID = %s" % metadata.id)
    updateDaumTV(metadata, media)

    # override metadata ID
    if Prefs['override_tv_id'] != 'None':
      title = metadata.original_title if metadata.original_title else metadata.title
      if Prefs['override_tv_id'] == 'TVDB':
        url = TVDB_TITLE_SRCH % urllib.quote_plus(title.encode('utf-8'))
        xml = XML.ElementFromURL(url)
        node = xml.xpath('/Data/Series/seriesid')
        if node:
          metadata.id = node[0].text
          Log.Info("override with TVDB ID, %s" % metadata.id)
