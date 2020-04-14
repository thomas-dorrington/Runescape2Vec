import json
import regex
import networkx as nx
from requests import get
from bs4 import BeautifulSoup
from networkx.readwrite import json_graph
from networkx.drawing.nx_agraph import to_agraph


homepage = 'https://oldschool.runescape.wiki'


def scrape_page(page_url):

    return {}


def scrape_category(category_url):

    return {}


class CategoryGraph(object):

    category_url_regex = regex.compile(
        r"^https:\/\/oldschool\.runescape\.wiki\/w\/Category:([A-Za-z0-9\_\-\.\%\(\)\/\!]+)"
        r"(?:\?(?:subcatfrom|subcatuntil)\=.*)?$"
    )

    def __init__(self, root_node, root_category_url, graph=None):

        self.root_node = root_node
        self.root_category_url = root_category_url

        if graph is None:
            # Initialise a Directed Graph and crawl wiki from scratch

            self.category_graph = nx.DiGraph()
            self.category_graph.add_node(self.root_node)

            self._crawl_categories(
                category_url=self.root_category_url,
                parent_category=self.root_node,
                processing_next_page=False
            )

        else:
            # We are loading an already crawled graph from disk
            self.category_graph = graph

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

    def draw(self, path_to_save, subgraph_root_node=None):

        A = to_agraph(self.category_graph)
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
        While the correct removal of some cycles can be automated, in general the process cannot be, so we rely on
        an input list of edges to remove, to be supplied after human inspection: `edges_to_remove`
        """

        for edge in edges_to_remove:

            if edge not in self.category_graph.edges:
                print "Warning: trying to delete an edge from %s to %s which does not exist." % (edge[0], edge[1])
                continue

            self.category_graph.remove_edge(*edge)

        # See if the graph still has cycles as a sanity check
        new_cycles = len(list(self.find_cycles()))
        if new_cycles != 0:
            print "Warning: directed graph still has %s cycles in." % str(new_cycles)


if __name__ == '__main__':

    category_graph = CategoryGraph(
        root_node='Old_School_RuneScape_Wiki',
        root_category_url='https://oldschool.runescape.wiki/w/Category:Content'
    )

    category_graph.draw('data/category_graph.pdf')
    category_graph.save('data/category_graph.json')
