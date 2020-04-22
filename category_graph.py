import json
import regex
import networkx as nx
from requests import get
from utils import homepage
from bs4 import BeautifulSoup
from networkx.readwrite import json_graph
from networkx.drawing.nx_agraph import to_agraph


class CategoryGraph(object):

    # Note: this regex does not allow categories to be spanning multiple subcategories *and* pages at the same time.
    # I.e. it does not allow for a mix of pagefrom/pageuntil and subcatfrom/subcatuntil.
    # This is fine though, as this case should never arise under the way we handle crawling multiple 'next page's
    category_url_regex = regex.compile(
        r"^https:\/\/oldschool\.runescape\.wiki\/w\/Category:([A-Za-z0-9\_\-\.\%\(\)\/\!]+)"
        r"(?:\?(?:(?:(?:pagefrom|pageuntil)\=.*\#mw-pages)|(?:(?:subcatfrom|subcatuntil)\=.*\#mw-subcategories)))?$"
    )

    def __init__(self, root_node, root_category_url, graph=None):

        self.root_node = root_node
        self.root_category_url = root_category_url

        if graph is None:
            # Initialise a Directed Graph and crawl wiki from scratch

            self.category_graph = nx.DiGraph()
            self.category_graph.add_node(self.root_node)
            self.category_graph.nodes[self.root_node]['pages'] = []

            self._crawl_categories(
                category_url=self.root_category_url,
                parent_category=self.root_node,
                processing_next_page=False
            )

        else:
            # We are loading an already crawled graph from disk
            self.category_graph = graph

        # See if the graph has cycles in, and if so print a warning
        number_of_cycles = len(list(self.find_cycles()))
        if number_of_cycles == 0:
            print "Directed graph has no cycles."
        else:
            print "Warning: directed graph has %s cycles in." % str(number_of_cycles)

    @staticmethod
    def get_category_name(category_url):

        category_url_match = CategoryGraph.category_url_regex.match(category_url)
        return category_url_match.group(1) if category_url_match is not None else None

    @staticmethod
    def load(path_to_load):

        with open(path_to_load, 'r') as open_f:
            category_graph_json = json.load(open_f)

        return CategoryGraph(
            root_node=category_graph_json['root_node'],
            root_category_url=category_graph_json['root_category_url'],
            graph=json_graph.adjacency_graph(category_graph_json['graph'])
        )

    def save(self, path_to_save):

        category_graph_json = {
            'root_node': self.root_node,
            'root_category_url': self.root_category_url,
            'graph': json_graph.adjacency_data(self.category_graph)
        }

        with open(path_to_save, 'w') as open_f:
            json.dump(category_graph_json, open_f, indent=4)

    def draw(self, path_to_save, nodes_to_include=None):
        """
        Draws graphical representation of the directed graph, saving to file `path_to_save`.
        `nodes_to_include` typically set to `nx.dag.descendants()`
        """

        if nodes_to_include is None:
            # Draw the entire graph network

            A = to_agraph(self.category_graph)

        else:
            # Draw the subgraph induced by the nodes in `nodes_to_include`
            # The induced subgraph contains the nodes in `nodes_to_include` and the edges between those nodes
            # Note: `subgraph()` returns a `SubGraph View`. The graph structure cannot be changed and
            # node/edge attributes are shared with the original graph.

            A = to_agraph(self.category_graph.subgraph(nodes_to_include))

        A.layout('dot')
        A.draw(path_to_save)

    def _crawl_categories(self, category_url, parent_category, processing_next_page=False):
        """
        Recursive function which crawls the category graph by following URL links on the Wiki via depth-first traversal.
        Initially called from __init__ with `category_url` set to the root category URL.
        """

        category_name = CategoryGraph.get_category_name(category_url)
        if category_name is None:
            print "%s is not a valid URL for a category page" % category_url
            return

        # Check if the category was already in the graph *before* adding the edge
        already_in_graph = True if category_name in self.category_graph.nodes else False

        # Add a directed edge from parent category to this category
        self.category_graph.add_edge(parent_category, category_name)

        if already_in_graph:
            if not processing_next_page:
                return
        else:
            # If first time seeing the category, initialise the node's attribute dictionary

            # Scrape category for page URLs
            pages = []
            self._scrape_category(category_url=category_url, pages=pages, category_name=category_name)

            self.category_graph.nodes[category_name]['pages'] = pages
            self.category_graph.nodes[category_name]['category_url'] = homepage + '/w/Category:' + category_name

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
                        self._crawl_categories(
                            category_url=homepage + subcategory.attrs['href'],
                            parent_category=parent_category,
                            processing_next_page=True
                        )

                else:

                    self._crawl_categories(
                        category_url=homepage + subcategory.attrs['href'],
                        parent_category=category_name,
                        processing_next_page=False
                    )

    def _scrape_category(self, category_url, pages, category_name):
        """
        Scrapes a category page (pointed to by the URL `category_url`) for all of its pages.
        Only finds page URLs directly under this category (i.e. not recursively accumulated under subcategories).

        Pages are accumulated in the argument list `pages`, which should be defined outside the scope of this function
        (i.e. just before calling) as an empty list.
        """

        # Check `category_url` is a valid URL for a category page, and that the category name inferred under
        # `category_url` is still referring to the same category as this function was initially called under
        # (i.e. it has not changed for some reason when following the 'next page' links)
        category_url_name = CategoryGraph.get_category_name(category_url)
        if category_url_name is None:
            print "%s is not a valid URL for a category page" % category_url
            return
        if category_url_name != category_name:
            print "%s is no longer the same as %s when scraping pages split across multiple URLs" % (category_url_name,
                                                                                                     category_name)
            return

        response = get(category_url)
        soup = BeautifulSoup(response.text, 'html.parser')

        pages_div = soup.find('div', id='mw-pages')
        if pages_div is not None:
            # If this category has pages, and is not just subcategories
            # Use same logic as is used in `self._crawl_categories()` - see there for detailed comments

            followed_next_page = False

            for page in pages_div.find_all('a'):

                if page.text == 'previous page':
                    continue

                if page.text == 'next page':

                    if followed_next_page:
                        continue

                    else:
                        followed_next_page = True
                        self._scrape_category(
                            category_url=homepage + page.attrs['href'],
                            pages=pages,
                            category_name=category_name
                        )

                else:
                    page_url = homepage + page.attrs['href']
                    if page_url not in pages:
                        pages.append(page_url)

    def find_cycles(self):
        """
        Finds the simple cycles of the directed graph, returning a generator.
        Each cycle is represented by a list of nodes along the cycle.
        """

        return nx.algorithms.cycles.simple_cycles(self.category_graph)

    def remove_edges(self, edges_to_remove):
        """
        Used to remove cycles from the graph.
        There appears to be some mistakes on the wiki, where cycles exist among some categories.
        For example, Skills -> Construction, but also Construction -> Skills.
        While the correct removal of some cycles could be automated, in general the process cannot be, so we rely on
        an input list of edges to remove, to be supplied after human inspection: `edges_to_remove`
        """

        for edge in edges_to_remove:

            if edge not in self.category_graph.edges:
                print "Warning: trying to delete an edge from %s to %s which does not exist." % (edge[0], edge[1])
                continue

            self.category_graph.remove_edge(*edge)

        # See if the graph still has cycles in as a sanity check
        new_cycles = len(list(self.find_cycles()))
        if new_cycles == 0:
            print "Directed graph now has no cycles in."
        else:
            print "Warning: directed graph still has %s cycles in." % str(new_cycles)

    def get_all_pages(self, from_category=None):
        """
        Returns a set of all the pages contained by any of the categories in the graph.
        """

        all_graph_pages = set()

        for node in self.category_graph.nodes:
            for page in self.category_graph.nodes[node]['pages']:
                all_graph_pages.add(page)

        return all_graph_pages

    def get_page_categories(self, page_url):
        """
        Returns a set of all the categories this page is classified (directly) under.

        Uses the category graph and node attributes (not the list of categories at the bottom of a page's URL).
        In fact, this method can be used to compare the two lists and check they are the same.
        """

        page_categories = set()

        for node in self.category_graph.nodes:
            if page_url in self.category_graph.nodes[node]['pages']:
                page_categories.add(node)

        return page_categories


if __name__ == '__main__':

    category_graph = CategoryGraph(
        root_node='Old_School_RuneScape_Wiki',
        root_category_url='https://oldschool.runescape.wiki/w/Category:Content'
    )

    cycle_edges_to_remove = [('Construction', 'Skills'), ('Images_in_the_Wilderness', 'Images_in_the_Wilderness')]
    category_graph.remove_edges(cycle_edges_to_remove)

    category_graph.save('data/category_graph.json')
