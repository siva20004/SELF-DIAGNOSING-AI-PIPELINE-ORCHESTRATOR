import urllib.request
import re

html = urllib.request.urlopen('https://self-diagnosing-ai-pipeline-orchest.vercel.app/').read().decode()
print("HTML:", html)
matches = re.findall(r'src="(/assets/[^"]+\.js)"', html)
for m in matches:
    js_url = 'https://self-diagnosing-ai-pipeline-orchest.vercel.app' + m
    print('Found JS file:', js_url)
    try:
        content = urllib.request.urlopen(js_url).read().decode()
        api_urls = re.findall(r'https?://[a-zA-Z0-9.-]+(?::\d+)?', content)
        print('API URLs found in', m, ':', set(api_urls))
    except Exception as e:
        print('Failed to read:', e)
