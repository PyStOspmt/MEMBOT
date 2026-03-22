import urllib.request
import re

def get_og(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req).read().decode('utf-8')
        m = re.search(r'property="og:video" content="([^"]+)"', res)
        if m: return m.group(1).replace('&amp;', '&')
    except Exception as e:
        print(e)
    return None

print(get_og('https://vxinstagram.com/reel/DNDxqF0s2Qe/'))
print(get_og('https://fxtwitter.com/elonmusk/status/1769741369527926831'))
print(get_og('https://vxtiktok.com/@scout2015/video/6718335390845095173'))
