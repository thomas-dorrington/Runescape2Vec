from requests import get
from bs4 import BeautifulSoup


homepage = 'https://oldschool.runescape.wiki'


def scrape_page(page_url):

    response = get(page_url)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Initialise a list to contain all the (non-hidden) categories classified at the bottom of the page
    page_categories = []
    category_links_div = soup.find('div', id='mw-normal-catlinks')
    if category_links_div is not None:
        for category in category_links_div.find_all('a'):
            if category.text == 'Category':
                continue
            page_categories.append(category.text)
    else:
        print "%s does not have a 'mw-normal-catlinks' div" % page_url

    return page_categories


def scrape_all_pages():
    """
    Uses https://oldschool.runescape.wiki/w/Special:AllPages to return the set of all pages (ignoring redirect pages).
    Useful to compare with all the pages found by a CategoryGraph object.

    Upon inspection, any pages found through this function, but not found when crawling the category graph,
    (about 1000) are nearly always disambiguation pages. Outside of that, they are stubs,
    or part of hidden/maintenance categories.

    Any pages found through crawling the category graph, and not through this function, (about 8000) are either:
        - Of the form .../w/(RuneScape|User|Update|Exchange|Transcript|Template|Calculator):...
        - A redirect page, typically some kind of polished bone, e.g. /w/Polished_ogre_ribs -> /w/Ogre_ribs
    """

    all_pages = set()
    start_page = 'https://oldschool.runescape.wiki/w/Special:AllPages?from=&to=&namespace=0&hideredirects=1'

    def crawl_page(page_url):

        response = get(page_url)
        soup = BeautifulSoup(response.text, 'html.parser')

        all_pages_div = soup.find('div', class_='mw-allpages-body')
        for page in all_pages_div.find_all('a'):
            all_pages.add(homepage + page['href'])

        all_pages_navigation = soup.find('div', class_='mw-allpages-nav')
        for link in all_pages_navigation.find_all('a'):
            if 'previous page' in link.text.lower():
                continue
            if 'next page' in link.text.lower():
                crawl_page(homepage + link['href'])

    crawl_page(start_page)
    return all_pages
