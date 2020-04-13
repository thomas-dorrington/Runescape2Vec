import json
import regex
import networkx as nx
from requests import get
from bs4 import BeautifulSoup
from networkx.readwrite import json_graph
from networkx.drawing.nx_agraph import to_agraph


homepage = 'https://oldschool.runescape.wiki'

category_url_regex = regex.compile(
    r"^https:\/\/oldschool\.runescape\.wiki\/w\/Category:([A-Za-z0-9\_\-\.\%\(\)\/\!]+)"
    r"(?:\?(?:subcatfrom|subcatuntil)\=.*)?$"
)


def get_category_name(category_url):

    category_url_match = category_url_regex.match(category_url)
    return category_url_match.group(1) if category_url_match is not None else None


def scrape_page(page_url):

    return {}


def scrape_category(category_url):

    return {}


def build_category_graph(category_blacklist=[]):

    # Initialise a Directed Graph
    DG = nx.DiGraph()
    root_node = 'Old_School_RuneScape_Wiki'
    DG.add_node(root_node)

    def crawl_categories(category_url, parent_category, processing_next_page=False):

        category_name = get_category_name(category_url)
        if category_name is None:
            print "%s is not a valid URL for a category page" % category_url
            return

        # Check if the category was already in the graph *before* adding the edge
        already_in_graph = True if category_name in DG.nodes else False

        # Add a directed edge from parent category to this category
        DG.add_edge(parent_category, category_name)

        if already_in_graph and not processing_next_page:
            return

        response = get(category_url)
        soup = BeautifulSoup(response.text, 'html.parser')

        subcategories_div = soup.find('div', id='mw-subcategories')
        if subcategories_div is not None:
            # If this category has subcategories, and is not just pages

            # If a category has subcategories split over multiple pages, there will be a 'next page' link,
            # one at the top of the page and one at the bottom of the page.
            # Only follow one to avoid repeated computation, so keep a flag to indicate if we've already followed one
            # Example: https://oldschool.runescape.wiki/w/Category:Updates_by_day
            followed_next_page = False

            for subcategory in subcategories_div.find_all('a'):

                if subcategory.text == 'previous page':
                    # We only travel by going forward using 'next page'
                    # Prevents the infinite loops arising from going back and forth with 'next page' and 'previous page'
                    # Assumes we cannot land 'in the middle', so to speak, of a category's subcategories list,
                    # and would actually need to go backwards.

                    continue

                if subcategory.text == 'next page':

                    if followed_next_page:
                        # We have already visited the next page
                        # (i.e. this is the 'next page' link at the bottom of the page)
                        continue

                    else:
                        # We are following the 'next page' link for the first time
                        # The parent category of the recursive call must remain the same

                        followed_next_page = True
                        crawl_categories(
                            category_url=homepage + subcategory.attrs['href'],
                            parent_category=parent_category,
                            processing_next_page=True
                        )

                else:

                    crawl_categories(
                        category_url=homepage + subcategory.attrs['href'],
                        parent_category=category_name,
                        processing_next_page=False
                    )

    crawl_categories(
        category_url='https://oldschool.runescape.wiki/w/Category:Content',
        parent_category=root_node
    )

    # A = to_agraph(DG)
    # A.layout('dot')
    # A.draw('category_graph.pdf')

    return DG


if __name__ == '__main__':

    category_graph = build_category_graph(
        category_blacklist=[]
    )

    with open('data/category_graph.json', 'w') as open_f:
        json.dump(json_graph.adjacency_data(category_graph), open_f, indent=4)
