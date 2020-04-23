import regex
from requests import get
from bs4 import BeautifulSoup


homepage = 'https://oldschool.runescape.wiki'

invalid_page_regex = regex.compile(
    r""
)


def is_valid_page(page_url):

    return invalid_page_regex.match(page_url) is None


def scrape_page(page_url):

    response = get(page_url)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Initialise a set to store all the (non-hidden) categories classified at the bottom of the page
    # Note: this is not necessarily the same as finding the categories containing the page in the category graph
    # (although hopefully the lists are the same or at least similar)
    page_categories = set()
    category_links_div = soup.find('div', id='mw-normal-catlinks')
    if category_links_div is not None:
        for category in category_links_div.find_all('a'):
            if category.text == 'Category' or category.text == 'Categories':
                continue
            page_categories.add(category.text)

    # Initialise a list to store all the paragraphs of the page, as strings
    page_paragraphs = []
    for paragraph in soup.find_all('p'):

        # Prevents text in paragraph like '1st floor[UK]2nd floor[US]'
        for span in paragraph.find_all('span', class_='floornumber-us'):
            span.decompose()

        # Prevents text in paragraph representing references, i.e. '[1]', '[2]', etc.
        for sup in paragraph.find_all('sup', class_='reference'):
            sup.decompose()

        # Collapse all multiple whitespaces and newlines into one single space
        paragraph_text = regex.sub(r'[ \n]+', r' ', paragraph.text).strip()

        if paragraph_text:
            # If not empty string
            page_paragraphs.append(paragraph_text)

    # Extract plain-text name of page using first heading
    # Useful for file names when saving text to disk, as well as collocation vectors


    return {
        'paragraphs': page_paragraphs,
        'categories': page_categories
    }


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
