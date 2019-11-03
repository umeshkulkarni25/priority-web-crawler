from concurrent.futures.thread import ThreadPoolExecutor
from googlesearch import search
from Page import Page
import queue
import threading
import copy
import csv
import datetime
import sys


class Crawler:
    strategy = 'priority'  # could be priority or bfs
    workers = 50  # number of threads that crawl
    target = 1000  # number of urls to be crawled before stopping, 1000 is default if not provided
    pages = queue.PriorityQueue()  # priority queue for pages waiting to be crawled
    frontier = {}  # tree for all the found urls
    explored = {}  # tree for crawled urls
    frontier_set = set([])  # used for bfs instead of tree
    explored_set = set([])  # used for bfs instead of tree
    explored_url = {}
    frontier_lock = threading.RLock()  # lock on frontier dict
    explored_lock = threading.RLock()  # lock on explored dict
    lock = threading.RLock()
    report_log = queue.Queue()  # report log
    phrase = 'new york'  # used as default phrase if no phrase provided from command line

    ''' initialize crawler with user provided values '''

    def __init__(self, target=None, phrase=None):
        if target is not None:
            self.target = target
        if phrase is not None:
            self.phrase = phrase
        self.get_seed_urls(self.phrase)

    ''' method to fetch the initial seed urls'''

    def get_seed_urls(self, query):
        for url, importance in zip(search(query, stop=10), range(10)):
            self.pages.put(Page(url, 0))

    def get_next_page_using_bfs(self):
        try:
            next_page = self.pages.get(block=True, timeout=5)
        except queue.Empty:
            return None
        return next_page

    ''' method used to retrieve highest priority valid page '''

    def retrieve_valid_page(self):
        try:
            page = self.pages.get(block=True, timeout=5)
            while True:
                if page.is_valid:
                    break
                page = self.pages.get(block=True, timeout=5)
            return page
        except queue.Empty:
            return None

    ''' method to fetch next page to be crawled in a priority based crawler'''

    def get_next_page_using_priority(self):
        page = self.retrieve_valid_page()
        if page is None:
            return
        while True:
            page.update_novelty(self.get_novelty_score(page))
            next_best_page = self.retrieve_valid_page()
            if next_best_page is None:
                return
            if page.priority <= next_best_page.priority:
                break
            self.pages.put(page)
            page = next_best_page
        return page

    ''' add a newly found page url to frontier tree the url is broken down in its constituent parts
        namely domain, path and query and given importance as we traverse down the tree'''

    def add_to_frontier(self, new_page, page):
        with self.frontier_lock:
            updated_pages = []
            url_parts = [new_page.domain] + new_page.path
            if len(new_page.query) > 0:
                url_parts += [new_page.query]
            frontier_pointer = self.frontier
            aggregated_importance = 0
            base_importance = 2 if new_page.domain != page.domain else 1  # give more importance to a cross reference than a self reference
            for url_part in url_parts:
                if frontier_pointer.get(url_part) is None:
                    frontier_pointer[url_part] = {'count': base_importance}
                    aggregated_importance += base_importance
                else:
                    frontier_pointer[url_part]['count'] += base_importance
                    aggregated_importance += frontier_pointer[url_part]['count']
                    # if we see a node that means we are seeing the url again, which means we need to update the importance of the said node
                    # to achieve this we copy the node calculate its new importance score and insert it in the the queue,
                    # the old duplicate node is now marked invalid and will be popped off from the queue and not processed,
                    # this approach saves us a re-hepifying post importance update
                    if isinstance(frontier_pointer[url_part].get('page'), Page):
                        replacement_page = copy.deepcopy(frontier_pointer[url_part]['page'])
                        replacement_page.update_importance(aggregated_importance)
                        updated_pages.append(replacement_page)
                        frontier_pointer[url_part]['page'].is_valid = False
                        frontier_pointer[url_part]['page'] = replacement_page
                frontier_pointer = frontier_pointer[url_part]
            new_page.update_importance(aggregated_importance)
            frontier_pointer['page'] = new_page
            updated_pages.append(new_page)
            return updated_pages

    ''' method to add a crawled url to explore tree, again the the url is broken down in its constituent parts
        namely domain, path and query and given novelty score as we traverse down the tree this structure is used as it 
        facilitates taxing a url in accordance with its match in the tree'''

    def add_to_explored(self, page):
        with self.explored_lock:
            url_parts = [page.domain] + page.path
            if len(page.query) > 0:
                url_parts += [page.query]
            explored_pointer = self.explored
            for url_part in url_parts:
                if explored_pointer.get(url_part) is None:
                    explored_pointer[url_part] = {'count': 1}
                else:
                    explored_pointer[url_part]['count'] += 1
                explored_pointer = explored_pointer[url_part]

    ''' method to traverse down a'''

    def is_explored(self, page):
        with self.explored_lock:
            url_parts = [page.domain] + page.path
            if len(page.query) > 0:
                url_parts += [page.query]
            explored_pointer = self.explored
            for url_part in url_parts:
                if explored_pointer.get(url_part) is None:
                    return False
                explored_pointer = explored_pointer[url_part]
            return True

    ''' method to traverse down the explored tree and give a more accurate and granular novelty score to a given url
        in accordance with the match this the explored tree'''

    def get_novelty_score(self, page):
        with self.explored_lock:
            aggregated_visits = 0
            url_parts = [page.domain] + page.path
            if len(page.query) > 0:
                url_parts += [page.query]
            explored_pointer = self.explored
            for url_part, depth in zip(url_parts, range(len(url_parts))):
                if explored_pointer.get(url_part) is None:
                    return aggregated_visits
                else:
                    aggregated_visits += explored_pointer[url_part]['count']
                explored_pointer = explored_pointer[url_part]
            return aggregated_visits

    ''' function to add a url to report to be printed post crawl'''

    def update_report(self, page):
        if not page.denied_by_robot_exclusion and page.is_valid:
            try:
                if page.time_stamp is not None:
                    time = page.time_stamp.ctime()
                else:
                    time = None
                page_report = [(
                    page.url,
                    time,
                    page.size,
                    page.response_code,
                    page.depth,
                    page.priority,
                    page.domain
                )]
                self.report_log.put(page_report, block=True, timeout=5)
            except queue.Full:
                return None

    ''' this function is target for all worker threads it performs following action:
        fetch url, crawl url, and append the newly found url ti the priority queue 
        it also updates the frontier and explored dicts accordingly'''

    def crawl(self, thread_number):
        while True:
            page = self.get_next_page_using_priority() if self.strategy == 'priority' else self.get_next_page_using_bfs()
            if page is None or self.is_explored(page):
                continue
            new_pages = page.process()
            self.update_report(page)
            if self.report_log.qsize() >= self.target:
                break

            self.add_to_explored(page)

            if new_pages is not None:
                if self.strategy == 'priority':
                    for new_page in new_pages:
                        for updated_page in self.add_to_frontier(new_page, page):
                            self.pages.put(updated_page)
                else:
                    for new_page in new_pages:
                        if new_page.url not in self.explored_set and new_page.url not in self.frontier_set:
                            self.pages.put(new_page)

    ''' method to make crawler start crawling'''

    def start(self):
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            executor.map(self.crawl, range(self.workers))


if __name__ == '__main__':
    try:
        target = int(sys.argv[1])
        crawler = Crawler(target, sys.argv[2])
        start_time = datetime.datetime.now()
        print('crawling started with seed phrase: {}'.format(crawler.phrase))
        print('start time: {}'.format(start_time))
        print('crawling...')
        crawler.start()
        end_time = datetime.datetime.now()
        print('end time: {}'.format(end_time))
        print('total time spent: {}'.format(end_time - start_time))
        print('pages crawled:{}'.format(crawler.report_log.qsize()))
        report = list(crawler.report_log.queue)
        with open('report_log.csv', 'w') as writeFile:
            writer = csv.writer(writeFile)
            writer.writerows([('url','time_stamp','page_size','response_code','depth','priority', 'domain')])
            writer.writerows(report)
    except ValueError:
        print('wrong options provided')
        print('sample command: python Crawler.py 100 \'brooklyn parks\'')

