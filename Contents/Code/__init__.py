# -*- coding: utf-8 -*-
# Daum Movie

import urllib, unicodedata, os

DAUM_MOVIE_SRCH   = "https://search.daum.net/search?w=tot&q=%s&rtmaxcoll=EM1"
DAUM_MOVIE_SGST   = "https://dapi.kakao.com/suggest-hub/v1/search.json?service=movie-v2&cate=movie&multiple=1&q=%s"

DAUM_MOVIE_DETAIL = "https://movie.daum.net/api/movie/%s/main"
DAUM_MOVIE_CAST   = "https://movie.daum.net/api/movie/%s/crew"
DAUM_MOVIE_PHOTO  = "https://movie.daum.net/api/movie/%s/photoList?page=1&size=100"

DAUM_TV_SRCH      = "https://search.daum.net/search?w=tot&q=%s&rtmaxcoll=TVP"
DAUM_TV_DETAIL    = "https://search.daum.net/search?w=%s&q=%s&spId=%s&spt=tv-info&DA=TVP"
DAUM_TV_EPISODE   = "https://search.daum.net/search?w=%s&q=%s&spId=%s&coll=tv-episode&spt=tv-episode&DA=TVP"

IMDB_TITLE_SRCH   = "http://www.google.com/search?q=site:imdb.com+%s"
TVDB_TITLE_SRCH   = "http://thetvdb.com/api/GetSeries.php?seriesname=%s"

RE_YEAR_IN_NAME   =  Regex('\((\d+)\)')
RE_MOVIE_ID       =  Regex("movieId=(\d+)")
RE_TV_ID          =  Regex("tvProgramId=(\d+)")
RE_PHOTO_SIZE     =  Regex("/C\d+x\d+/")
RE_IMDB_ID        =  Regex("/(tt\d+)/")

JSON_MAX_SIZE     = 10 * 1024 * 1024

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
    u'제한상영가': {     # 어느 여름날 밤에 (2016)
        'KMRB': 'kr/X',
        'MPAA': 'NC-17'
    }
}

def Start():
  HTTP.CacheTime = CACHE_1HOUR * 12
  HTTP.Headers['Accept'] = 'text/html, application/json'

  if Prefs['http_proxy']:
    os.environ['http_proxy'] = Prefs['http_proxy'].strip()
  if Prefs['https_proxy']:
    os.environ['https_proxy'] = Prefs['https_proxy'].strip()

def downloadImage(url, fetchContent=True):
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
  if 'daumcdn.net' in url:
    url = urllib.unquote(Regex('fname=(.*)').search(url).group(1))

  if url.startswith('//'):
    url = ( 'http:', 'https:' )[Prefs['use_https_for_image']] + url

  return url

def levenshteinRatio(first, second):
  return 1 - (Util.LevenshteinDistance(first, second) / float(max(len(first), len(second))))

def containsHangul(text):
  # return any(ord(c) >= 44032 and ord(c) <= 55203 for c in text)
  for c in list(text):
    if ord(c) >= 44032 and ord(c) <= 55203:
      return True
  return False

####################################################################################################
def searchDaumMovie(results, media, lang):
  media_ids = []

  # 영화 검색 (메인)
  media_name = unicodedata.normalize('NFKC', unicode(media.name)).strip()
  media_words = media_name.split(' ') if containsHangul(media_name) else [ media_name ]
  while media_words:
    media_name = ' '.join(media_words)
    Log.Debug("search: %s %s" %(media_name, media.year))
    html = HTML.ElementFromURL(DAUM_MOVIE_SRCH % urllib.quote(media_name.encode('utf8')))
    movieEColl = html.xpath('//div[@id="movieEColl"]')
    if movieEColl:
      try:
        media_ids.append(Regex('movieId=(\d+)').search(movieEColl[0].xpath('.//div[@id="movieTitle"]/a/@href')[0]).group(1))
        # 영화검색 > 시리즈
        for a in movieEColl[0].xpath('.//div[contains(@class,"type_series")]//li/div[@class="wrap_cont"]/a'):
          media_ids.append(Regex('scckey=MV\|\|(\d+)').search(a.get('href')).group(1))
        # 영화검색 > 동명영화
        for a in movieEColl[0].xpath('.//div[@class="coll_etc"]//a'):
          media_ids.append(Regex('scckey=MV\|\|(\d+)').search(a.get('href')).group(1))
      except Exception as e: Log(str(e))
      break
    if containsHangul(media_words.pop()):
      break

  if not media_ids:
    # 영화 검색 (자동완성)
    media_name = unicodedata.normalize('NFKC', unicode(media.name)).strip()
    media_words = media_name.split(' ') if containsHangul(media_name) else [ media_name ]
    while media_words:
      media_name = ' '.join(media_words)
      Log.Debug("search: %s %s" %(media_name, media.year))
      data = JSON.ObjectFromURL(url=DAUM_MOVIE_SGST % (urllib.quote(media_name.encode('utf8'))), headers={'authorization': 'KakaoAK eef996dbcc900b7c164d80b6653565b3'})
      movies = data['items']['movie']
      if movies:
        media_ids = [ movie['item'].split('|')[1] for movie in movies]
        Log.Debug(media_ids)
        break
      if containsHangul(media_words.pop()):
        break

  if not media_ids:
    Log.Debug('No movie matches found')
    return

  for id in media_ids:
    data = JSON.ObjectFromURL(DAUM_MOVIE_DETAIL % id)
    title = data['movieCommon']['titleKorean']
    year = data['movieCommon']['productionYear']
    score = int(max(
      levenshteinRatio(media_name, title),
      levenshteinRatio(media_name, data['movieCommon']['titleEnglish'] or ''),
      levenshteinRatio(media_name, data['movieCommon']['titleOrigin'] or '')) * 80)
    if media.year and year:
      score += (2 - min(2, abs(int(media.year) - int(year)))) * 10
    Log.Debug('ID=%s, media_name=%s, title=%s, year=%s, score=%d' %(id, media_name, title, year, score))
    results.Append(MetadataSearchResult(id=id, name=title, year=year, score=score, lang=lang))

def searchDaumTV(results, media, lang):
  media_name = unicodedata.normalize('NFKC', unicode(media.show)).strip()
  media_year = media.year
  Log.Debug("search: %s %s" %(media_name, media_year))

  # TV검색
  html = HTML.ElementFromURL(DAUM_TV_SRCH % urllib.quote(media_name.encode('utf8')))
  try:
    tvp = html.xpath('//div[@id="tvpColl"]')[0]
  except:
    Log.Debug('No TV matches found')
    return

  items = []
  
  # 메인 검색 결과 추출
  try:
    tit_links = tvp.xpath('.//div[@class="area_tit"]//a/@href')
    if tit_links:
      title_href = tit_links[0]
      title = Regex('[?&]q=([^&]*)').search(title_href).group(1)
      id_match = Regex('[?&]spId=(\d+)').search(title_href) or Regex('[?&]irk=(\d+)').search(title_href)
      id = id_match.group(1)
      title = urllib.unquote(title)
      
      year = None
      try:
        texts = tvp.xpath('.//div[@class="sub_header"]//span[@class="txt-split"]')
        for text in texts:
          year_match = Regex('(\d{2,4})\.\d+\.\d+\.\s*~').search(text.text)
          if year_match:
            y = year_match.group(1)
            year = '20' + y if len(y) == 2 else y
            break
      except: pass
      items.append({ 'id': id, 'title': title, 'year': year })
  except Exception as e:
    Log.Debug('Error extracting base match: %s' % e)

  # TV검색 > 시리즈
  more_a = tvp.xpath('.//a[text()="시리즈"]')
  if more_a:
    try:
      series_html = HTML.ElementFromURL('https://search.daum.net/search%s' % more_a[0].get('href'))
      season_item = series_html.xpath('.//div[@class="pdt2"]//li')
      for li in season_item:
        try:
          links = li.xpath('.//a')
          a = links[1] if len(links) >= 2 else links[0]
          href = a.get('href')
          id_match = Regex('[?&]spId=(\d+)').search(href) or Regex('[?&]irk=(\d+)').search(href)
          id = id_match.group(1)
          title = a.text
          year = None
          try:
            spans = li.xpath('.//span')
            if spans:
              year = Regex('(\d{4})\.\d+').search(spans[0].text).group(1)
          except: pass
          items.append({ 'id': id, 'title': title, 'year': year })
        except: pass
    except Exception as e:
      Log.Debug('Error in series match: %s' % e)
  else:
    lis = tvp.xpath('//div[@id="tv_series"]//li')
    for li in lis:
      try:
        a_list = li.xpath('./a')
        if not a_list: continue
        a = a_list[0]
        href = a.get('href')
        id_match = Regex('[?&]irk=(\d+)').search(href) or Regex('[?&]spId=(\d+)').search(href)
        id = id_match.group(1)
        title = a.text
        year = None
        try:
          spans = li.xpath('./span')
          if spans:
            year = Regex('(\d{4})\.\d+').search(spans[0].text).group(1)
        except: pass
        items.append({ 'id': id, 'title': title, 'year': year })
      except: pass

  # TV검색 > 동명 콘텐츠
  dm_items = tvp.xpath('.//div[contains(@class,"cont_pannel")]//strong[text()="동명프로그램"]/following-sibling::div[1]//div[@class="c-item-content"]')
  if not dm_items:
    dm_items = tvp.xpath('//div[@data-tab="tab1"]//div[@class="c-item-content"]')

  for item in dm_items:
    try:
      links = item.xpath('.//a')
      target_a = None
      for a in links:
        href = a.get('href') or ""
        if 'spId=' in href or 'irk=' in href:
          target_a = a
          break
      if not target_a: continue
      
      href = target_a.get('href')
      id_match = Regex('[?&]spId=(\d+)').search(href) or Regex('[?&]irk=(\d+)').search(href)
      id = id_match.group(1)
      title = target_a.text.strip() if target_a.text else ""
      if not title:
        for a in links:
          if a.text and a.text.strip():
            title = a.text.strip()
            break
      
      year = None
      try:
        program_texts = item.xpath('.//dd[contains(@class, "program")]/text()')
        for txt in program_texts:
          year_match = Regex('(\d{4})').search(txt)
          if year_match:
            year = year_match.group(1)
            break
      except: pass
      
      items.append({ 'id': id, 'title': title, 'year': year })
    except: pass

  id_hist = []
  for item in items:
    if item['id'] not in id_hist:
      score = int(levenshteinRatio(media_name, item['title']) * 90)
      if media_year and item['year']:
        score += (2 - min(2, abs(int(media_year) - int(item['year'])))) * 5
      Log.Debug('ID=%s, media_name=%s, title=%s, year=%s, score=%d' %(item['id'], media_name, item['title'], item['year'], score))
      results.Append(MetadataSearchResult(id=item['id'], name=item['title'], year=item['year'], score=score, lang=lang))
      id_hist.append(item['id'])

def updateDaumMovie(metadata):
  # (1) from detail page
  poster_url = None

  try:
    data = JSON.ObjectFromURL(DAUM_MOVIE_DETAIL % metadata.id)
    metadata.title = data['movieCommon']['titleKorean']
    metadata.title_sort = unicodedata.normalize('NFKD' if Prefs['use_title_decomposition'] else 'NFKC', metadata.title)
    try: metadata.rating = float(data['movieCommon']['avgRating'])
    except: metadata.rating = None
    metadata.genres.clear()
    for genre in data['movieCommon']['genres']:
      metadata.genres.add(genre)
    metadata.countries.clear()
    for country in data['movieCommon']['productionCountries']:
      metadata.countries.add(country)
    metadata.summary = String.DecodeHTMLEntities(String.StripTags(data['movieCommon']['plot'])).strip()
    if data['movieCommon']['mainPhoto']:
      poster_url = data['movieCommon']['mainPhoto']['imageUrl']

    # Log.Debug('genre=%s, country=%s' %(','.join(g for g in metadata.genres), ','.join(c for c in metadata.countries)))
    # Log.Debug('oaa=%s, duration=%s, content_rating=%s' %(metadata.originally_available_at, metadata.duration, metadata.content_rating))

    productionCountries = [ '한국' ]
    productionCountries.append(data['movieCommon']['productionCountries'])
    for pc in productionCountries:
      try:
        cmi = (x for x in data['movieCommon']['countryMovieInformation'] if x['country']['nameKorean'] == pc).next()
        if cmi['releaseDate'] and cmi['admissionCode']:
          metadata.originally_available_at = Datetime.ParseDate(cmi['releaseDate']).date()
          metadata.duration = cmi['duration'] * 60 * 1000
          if cmi['country']['id'] == 'KR' and cmi['admissionCode'] in DAUM_CR_TO_MPAA_CR:
            metadata.content_rating = DAUM_CR_TO_MPAA_CR[cmi['admissionCode']]['MPAA' if Prefs['use_mpaa'] else 'KMRB']
          else:
            metadata.content_rating = cmi['country']['id'].lower() + '/' + cmi['admissionCode']
          break
      except StopIteration: pass

  except Exception as e:
    Log.Debug(repr(e))
    pass

  # (2) cast crew
  directors = list()
  producers = list()
  writers = list()
  roles = list()

  try:
    data = JSON.ObjectFromURL(DAUM_MOVIE_CAST % metadata.id)
    for a in data['casts']:
      cast = dict()
      cast['name'] = a['nameKorean']
      if a['profileImage']:
        cast['photo'] = a['profileImage']
      role = a['movieJob']['role']
      if role == '감독':
        directors.append(cast)
      else:   # 주연, 출연
        cast['role'] = a['description'].strip() if a.get('description') else role
        roles.append(cast)

    for a in data['staff']:
      staff = dict()
      staff['name'] = a['nameKorean']
      if a['profileImage']:
        staff['photo'] = a['profileImage']
      role = a['movieJob']['role']
      if role in [ '제작', '기획' ]:
        producers.append(staff)
      elif role in [ '각본', '원작' ]:
        writers.append(staff)

    if data['companies']:
      metadata.studio = data['companies'][0]['nameKorean'] or data['companies'][0]['nameEnglish']

  except Exception as e:
    Log.Debug(repr(e))
    pass

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

  # # (3) from photo page
  data = JSON.ObjectFromURL(DAUM_MOVIE_PHOTO % metadata.id)
  max_poster = int(Prefs['max_num_posters'])
  max_art = int(Prefs['max_num_arts'])
  idx_poster = 0
  idx_art = 0
  for item in data['contents']:
    if item['movieCategory'] == '스틸' and idx_art < max_art:
      idx_art += 1
      art_url = item['imageUrl']
      if art_url not in metadata.art:
        try:
          metadata.art[art_url] = Proxy.Preview(downloadImage(art_url), sort_order = idx_art)
        except Exception as e: Log(str(e))
    if item['movieCategory'] == '포스터' and idx_poster < max_poster:
      idx_poster += 1
      poster_url = item['imageUrl']
      if poster_url not in metadata.posters:
        try:
          metadata.posters[poster_url] = Proxy.Preview(downloadImage(poster_url), sort_order = idx_poster)
        except Exception as e: Log(str(e))

  if len(metadata.posters) == 0:
    if poster_url:
      try:
        metadata.posters[poster_url] = Proxy.Preview(downloadImage(poster_url), sort_order = 100)
      except Exception as e: Log(str(e))

  Log.Debug('Total %d posters, %d artworks' %(len(metadata.posters), len(metadata.art)))

def updateDaumTV(metadata, media):
  # TV 상세 정보 로드
  html = HTML.ElementFromURL(DAUM_TV_DETAIL % ('tv', urllib.quote(media.title.encode('utf8')), metadata.id))
  try:
    tvp = html.xpath('//div[@id="tvpColl"]')[0]
  except:
    Log.Debug('No TV matches found')
    return

  # TV 쇼 기본 정보 설정
  try:
    Log.Debug("TV Update: %s" %(media.title))
    metadata.title = media.title
    metadata.title_sort = unicodedata.normalize('NFKD' if Prefs['use_title_decomposition'] else 'NFKC', metadata.title)
    metadata.original_title = ''
    metadata.rating = None
    metadata.genres.clear()
    
    # 줄거리 추출
    try:
      summary_nodes = html.xpath(u'//strong[.="줄거리"]/following-sibling::p/text()')
      if summary_nodes:
        metadata.summary = String.DecodeHTMLEntities(String.StripTags(summary_nodes[0]).strip())
    except: pass

    # 제작사 추출
    try:
      studio_nodes = html.xpath('//dd[@class="program"]//a/text()')
      if studio_nodes:
        metadata.studio = studio_nodes[0]
    except: pass

    # 포스터 추출
    try:
      poster_imgs = tvp.xpath('.//div[@class="wrap_thumb"]//img')
      if poster_imgs:
        poster_url = originalImageUrlFromCdnUrl(poster_imgs[0].get('data-original-src'))
        if poster_url not in metadata.posters:
          metadata.posters[poster_url] = Proxy.Preview(HTTP.Request(poster_url, cacheTime=0), sort_order = len(metadata.posters) + 1)
    except: pass
  except Exception as e:
    Log.Debug('Error updating TV base info: %s' % e)

  # 출연진 및 제작진 정보
  directors = []
  producers = []
  writers = []
  try:
    cast_links = tvp.xpath(u'.//a[.="출연"]')
    if cast_links:
      cast_html = HTML.ElementFromURL('https://search.daum.net/search%s' % cast_links[0].get('href'))
      
      roles = []
      # 제작진 (감독, 작가 등)
      for item in cast_html.xpath(u'//div[@class="pdt2" and @data-tab="제작"]/ul/li'):
        try:
          role_nodes = item.xpath('.//div[@class="item-contents"]/span/text()')
          if not role_nodes: continue
          role = role_nodes[0].strip().replace(u'이전 ', '')
          
          name_nodes = item.xpath('.//div[@class="item-title"]/span/text()')
          if not name_nodes: continue
          name = name_nodes[0]
          
          img_nodes = item.xpath('.//img/@data-original-src')
          photo = img_nodes[0] if img_nodes else None
          
          cast = {'name': name, 'photo': photo}
          if role in [u'감독', u'연출', u'조감독']: directors.append(cast)
          elif role in [u'제작', u'프로듀서', u'책임프로듀서', u'기획']: producers.append(cast)
          elif role in [u'극본', u'각본', u'원작', u'작가']: writers.append(cast)
        except: pass

      # 출연진
      for item in cast_html.xpath(u'//div[@class="pdt2" and @data-tab="출연"]/ul/li'):
        try:
          cast = {}
          cast['name'] = ''.join(item.xpath('.//div[@class="item-title"]//text()')).strip()
          cast['role'] = ''.join(item.xpath('.//div[@class="item-contents"]//text()')).strip()
          img_nodes = item.xpath('.//img/@data-original-src')
          if img_nodes:
            cast['photo'] = originalImageUrlFromCdnUrl(img_nodes[0])
          roles.append(cast)
        except: pass

      if roles:
        metadata.roles.clear()
        for r in roles:
          meta_role = metadata.roles.new()
          meta_role.name = r.get('name')
          meta_role.role = r.get('role')
          meta_role.photo = r.get('photo')
  except Exception as e:
    Log.Debug('Error updating cast info: %s' % e)

  # 시즌 정보 수집
  season_info = []
  try:
    more_links = tvp.xpath(u'.//a[.="시리즈"]')
    if more_links:
      Log.Debug("Series link found: %s" % more_links[0].get('href'))
      epi_html = HTML.ElementFromURL('https://search.daum.net/search%s' % more_links[0].get('href'))
      season_items = epi_html.xpath('.//div[@class="pdt2"]//li')
      for s_item in season_items:
        try:
          a_tags = s_item.xpath('.//a')
          a = a_tags[1] if len(a_tags) >= 2 else a_tags[0]
          s_id = Regex('spId=(\d+)').search(a.get('href')).group(1)
          s_title = a.text
          s_num_match = Regex('(\d+)\s*$').search(s_title)
          s_num = s_num_match.group(1) if s_num_match else '1'
          
          year = None
          span_nodes = s_item.xpath('.//span')
          if span_nodes:
            year_match = Regex('(\d{4})\.\d+').search(span_nodes[0].text)
            if year_match: year = year_match.group(1)
            
          season_info.append({
            'id': s_id, 'title': s_title, 'season': s_num, 'year': year,
            'href': 'https://search.daum.net/search%s' % a.get('href')
          })
        except: pass
    
    if not season_info:
      # 시리즈 정보가 없으면 현재 정보를 시즌 1로 간주
      year = None
      try:
        texts = tvp.xpath('.//div[@class="sub_header"]//span[@class="txt-split"]')
        for t in texts:
          y_match = Regex('(\d{2,4})\.\d+\.\d+\.\s*~').search(t.text)
          if y_match:
            y = y_match.group(1)
            year = '20' + y if len(y) == 2 else y
            break
      except: pass
      season_info.append({
        'id': metadata.id, 'title': media.title, 'season': '1', 'year': year,
        'href': DAUM_TV_DETAIL % ('tv', urllib.quote(media.title.encode('utf8')), metadata.id)
      })
  except Exception as e:
    Log.Debug('Error collecting season info: %s' % e)

  # 각 시즌 및 에피소드 정보 업데이트
  for season_num in media.seasons:
    for s_item in season_info:
      if s_item['season'] == season_num:
        try:
          Log.Debug("Updating Season: %s" % season_num)
          s_html = HTML.ElementFromURL(s_item['href'])
          
          # 시즌 포스터
          try:
            s_poster_imgs = s_html.xpath('//div[@id="tvpColl"]//div[@class="wrap_thumb"]//img')
            if s_poster_imgs:
              s_poster_url = originalImageUrlFromCdnUrl(s_poster_imgs[0].get('data-original-src'))
              if s_poster_url not in metadata.seasons[season_num].posters:
                metadata.seasons[season_num].posters[s_poster_url] = Proxy.Preview(HTTP.Request(s_poster_url, cacheTime=0), sort_order=len(metadata.seasons[season_num].posters) + 1)
          except: pass

          # 에피소드 리스트 (회차 선택기)
          episode_map = {}
          try:
            tab_links = s_html.xpath(u'.//a[.="회차"]')
            if tab_links:
              epi_list_html = HTML.ElementFromURL('https://search.daum.net/search%s' % tab_links[0].get('href'))
              options = epi_list_html.xpath('.//q-select//option')
              episode_map = {opt.get('value').replace('회', ''): opt.get('data-sp-id') for opt in options}
          except: pass

          # 각 에피소드 정보 업데이트
          for epi_num in media.seasons[season_num].episodes:
            if str(epi_num) not in episode_map: continue
            try:
              Log.Debug("Updating Episode: %s" % epi_num)
              epi_page = HTML.ElementFromURL(DAUM_TV_EPISODE % ('tv', urllib.quote(media.title.encode('utf8')) + urllib.quote(" " + str(epi_num) + "회"), episode_map[str(epi_num)]))
              episode = metadata.seasons[season_num].episodes[epi_num]
              
              # 에피소드 줄거리
              summary_nodes = epi_page.xpath('.//p[@class="desc_story"]/text()')
              if summary_nodes: episode.summary = summary_nodes[0].strip()
              
              # 에피소드 제목
              tit_nodes = epi_page.xpath('.//strong[@class="tit_story"]')
              if tit_nodes and tit_nodes[0].text: episode.title = tit_nodes[0].text.strip()
              
              # 에피소드 썸네일
              thumb_nodes = epi_page.xpath('.//div[@class="player_sch"]//img/@data-original-src')
              if thumb_nodes:
                t_url = originalImageUrlFromCdnUrl(thumb_nodes[0])
                if t_url not in episode.thumbs:
                  episode.thumbs[t_url] = Proxy.Preview(HTTP.Request(t_url, cacheTime=0), sort_order=len(episode.thumbs) + 1)
              
              # 방영일
              try:
                date_nodes = epi_page.xpath(u'.//span[.="방영일"]/../text()')
                if date_nodes:
                  date_str = date_nodes[0].strip().rsplit('.', 1)[0]
                  episode.originally_available_at = Datetime.ParseDate(date_str, '%Y.%m.%d').date()
              except: pass

              # 감독 및 작가 설정 (TV 쇼 정보 활용)
              if directors:
                episode.directors.clear()
                for d in directors:
                  meta_d = episode.directors.new()
                  meta_d.name = d.get('name'); meta_d.photo = d.get('photo')
              if writers:
                episode.writers.clear()
                for w in writers:
                  meta_w = episode.writers.new()
                  meta_w.name = w.get('name'); meta_w.photo = w.get('photo')
            except Exception as e:
              Log.Debug('Error updating episode %s: %s' % (epi_num, e))
        except Exception as e:
          Log.Debug('Error updating season %s: %s' % (season_num, e))

  return
  # (1) from detail page
  try:

    season_search = False
    for season in media.seasons:
      if season != '1':
        season_search = True

    # if any([season != '1' for season in media.seasons]):
      

    #Series Search
    if season_search: 
      Log.Debug("Season search: %s" %(media.title))

      # TV검색
      html = HTML.ElementFromURL(DAUM_TV_SRCH % urllib.quote(media.title.encode('utf8')))
      try:
        tvp = html.xpath('//div[@id="tvpColl"]')[0]
      except:
        Log.Debug('No TV matches found')
        return

      season_items = []
      #title, id = Regex('q=(.*?)&irk=(\d+)').search(tvp.xpath('//a[@class="tit_info"]/@href')[-1]).group(1, 2)
      title = Regex('&q=([^&]*)').search(tvp.xpath('//div[@class="area_tit"]//a/@href')[0]).group(1)
      id = Regex('&spId=(\d+)').search(tvp.xpath('//div[@class="area_tit"]//a/@href')[0]).group(1)
      title = urllib.unquote(title)
      try:
        texts = tvp.xpath('//div[@class="sub_header"]//span[@class="txt-split"]')
        for text in texts:
          year = Regex('(\d{2})\.\d+\.\d+\.\s*~').search(text.text)
          if year is not None:
            year = '20'+year.group(1)
            break
        #year = Regex('(\d{4})\.\d+\.\d+~').search(tvp.xpath('//div[@class="head_cont"]//span[@class="txt_summary"][last()]')[0].text).group(1)
      except: year = None
      season_items.append({ 'id': id, 'title': title, 'year': year })

      # TV검색 > 시리즈
      more_a = tvp.xpath(u'.//a[.="시리즈"]')
      if more_a:
        html = HTML.ElementFromURL('https://search.daum.net/search%s' % more_a[0].get('href'))
        season_item = html.xpath('.//div[@class="pdt2"]//li')
        for season_item in season_item:
          a = season_item.xpath('.//a')[1]
          id = Regex('spId=(\d+)').search(a.get('href')).group(1)
          title = a.text
          try:
            #Log.Debug(li.xpath('.//span')[0].text)
            year = Regex('(\d{4})\.\d+').search(season_item.xpath('.//span')[0].text).group(1)
            items.append({ 'id': id, 'title': title, 'year': year })
          except: pass

    html = HTML.ElementFromURL(DAUM_TV_DETAIL % ('tv', urllib.quote(media.title.encode('utf8')), metadata.id))
    tvp = html.xpath('//div[@id="tvpColl"]')[0]
    #metadata.title = html.xpath('//div[@class="tit_program"]/strong')[0].text
    metadata.title = media.title
    metadata.title_sort = unicodedata.normalize('NFKD' if Prefs['use_title_decomposition'] else 'NFKC', metadata.title)
    metadata.original_title = ''
    metadata.rating = None
    metadata.genres.clear()
    # 드라마 (24부작)
    #metadata.genres.add(Regex(u'(.*?)(?:\u00A0(\(.*\)))?$').search(html.xpath(u'//dt[.="장르"]/following-sibling::dd/text()')[0]).group(1))

    #Summay 
    #Log.Debug(html.xpath(u'//strong[.="줄거리"]/following-sibling::p/text()'))
    metadata.summary = String.DecodeHTMLEntities(String.StripTags(html.xpath(u'//strong[.="줄거리"]/following-sibling::p/text()')[0]).strip())
    #Log.Debug(metadata.summary)
    #metadata.summary = String.DecodeHTMLEntities(String.StripTags(html.xpath(u'//dt[.="소개"]/following-sibling::dd')[0].text).strip())

    #Studio
    metadata.studio = html.xpath('//dd[@class="program"]//a/text()')[0]
    Log.Debug(metadata.studio)

    #Poster    
    poster_ele = tvp.xpath('.//div[@class="wrap_thumb"]//img')[0]
    poster_url = originalImageUrlFromCdnUrl(poster_ele.get('data-original-src'))
    #poster_url = originalImageUrlFromCdnUrl(html.xpath('//div[@class="info_cont"]/div[@class="wrap_thumb"]/a/img/@data-original-src')[0])
    if poster_url not in metadata.posters:
      metadata.posters[poster_url] = Proxy.Preview(HTTP.Request(poster_url, cacheTime=0), sort_order = len(metadata.posters) + 1)
  except Exception as e:
    Log.Debug(repr(e))
    pass

  # (2) cast crew
  cast_ele = tvp.xpath(u'.//a[.="출연"]')[0] 
  html = HTML.ElementFromURL('https://search.daum.net/search%s' % cast_ele.get('href'))
  
  directors = list()
  producers = list()
  writers = list()
  roles = list()

  for item in html.xpath(u'//div[@class="pdt2" and @data-tab="제작"]/ul/li'):
    try:
      role = item.xpath('.//div[@class="item-contents"]/span/text()')[0].strip().replace(u'이전 ', '')
      cast = dict()
      cast['name'] = item.xpath('.//div[@class="item-title"]/span/text()')[0]
      cast['photo'] = item.xpath('.//img/@data-original-src')[0]
      #Log.Debug(cast)
      #Log.Debug(role)
      if role in [u'감독', u'연출', u'조감독']:
        directors.append(cast)
      elif role in [u'제작', u'프로듀서', u'책임프로듀서', u'기획']:
        producers.append(cast)
      elif role in [u'극본', u'각본', u'원작', u'작가']:
        writers.append(cast)
      else:
        Log('Unknown role %s' % role)
    except: pass

  for item in html.xpath(u'//div[@class="pdt2" and @data-tab="출연"]/ul/li'):
    #Log.Debug(item)
    try:
      cast = dict()
      cast['name'] = ''.join(item.xpath('.//div[@class="item-title"]//text()')).strip()
      cast['role'] = ''.join(item.xpath('.//div[@class="item-contents"]//text()')).strip()
      cast['photo'] = originalImageUrlFromCdnUrl(item.xpath('.//img/@data-original-src')[0])
      roles.append(cast)
      #Log.Debug(cast)
    except: pass

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

  season_num='1'
  # (4) from episode page
  if not season_search:
    season_items = [{"id":metadata.id}]
  for season_item in season_items:
    if season_search:
      epi_html = HTML.ElementFromURL(DAUM_TV_DETAIL % ('tv', urllib.quote(media.title.encode('utf8')), season_item['id']))
      Log.Debug("Season epi_html load: %s" %(season_item['id']))
      match = Regex('(\d+)\s*$').search(season_item['title'])
      if match:
        season_num = str(match.group(1))
      else:
        season_num = '1'

      poster_ele = epi_html.xpath('//div[@id="tvpColl"]//div[@class="wrap_thumb"]//img')[0]
      poster_url = originalImageUrlFromCdnUrl(poster_ele.get('data-original-src'))
      if media is None or season_num in media.seasons:
        if poster_url not in metadata.seasons[season_num].posters:
          try: metadata.seasons[season_num].posters[poster_url] = Proxy.Preview(HTTP.Request(poster_url, cacheTime=0), sort_order = len(metadata.seasons[season_num].posters) + 1)
          except Exception, e: Log(str(e))
      Log.Debug("Season number search: %s %s" %(season_item['title'], season_num))
    else:
      epi_html = html
      season_num = '1'

    #Episode Info
      Log.Debug("Debug")
      Log.Debug(media.seasons[season_num].episodes)

      try:
        tab_ele = html.xpath(u'.//a[.="회차"]')[0] 
        html = HTML.ElementFromURL('https://search.daum.net/search%s' % tab_ele.get('href'))
        episode_list = html.xpath('.//q-select//option')
        episode_list = {ele.get('value').replace('회',''): ele.get('data-sp-id') for ele in episode_list}
      except:
        episode_list = {}
      #Log.Debug(episode_list)

      for episode_num in media.seasons[season_num].episodes:
        try:
          #Log.Debug("Episode %s search"%episode_num)
          page = HTML.ElementFromURL(DAUM_TV_EPISODE % ('tv', urllib.quote(media.title.encode('utf8'))+urllib.quote(" "+str(episode_num)+"회"), episode_list[str(episode_num)]))
          episode = metadata.seasons[season_num].episodes[episode_num]
          episode.summary = page.xpath('.//p[@class="desc_story"]/text()')[0].strip()
          #Log.Debug(episode.summary)
          tit_ele = page.xpath('.//strong[@class="tit_story"]')
          if tit_ele:
            episode.title = tit_ele[0].text.strip()
          episode.rating = None
          thumbs_url = page.xpath('.//div[@class="player_sch"]//img/@data-original-src')
          thumbs_url = originalImageUrlFromCdnUrl(thumbs_url[0]) if len(thumbs_url) > 0 else None
          if thumbs_url is not None and thumbs_url not in episode.thumbs:
            try: episode.thumbs[thumbs_url] = Proxy.Preview(HTTP.Request(thumbs_url, cacheTime=0), sort_order = len(episode.thumbs) + 1)
            except Exception, e: Log(str(e))

          episode_date = page.xpath(u'.//span[.="방영일"]/../text()')[0].strip()
          episode_date = episode_date.rsplit('.', 1)[0]
          episode_date = Datetime.ParseDate(episode_date, '%Y.%m.%d').date()
          episode.originally_available_at = episode_date 

          if directors:
            episode.directors.clear()
            for director in directors:
              meta_director = episode.directors.new()
              if 'name' in director:
                meta_director.name = director['name']
              if 'photo' in director:
                meta_director.photo = director['photo']
          if writers:
            episode.writers.clear()
            for writer in writers:
              meta_writer = episode.writers.new()
              if 'name' in writer:
                meta_writer.name = writer['name']
              if 'photo' in writer:
                meta_writer.photo = writer['photo']
        except Exception, e: Log(str(e))
  


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
        page = HTTP.Request( url ).content
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
        xml = XML.ElementFromURL( url )
        node = xml.xpath('/Data/Series/seriesid')
        if node:
          metadata.id = node[0].text
          Log.Info("override with TVDB ID, %s" % metadata.id)
