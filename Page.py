import datetime
import traceback
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import urllib.request
from url_normalize import url_normalize
import sys
from urllib import robotparser


class Page(dict):
    url = None
    parsed_url = None
    domain = None
    path = None
    query = None
    size = None
    time_stamp = None
    base_url = None
    depth = 0
    novelty = 0
    importance = 0
    priority = novelty - importance
    is_valid = True
    rp = robotparser.RobotFileParser()
    response_code = None
    denied_by_robot_exclusion = False
    timestamp = None

    def __init__(self, url, depth):
        self.raw_url = url
        self.url = url_normalize(url)
        self.parsed_url = urlparse(url)
        self.domain = self.parsed_url.netloc
        self.path = list(filter(None, self.parsed_url.path.split('/')))
        self.query = self.parsed_url.query
        self.base_url = self.parsed_url[0] + '://' + self.parsed_url[1]
        self.depth = depth
        self.rp.set_url(self.base_url + '/robots.txt')

    def __lt__(self, other):
        return self.priority < other.priority

    def update_novelty(self, novelty):
        self.novelty = novelty
        self.priority = self.novelty - self.importance

    def update_importance(self, importance):
        self.importance = importance
        self.priority = self.novelty - importance

    def fetch(self):
        try:
            with urllib.request.urlopen(self.url, timeout=5) as response:
                self.response_code = response.code
                self.time_stamp = datetime.datetime.now()
                return response.read()
        except:
            # traceback.print_exc()
            # print('failed')
            return None

    def mine_urls(self, html_doc):
        if html_doc is None:
            return
        soup = BeautifulSoup(html_doc, 'html.parser', from_encoding="iso-8859-1")
        mined_urls = set([])
        for a in soup.find_all('a'):
            mined_urls.add(a.get('href'))
        return mined_urls

    def vet_url(self, url):
        if url is None:
            return
        url_exts = ['.ogg', '.flv', '.swf', '.mp3', '.jpg', '.jpeg', '.gif', '.css', '.ico', '.rss' '.tiff', '.png',
                    '.pdf']
        for ext in url_exts:
            if url.endswith(ext):
                return
        if url.startswith('#'):
            return
        elif url.startswith('/') and ':' not in url:
            return urljoin(self.base_url, url)
        elif url.startswith('http') or url.startswith('https'):
            return url
        else:
            return None

    def vet_mined_urls(self, mined_urls):
        vetted_urls = []
        for mined_url in mined_urls:
            vetted_url = self.vet_url(mined_url)
            if vetted_url is not None:
                vetted_urls.append(vetted_url)
        vetted_url_depth = self.depth + 1
        return [Page(page_url, vetted_url_depth) for page_url in vetted_urls]

    def process(self):
        self.rp.read()
        if not self.rp.can_fetch("*", self.url):
            self.denied_by_robot_exclusion = True
            return None
        html_doc = self.fetch()
        if html_doc is None:
            return
        mined_urls = self.mine_urls(html_doc)
        if mined_urls is None:
            return
        vetted_urls = self.vet_mined_urls(mined_urls)
        return vetted_urls
