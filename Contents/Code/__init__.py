# -*- coding: utf-8 -*-
# Daum Movie

import urllib, unicodedata, os

DAUM_MOVIE_SRCH   = "https://search.daum.net/search?w=tot&q=%s&rtmaxcoll=EM1"
DAUM_MOVIE_SGST   = "https://dapi.kakao.com/suggest-hub/v1/search.json?service=movie-v2&cate=movie&multiple=1&q=%s"

DAUM_MOVIE_DETAIL = "https://movie.daum.net/api/movie/%s/main"
DAUM_MOVIE_CAST   = "https://movie.daum.net/api/movie/%s/crew"
DAUM_MOVIE_PHOTO  = "https://movie.daum.net/api/movie/%s/photoList?page=1&size=100"

DAUM_TV_SRCH      = "https://search.daum.net/search?w=tot&q=%s&rtmaxcoll=TVP"
DAUM_TV_DETAIL    = "https://search.daum.net/search?w=%s&q=%s&irk=%s&irt=tv-program&DA=TVP"

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
  # if not media_year and media.filename:
  #   match = Regex('\D(\d{2})[01]\d[0-3]\d\D').search(os.path.basename(urllib.unquote(media.filename)))
  #   if match:
  #     media_year = '20' + match.group(1)
  Log.Debug("search: %s %s" %(media_name, media_year))

  # TV검색
  html = HTML.ElementFromURL(DAUM_TV_SRCH % urllib.quote(media_name.encode('utf8')))
  try:
    tvp = html.xpath('//div[@id="tvpColl"]')[0]
  except:
    Log.Debug('No TV matches found')
    return

  items = []
  title, id = Regex('q=(.*?)&irk=(\d+)').search(tvp.xpath('//a[@class="tit_info"]/@href')[-1]).group(1, 2)
  title = urllib.unquote(title)
  try:
    year = Regex('(\d{4})\.\d+\.\d+~').search(tvp.xpath('//div[@class="head_cont"]//span[@class="txt_summary"][last()]')[0].text).group(1)
  except: year = None
  items.append({ 'id': id, 'title': title, 'year': year })

  # TV검색 > 시리즈
  more_a = tvp.xpath(u'//a[span[.="시리즈 더보기"]]')
  if more_a:
    html = HTML.ElementFromURL('https://search.daum.net/search%s' % more_a[0].get('href'))
    for li in html.xpath('//div[@id="series"]//li'):
      a = li.xpath('.//a')[1]
      id = Regex('irk=(\d+)').search(a.get('href')).group(1)
      title = a.text
      try:
        year = Regex('(\d{4})\.\d+').search(li.xpath('./span')[0].text).group(1)
        items.append({ 'id': id, 'title': title, 'year': year })
      except: pass
  else:
    lis = tvp.xpath('//div[@id="tv_series"]//li')
    for li in lis:
      id = Regex('irk=(\d+)').search(li.xpath('./a/@href')[0]).group(1)
      title = li.xpath('./a')[0].text
      try:
        year = Regex('(\d{4})\.\d+').search(li.xpath('./span')[0].text).group(1)
        items.append({ 'id': id, 'title': title, 'year': year })
      except: pass

  # TV검색 > 동명 콘텐츠
  spans = tvp.xpath(u'//div[contains(@class,"coll_etc")]//span[.="(동명프로그램)"]')
  for span in spans:
    try:
      year = Regex('(\d{4})').search(span.xpath('./preceding-sibling::span[1]')[0].text).group(1)
    except: year = None
    a = span.xpath('./preceding-sibling::a[1]')[0]
    id = Regex('irk=(\d+)').search(a.get('href')).group(1)
    title = a.text.strip()
    items.append({ 'id': id, 'title': title, 'year': year })

  for idx, item in enumerate(items):
    score = int(levenshteinRatio(media_name, item['title']) * 90)
    if media_year and item['year']:
      score += (2 - min(2, abs(int(media_year) - int(item['year'])))) * 5
    Log.Debug('ID=%s, media_name=%s, title=%s, year=%s, score=%d' %(item['id'], media_name, item['title'], item['year'], score))
    results.Append(MetadataSearchResult(id=item['id'], name=item['title'], year=item['year'], score=score, lang=lang))

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
      title, id = Regex('q=(.*?)&irk=(\d+)').search(tvp.xpath('//a[@class="tit_info"]/@href')[-1]).group(1, 2)
      title = urllib.unquote(title)
      try:
        year = Regex('(\d{4})\.\d+\.\d+~').search(tvp.xpath('//div[@class="head_cont"]//span[@class="txt_summary"][last()]')[0].text).group(1)
      except: year = None
      season_items.append({ 'id': id, 'title': title, 'year': year })

      # TV검색 > 시리즈
      more_a = tvp.xpath(u'//a[span[.="시리즈 더보기"]]')
      if more_a:
        html = HTML.ElementFromURL('https://search.daum.net/search%s' % more_a[0].get('href'))
        for li in html.xpath('//div[@id="series"]//li'):
          a = li.xpath('.//a')[1]
          id = Regex('irk=(\d+)').search(a.get('href')).group(1)
          title = a.text
          try:
            year = Regex('(\d{4})\.\d+').search(li.xpath('./span')[0].text).group(1)
            season_items.append({ 'id': id, 'title': title, 'year': year })
          except: pass
      else:
        lis = tvp.xpath('//div[@id="tv_series"]//li')
        for li in lis:
          id = Regex('irk=(\d+)').search(li.xpath('./a/@href')[0]).group(1)
          title = li.xpath('./a')[0].text
          try:
            year = Regex('(\d{4})\.\d+').search(li.xpath('./span')[0].text).group(1)
            season_items.append({ 'id': id, 'title': title, 'year': year })
          except: pass

    html = HTML.ElementFromURL(DAUM_TV_DETAIL % ('tv', urllib.quote(media.title.encode('utf8')), metadata.id))
    #metadata.title = html.xpath('//div[@class="tit_program"]/strong')[0].text
    metadata.title = media.title
    metadata.title_sort = unicodedata.normalize('NFKD' if Prefs['use_title_decomposition'] else 'NFKC', metadata.title)
    metadata.original_title = ''
    metadata.rating = None
    metadata.genres.clear()
    # 드라마 (24부작)
    metadata.genres.add(Regex(u'(.*?)(?:\u00A0(\(.*\)))?$').search(html.xpath(u'//dt[.="장르"]/following-sibling::dd/text()')[0]).group(1))
    spans = html.xpath('//div[@class="txt_summary"]/span')
    if not spans:
      tot = HTML.ElementFromURL(DAUM_TV_DETAIL % ('tot', urllib.quote(media.title.encode('utf8')), metadata.id))
      spans = tot.xpath('//div[@class="summary_info"]/*[@class="txt_summary"]')
    if spans:
      metadata.studio = spans[0].text
      match = Regex('(\d+\.\d+\.\d+)~(\d+\.\d+\.\d+)?').search(spans[-1].text or '')
      if match:
        metadata.originally_available_at = Datetime.ParseDate(match.group(1)).date()
    metadata.summary = String.DecodeHTMLEntities(String.StripTags(html.xpath(u'//dt[.="소개"]/following-sibling::dd')[0].text).strip())

    # //search1.kakaocdn.net/thumb/C232x336.q85/?fname=http%3A%2F%2Ft1.daumcdn.net%2Fcontentshub%2Fsdb%2Ff63c5467710f5669caac131943855dfea31011003e57e674832fe8b16b946aa8
    # poster_url = urlparse.parse_qs(urlparse.urlparse(html.xpath('//div[@class="info_cont"]/div[@class="wrap_thumb"]/a/img/@src')[0]).query)['fname'][0]
    # poster_url = urllib.unquote(Regex('fname=(.*)').search(html.xpath('//div[@class="info_cont"]/div[@class="wrap_thumb"]/a/img/@src')[0]).group(1))
    poster_url = originalImageUrlFromCdnUrl(html.xpath('//div[@class="info_cont"]/div[@class="wrap_thumb"]/a/img/@src')[0])
    if poster_url not in metadata.posters:
      metadata.posters[poster_url] = Proxy.Preview(HTTP.Request(poster_url, cacheTime=0), sort_order = len(metadata.posters) + 1)
  except Exception as e:
    Log.Debug(repr(e))
    pass

  # (2) cast crew
  directors = list()
  producers = list()
  writers = list()
  roles = list()

  for item in html.xpath('//div[@class="wrap_col lst"]/ul/li'):
    try:
      role = item.xpath('./span[@class="sub_name"]/text()')[0].strip().replace(u'이전 ', '')
      cast = dict()
      cast['name'] = item.xpath('./span[@class="txt_name"]/a/text()')[0]
      cast['photo'] = item.xpath('./div/a/img/@src')[0]
      if role in [u'감독', u'연출', u'조감독']:
        directors.append(cast)
      elif role in [u'제작', u'프로듀서', u'책임프로듀서', u'기획']:
        producers.append(cast)
      elif role in [u'극본', u'각본', u'원작']:
        writers.append(cast)
      else:
        Log('Unknown role %s' % role)
    except: pass

  for item in html.xpath('//div[@class="wrap_col castingList"]/ul/li'):
    try:
      cast = dict()
      a = item.xpath('./span[@class="sub_name"]/a')
      if a:
        cast['name'] = a[0].text
        cast['role'] = item.xpath('./span[@class="txt_name"]/a')[0].text
        cast['photo'] = originalImageUrlFromCdnUrl(item.xpath('./div/a/img/@src')[0])
      else:
        cast['name'] = item.xpath('./span[@class="txt_name"]/a')[0].text
        cast['role'] = item.xpath('./span[@class="sub_name"]')[0].text.strip()
        cast['photo'] = originalImageUrlFromCdnUrl(item.xpath('./div/a/img/@src')[0])
      roles.append(cast)
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

  # (4) from episode page
  if not season_search:
    season_items = [{"id":"No search"}]
  for season_item in season_items:
    if season_search:
      epi_html = HTML.ElementFromURL(DAUM_TV_DETAIL % ('tv', urllib.quote(media.title.encode('utf8')), season_item['id']))
      Log.Debug("Season epi_html load: %s" %(season_item['id']))
      match = Regex('(\d+)\s*$').search(season_item['title'])
      if match:
        season_num = str(match.group(1))
      else:
        season_num = '1'

      poster_url = originalImageUrlFromCdnUrl(epi_html.xpath('//div[@class="info_cont"]/div[@class="wrap_thumb"]/a/img/@src')[0])
      if media is None or season_num in media.seasons:
        if poster_url not in metadata.seasons[season_num].posters:
          try: metadata.seasons[season_num].posters[poster_url] = Proxy.Preview(HTTP.Request(poster_url, cacheTime=0), sort_order = len(metadata.seasons[season_num].posters) + 1)
          except Exception, e: Log(str(e))
      Log.Debug("Season number search: %s %s" %(season_item['title'], season_num))
    else:
      epi_html = html
      season_num = '1'
    
    for a in epi_html.xpath('//ul[@id="clipDateList"]/li/a'):
      episode_num = a.xpath(u'substring-before(./span[@class="txt_episode"],"회")')
      try:
        episode_date = Datetime.ParseDate(a.xpath('./parent::li/@data-clip')[0], '%Y%m%d').date()
      except: continue
      if not episode_num: continue    # 시청지도서
      date_based_season_num = episode_date.year
      date_based_episode_num = episode_date.strftime('%Y-%m-%d')
      if ((season_num in media.seasons and episode_num in media.seasons[season_num].episodes) or
          (date_based_season_num in media.seasons and date_based_episode_num in media.seasons[date_based_season_num].episodes)):
        # Log.Debug("Hit: %s %s %s" %(season_item['title'], season_num, episode_num))
        page = HTML.ElementFromURL('https://search.daum.net/search' + a.get('href'))
        episode = metadata.seasons[season_num].episodes[episode_num]
        subtitle = page.xpath('//p[@class="episode_desc"]/strong/text()')
        episode.summary = '\n'.join(txt.strip() for txt in page.xpath('//p[@class="episode_desc"]/text()')).strip()
        episode.originally_available_at = episode_date
        epinum_subtitle = "제 %s화"%episode_num
        episode.title = subtitle[0] if subtitle else epinum_subtitle
        episode.rating = None
        thumbs_url = page.xpath('//div[@class="wrap_player"]/div[@class="wrap_thumb"]/a/img/@src')
        thumbs_url = originalImageUrlFromCdnUrl(thumbs_url[0]) if len(thumbs_url) > 0 else None
        if thumbs_url is not None and thumbs_url not in episode.thumbs:
          try: episode.thumbs[thumbs_url] = Proxy.Preview(HTTP.Request(thumbs_url, cacheTime=0), sort_order = len(episode.thumbs) + 1)
          except Exception, e: Log(str(e))

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

  # TV검색 > TV정보 > 공식홈
  home = html.xpath(u'//a[span[contains(.,"공식홈")]]/@href')
  if home:
    if 'www.imbc.com' in home[0]:
      page = HTML.ElementFromURL(home[0])
      for prv in page.xpath('//div[@class="roll-ban-event"]/ul/li/img/@src'):
        if prv not in metadata.art:
          try: metadata.art[prv] = Proxy.Preview(HTTP.Request(prv, cacheTime=0), sort_order = len(metadata.art) + 1)
          except Exception as e: Log(str(e))

  # TV검색 > TV정보 > 다시보기
  vod = html.xpath(u'//a[span[contains(.,"다시보기")]]/@href')
  if vod:
    replay_url = vod[0]
  else:
    if home and 'program.kbs.co.kr' in home[0]:
      # 카카오VOD > http://program.kbs.co.kr/2tv/drama/dramaspecial2018/pc/list.html?smenu=c2cc5a
      replay_url = home[0] + 'list.html?smenu=c2cc5a'
    else:
      replay_url = None
      if metadata.studio and Regex('MBC|SBS|KBS|EBS').match(metadata.studio):
        Log.Debug('No replay URL for [%s] %s' % (metadata.studio, metadata.title))

  if replay_url:
    if 'www.imbc.com' in replay_url:
      try:
        prog_codes = []
        # http://www.imbc.com/broad/tv/ent/challenge/vod/index.html
        page = HTML.ElementFromURL(replay_url)
        prog_codes.append(Regex('var progCode = "(.*?)";').search(page.xpath('//script[contains(.,"var progCode = ")]/text()')[0]).group(1))
        # for season_vod in page.xpath('//map[@name="vod"]/area/@href'):
        #   # http://www.imbc.com/broad/tv/ent/challenge/vod1/
        #   # http://www.imbc.com/broad/tv/ent/challenge/vod2/
        #   page = HTML.ElementFromURL(season_vod)
        #   prog_codes.append(Regex('var progCode = "(.*?)";').search(page.xpath('//script[contains(.,"var progCode = ")]/text()')[0]).group(1))
        for prog_code in prog_codes:
          page = HTTP.Request('http://vodmall.imbc.com/util/wwwUtil_sbox.aspx?kind=image&progCode=%s' % prog_code).content
          years = Regex("<option value='(\d+)'>").findall(page)
          for year in years:
            page = unicode(HTTP.Request('http://vodmall.imbc.com/util/wwwUtil_sbox_contents.aspx?progCode=%s&yyyy=%s&callback=jQuery1123011760857070017172_1538059867383&_=1538059867389'
                % (prog_code, year)).content, 'euc-kr')
            bcasts = JSON.ObjectFromString(Regex('jQuery1123011760857070017172_1538059867383\((.*)\)$').search(page).group(1))
            for bcast in bcasts:
              # if u'특집' in bcast['ContentNumber'] or u'스페셜' in bcast['ContentNumber']:   # 특집05회, 특집회, 추석특집회, 스페셜회
              #   # Log('ignoring %s' % bcast['ContentNumber'])
              #   continue
              season_num = '1'
              episode_date = Datetime.ParseDate(bcast['BroadDate'], '%Y-%m-%d').date()
              match = Regex(u'^(\d+(-\d+)?)회$').search(bcast['ContentNumber'])  # 7-8회, 1회
              if match:
                for episode_num in match.group(1).split('-'):
                  date_based_season_num = episode_date.year
                  date_based_episode_num = episode_date.strftime('%Y-%m-%d')
                  if ((season_num in media.seasons and episode_num in media.seasons[season_num].episodes) or
                      (date_based_season_num in media.seasons and date_based_episode_num in media.seasons[date_based_season_num].episodes)):
                    episode = metadata.seasons[season_num].episodes[episode_num]
                    if episode.summary and u'회차정보가 없습니다' not in episode.summary:
                      continue
                    page = unicode(HTTP.Request('http://vodmall.imbc.com/util/wwwUtil_json.aspx?kind=image&progCode=%s&callback=jQuery111104041909438012061_1538031601249&_=1538031601252'
                        % bcast['BroadCastID']).content, 'euc-kr')
                    info = JSON.ObjectFromString(Regex('jQuery111104041909438012061_1538031601249\((.*)\)$').search(page).group(1))[0]
                    episode.summary = info['Content'].replace('\r\n', '\n').replace('<br><br>', '\n').replace('<br>', '').strip()
                    episode.originally_available_at = episode_date
                    episode.title = info['Title']
                    episode.rating = None
      except Exception as e:
        Log.Debug(repr(e))
        pass

    elif 'programs.sbs.co.kr' in replay_url:
      try:
        # http://programs.sbs.co.kr/enter/jungle/vods/50479
        programcd, mnuid = Regex('programs\.sbs\.co\.kr/(.+?)/(.+?)/vods/(.+)$').search(replay_url).group(2, 3)

        # http://static.apis.sbs.co.kr/program-api/1.0/menu/jungle
        menu = JSON.ObjectFromURL('http://static.apis.sbs.co.kr/program-api/1.0/menu/%s' % programcd)

        shareimg = menu['program']['shareimg'].replace('_w640_h360', '_ori')
        if shareimg.startswith('//'):
          shareimg = 'http:' + shareimg
        if shareimg not in metadata.art:
          try: metadata.art[shareimg] = Proxy.Preview(HTTP.Request(shareimg, cacheTime=0), sort_order = len(metadata.art) + 1)
          except Exception as e: Log(str(e))

        # http://static.apis.sbs.co.kr/play-api/1.0/sbs_vodalls?...
        vods = JSON.ObjectFromURL('http://static.apis.sbs.co.kr/play-api/1.0/sbs_vodalls?offset=%d&limit=%d&sort=new&search=&cliptype=&subcategory=&programid=%s&absolute_show=Y&mdadiv=01&viewcount=Y' %
            ( 0, 2000, menu['program']['channelid'] + '_V' + menu['program']['programid'][-10:] ), max_size = JSON_MAX_SIZE)
        for v in vods['list']:
          # Log('%s %s-%s %s' % (v['broaddate'], v['content']['contentnumber'], v['content']['cornerid'], v['content']['contenttitle'] ))
          if v['content']['cornerid'] != 0: # 스페셜
            continue
          season_num = '1'
          episode_date = Datetime.ParseDate(v['broaddate'], '%Y-%m-%d').date()   # fix TZ
          episode_nums = []
          match = Regex(u'^\[(\d+)&(\d+)회차 통합본\]').search(v['synopsis'])
          if match:
            episode_nums.append(match.group(1))
            episode_nums.append(match.group(2))
          else:
            episode_nums.append(v['content']['contentnumber'])
          for episode_num in episode_nums:
            date_based_season_num = episode_date.year
            date_based_episode_num = episode_date.strftime('%Y-%m-%d')
            if ((season_num in media.seasons and episode_num in media.seasons[season_num].episodes) or
                (date_based_season_num in media.seasons and date_based_episode_num in media.seasons[date_based_season_num].episodes)):
              episode = metadata.seasons[season_num].episodes[episode_num]
              if episode.summary and u'회차정보가 없습니다' not in episode.summary:
                continue
              episode.summary = String.DecodeHTMLEntities(String.StripTags(v['synopsis'])).strip()
              episode.originally_available_at = episode_date
              episode.title = v['content']['contenttitle'].strip()
              episode.rating = None
      except Exception as e:
        Log.Debug(repr(e))
        pass

    elif 'program.kbs.co.kr' in replay_url:
      try:
        # http://program.kbs.co.kr/2tv/enter/gagcon/pc/list.html?smenu=c2cc5a
        source, sname, stype, smenu = Regex('program.kbs.co.kr/(.+?)/(.+?)/(.+?)/pc/list.html\?smenu=(.+)$').search(replay_url).group(1, 2, 3, 4)

        # http://pprogramapi.kbs.co.kr/api/v1/page?platform=P&smenu=c2cc5a&source=2tv&sname=enter&stype=gagcon&page_type=list
        menu = JSON.ObjectFromURL('http://pprogramapi.kbs.co.kr/api/v1/page?platform=P&smenu=%s&source=%s&sname=%s&stype=%s&page_type=list' %
            ( smenu, source, sname, stype ))

        image_h = menu['data']['site']['meta']['image_h']
        if image_h not in metadata.posters:
          try: metadata.posters[image_h] = Proxy.Preview(HTTP.Request(image_h, cacheTime=0), sort_order = len(metadata.posters) + 1)
          except Exception as e: Log(str(e))

        image_w = menu['data']['site']['meta']['image_w']
        if image_w not in metadata.art:
          try: metadata.art[image_w] = Proxy.Preview(HTTP.Request(image_w, cacheTime=0), sort_order = len(metadata.art) + 1)
          except Exception as e: Log(str(e))

        page = 1
        while True:
          # https://ummsapi.kbs.co.kr/landing/contents/episode/list?rtype=jsonp&sort_option=rdatetime%20desc&program_code=T2000-0065&page=1&page_size=9&&callback=angular.callbacks._0
          res = JSON.ObjectFromURL('https://ummsapi.kbs.co.kr/landing/contents/episode/list?rtype=json&sort_option=rdatetime%%20desc&program_code=%s&page=%d&page_size=%d' %
              ( menu['data']['site']['meta']['program_code'], page, 500 ))
          if 'error_msg' in res:
            Log.Debug(res['error_msg'])
            break

          for v in res['data']:
            # Log('%s %s %s' % (v['program_date'], v['program_number'], v['program_subtitle'] or v['description']))
            if not v['program_number']:
              continue
            season_num = '1'
            episode_num = v['program_number']
            episode_date = Datetime.ParseDate(v['program_date'], '%Y%m%d').date()
            date_based_season_num = episode_date.year
            date_based_episode_num = episode_date.strftime('%Y-%m-%d')
            if ((season_num in media.seasons and episode_num in media.seasons[season_num].episodes) or
                (date_based_season_num in media.seasons and date_based_episode_num in media.seasons[date_based_season_num].episodes)):
              episode = metadata.seasons[season_num].episodes[episode_num]
              if episode.summary and u'회차정보가 없습니다' not in episode.summary:
                continue
              episode.summary = v['program_summary']
              episode.originally_available_at = episode_date
              episode.title = v['program_subtitle'] or v['description'] or date_based_episode_num
              episode.rating = None     # float(v['avg_rating'])

          page += 1
          if page > res['page_count']:
            break

      except Exception as e:
        Log.Debug(repr(e))
        pass

    elif 'home.ebs.co.kr' in replay_url:
      try:
        # http://home.ebs.co.kr/bestdoctors/review
        #  => http://home.ebs.co.kr/bestdoctors/replay/1/list;jsessionid=...?courseId=BP0PAPG0000000014&stepId=01BP0PAPG0000000014
        # http://home.ebs.co.kr/baddog/replay/24/list?courseId=10016245&stepId=10035139
        match = Regex('courseId=(.+)&stepId=(.+)').search(replay_url)
        if match:
          courseId, stepId = match.group(1, 2)
          page = 1
          while True:
            html = HTML.ElementFromURL('https://www.ebs.co.kr/tv/show/vodListNew', values={
                'courseId': courseId,
                'stepId': stepId,
                'lectId': '666',    # '10962899',
                'vodStepNm': '',    # '세상에 나쁜 개는 없다 시즌3',
                # 'srchType': '',
                # 'srchText': '',
                # 'srchYear': '',
                # 'srchMonth': '',
                'pageNum': page,
                # 'vodProdId': ''
            }, sleep = 0.5)
            for a in html.xpath('//ul[@class="_playList"]/li//a'):
              season_num = '1'
              episode_date = Datetime.ParseDate(a.xpath('./span[@class="date"]')[0].text, '%Y.%m.%d').date()
              match = Regex(u'^(\d+)회').search(a.text.strip())
              if match:
                episode_num = match.group(1)
              else:
                episode_num = episode_date.strftime('%y%m%d')
              date_based_season_num = episode_date.year
              date_based_episode_num = episode_date.strftime('%Y-%m-%d')
              if ((season_num in media.seasons and episode_num in media.seasons[season_num].episodes) or
                  (date_based_season_num in media.seasons and date_based_episode_num in media.seasons[date_based_season_num].episodes)):
                episode = metadata.seasons[season_num].episodes[episode_num]
                if episode.summary and u'회차정보가 없습니다' not in episode.summary:
                  continue
                # Log('E: S%s E%s %s %s' % (season_num, episode_num, episode_date, a.text.strip()))
                show = HTML.ElementFromURL('https://www.ebs.co.kr/tv/show?prodId=&lectId=%s' % Regex('selVodList\(\'(\d+?)\'').search(a.get('href')).group(1), sleep = 0.5)
                episode.summary = show.xpath('//p[@class="detail_story"]')[0].text.strip()
                episode.originally_available_at = episode_date
                episode.title = a.text.strip() or date_based_episode_num
                episode.rating = None

            page += 1
            if page > min(20, int(''.join(html.xpath('//span[@class="pro_vod_page"]//text()')).strip().split(' / ')[1])):
              break

      except Exception as e:
        Log.Debug(repr(e))
        pass

    elif 'www.tving.com' in replay_url:
      try:
        # https://www.tving.com/contents/P001641335
        programCode = Regex('contents/(.+)$').search(replay_url).group(1)
        response = JSON.ObjectFromURL(('https://api.tving.com/v2/media/frequency/program/%s?'
            'order=new&screenCode=CSSD0100&networkCode=CSND0900&osCode=CSOD0900&teleCode=CSCD0900&apiKey=1e7952d0917d6aab1f0293a063697610&'
            'cacheType=main&pageSize=20&&adult=all&free=all&guest=all&scope=all') % programCode)
        for result in response['body']['result']:
          episode = metadata.seasons['1'].episodes[str(result['episode']['frequency'])]
          episode.summary = result['episode']['synopsis']['ko']
          episode.originally_available_at = Datetime.ParseDate(str(result['episode']['broadcast_date']), '%Y%m%d').date()
          episode.title = result['vod_name']['ko']
          episode.rating = None

      except Exception as e:
        Log.Debug(repr(e))
        pass

    else:
      Log(replay_url)

  #   # (5) fill missing info
  #   # if Prefs['override_tv_id'] != 'None':
  #   #   page = HTTP.Request(DAUM_TV_DETAIL2 % metadata.id).content
  #   #   match = Regex('<em class="title_AKA"> *<span class="eng">([^<]*)</span>').search(page)
  #   #   if match:
  #   #     metadata.original_title = match.group(1).strip()

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
