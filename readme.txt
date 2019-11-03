Submission list:
 code files:
  1. Page.py - Page class which represents a Page and houses code to fetch the url
  and mine the html doc. It supports robot exclusion as well.

  2 .Crawler.py - This is the muti-threaded crawler

  Log files:
  1. paris_texas_bfs.csv - bfs crawl log for the query 'paris texas'(10000 rows)
  2. paris_texas_priority_crawl.csv - priority crawl log for query 'paris texas'(10000 rows)
  3. brooklyn_parks_bfs.csv - bfs crawl log for the query 'brooklyn parks'(10000 rows)
  4. brooklyn_parks_priority_crawl.csv - priority crawl log for query 'brooklyn parks'(10000 rows)

  run instructions:
    Please run Crawler.py it takes following commandline-arguments:
    Sample command: python Crawler.py 100 'paris texas'
    target: how many urls to crawl
    phrase: phrase to get seed pages

  The code uses third-party libraries such as googlesearch, BeautifulSoup pleas make sure they are installed
  The code is Python3.0
