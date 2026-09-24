import urllib.request
import re

req = urllib.request.Request('https://my.rotary.org/en/club-search', headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
try:
    with urllib.request.urlopen(req) as resp:
        content = resp.read().decode('utf-8')
        print('Page length:', len(content))
        apis = re.findall(r'https?://[^\s\"\'\<\>]+api[^\s\"\'\<\>]+', content)
        print('APIs found in page:', apis[:10])
        # Find forms or data endpoints
        endpoints = re.findall(r'/(?:en/)?[a-zA-Z0-9_\-/]+search[a-zA-Z0-9_\-/]*', content)
        print('Search endpoints found:', set(endpoints[:15]))
except Exception as e:
    print('Error:', e)
