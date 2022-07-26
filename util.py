""" 
    Miscellaneous functions. 
"""

from bs4 import BeautifulSoup as bs
import json

def make_soup(request):
    """ Convert a request into a BeautifulSoup object. """
    return bs(request.text, 'lxml')

def load_json_data(file_name):
    """ Loads the data from a json file, returns it.
    r-type: dict 
    """
    try:
        with open(f"data/{file_name}.json") as jf:
            content = json.load(jf)
    except FileNotFoundError:
        return False
    return content

def list_of_unique_dicts(x):
    """ 
    Removes duplicate values from a list of dicts.
    """
    return list({v['filmId']:v for v in x}.values())

def lists_merge(lists, unique=False):
    """
    Parameters: lists (list of lists)
    Returns a single list with merged items
    """
    results = [elem for sublist in lists for elem in sublist]
    return results if not unique else list(set(results))

class HTML_Adder():
    bolden = lambda x: f'<strong>{x}</strong>'
    italicise = lambda x: f'<i>{x}</i>'
    link = lambda x, y: f'<a href="{x}">{y}</a>'