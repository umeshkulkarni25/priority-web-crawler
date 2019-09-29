from collections import OrderedDict
from concurrent.futures.thread import ThreadPoolExecutor

from googlesearch import search
from Page import Page
import queue
import threading
import copy


class Crawler:
    crawling_policy = 'prioritized'
    workers = 10
    pages_to_be_crawled = queue.PriorityQueue()
    frontier = {}
    crawled_web = {}
    crawled_pages = set([])
    log = []
    target = 1000
    crawl_count = 0
    crawler_lock = threading.RLock()

    def get_seed_urls(self, query):
        for url, importance in zip(search(query, stop=5), range(5)):
            self.pages_to_be_crawled.put(Page(url, 0))

    def get_next_page_to_be_crawled_bfs(self):
        return self.pages_to_be_crawled.get()

    def crawl(self, thread_number):
        while True:
            next_page = self.get_next_page_to_be_crawled_bfs()
            newly_found_pages = next_page.process()
            with self.crawler_lock:
                if next_page.url in self.crawled_pages:
                    print('wtf-{}'.format(next_page.url))
                self.crawled_pages.add(next_page.url)
                print(len(self.crawled_pages))
                if len(self.crawled_pages) >= self.target:
                    print('breaking-{}'.format(thread_number))
                    break
                self.log.append(next_page)
                if newly_found_pages is not None:
                    for newly_found_page in newly_found_pages:
                        if self.crawled_web.get(newly_found_page.url) is None and self.frontier.get(newly_found_page.url) is None:
                            self.frontier[newly_found_page.url] = newly_found_page
                            self.pages_to_be_crawled.put(newly_found_page)

    def start(self):
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            executor.map(self.crawl, range(self.workers))


if __name__ == '__main__':
    crawler = Crawler()
    crawler.get_seed_urls('australia')
    import datetime

    print(datetime.datetime.now())
    crawler.start()
    print(datetime.datetime.now())
    print(len(crawler.crawled_pages))

    import json

    with open('frontier.json', 'w') as fp:
        json.dump(crawler.frontier, fp)
    from urllib.parse import urlparse

    with open('crawled_urls.json', 'w') as fp:
        domains = {}
        for url in list(crawler.crawled_pages):
            domain = urlparse(url).netloc
            if domains.get(domain) is None:
                domains[domain] = 1
            else:
                domains[domain] += 1
        OrderedDict(sorted(domains.items(),
                           key=lambda kv: kv[1], reverse=True))
        json.dump(domains, fp)
    with open('log.json', 'w') as fp:
        log = []
        for page in crawler.log:
            page_log = {
                'url': page.url,
                'depth': page.depth,
                'priority': page.priority,
                'code': page.response_code,
                'denied_by_robot_exclusion': page.denied_by_robot_exclusion
            }
            log.append(page_log)
        json.dump(log, fp)
