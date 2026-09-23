import sys
import urllib.request

try:
    from bs4 import BeautifulSoup

    def fetch_web_page_text(url: str) -> str:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )
        with urllib.request.urlopen(req) as response:
            html = response.read().decode("utf-8", errors="replace")

        soup = BeautifulSoup(html, "html.parser")
        for element in soup(["script", "style", "noscript", "header", "footer", "nav"]):
            element.decompose()
        return soup.get_text(separator="\n", strip=True)

except ImportError:
    from html.parser import HTMLParser

    class _TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.chunks = []
            self.ignore = False

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style", "noscript", "header", "footer", "nav"):
                self.ignore = True

        def handle_endtag(self, tag):
            if tag in ("script", "style", "noscript", "header", "footer", "nav"):
                self.ignore = False

        def handle_data(self, data):
            if not self.ignore:
                stripped = data.strip()
                if stripped:
                    self.chunks.append(stripped)

    def fetch_web_page_text(url: str) -> str:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )
        with urllib.request.urlopen(req) as response:
            html = response.read().decode("utf-8", errors="replace")

        parser = _TextExtractor()
        parser.feed(html)
        return "\n".join(parser.chunks)


if __name__ == "__main__":
    target_url = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    print(f"Fetching text from: {target_url}\n{'-' * 40}")
    try:
        text = fetch_web_page_text(target_url)
        print(text)
    except Exception as e:
        print(f"Error fetching page: {e}", file=sys.stderr)
