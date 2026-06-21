import urllib.request

API_KEY = "Sd_440ab2e89ce04ad1508862462d0e5278"

url = "https://api.supadata.ai/v1/transcript?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ"

req = urllib.request.Request(
    url,
    headers={
        "x-api-key": API_KEY
    }
)

print(urllib.request.urlopen(req).read().decode())