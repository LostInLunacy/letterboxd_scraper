""" 
    Miscellaneous functions. 
"""

from bs4 import BeautifulSoup as bs
import json
import pathlib
import git
import re

def get_current_file():
    return pathlib.Path(__file__).parent.absolute()

def get_git_root(path):
    git_repo = git.Repo(path, search_parent_directories=True)
    # print(git_repo.working_dir)
    git_root = git_repo.git.rev_parse("--show-toplevel")
    return git_root

def make_soup(request):
    """ Convert a request into a BeautifulSoup object. """
    return bs(request.text, 'lxml')

def load_json_data(file_name):
    """ Loads the data from a json file, returns it.
    r-type: dict 
    """
    try:
        with open(f"{ROOT}/data/{file_name}.json") as jf:
            content = json.load(jf)
    except FileNotFoundError:
        return False
    return content

def key_max(d, max_num=1, only_max=False):
    assert len(d) >= max_num
    if max_num == 1: 
        m = max(zip(d.values(), d.keys()))[1]
    else:
        n = 1
        while n <= max_num:
            m = max(zip(d.values(), d.keys()))[1]
            d.pop(m)
            n += 1
    if only_max and list(d.values()).count(d[m]) > only_max:
        return False
    return m


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

def multi_replace(string, d):
    """
    Params:
    d (dict)
        Example ({'hello': 'welcome', 'world': 'back'})
    """
    for k, v in d.items():
        string = string.replace(k,v)
    return string

def format_name(name):
    """
    Name -> valid link
    """
    list_name = name.lower()
    formatted_name = multi_replace(list_name, {' ': '-', '|': '-', '+': ''})

    # Get a set of unique characters which will not make up url for list page
    unknown_chrs = set([c for c in formatted_name if not any( [c.isalpha(), c.isnumeric(), c in ('-', '_')] )])
    # Make sure parenthesis are proceeded by a backslash, to avoid unmatched parenthesis error
    unknown_chrs = "|".join([i if i not in ("(", ")") else f"\{i}" for i in unknown_chrs])
    # Replace characters which do not show in URL links with spaces
    try:
        formatted_name = re.sub(unknown_chrs, "", formatted_name)
    except:
        print(f'''\
            Failed to format list name: {list_name}\
            Formatted name: {formatted_name}\
            Unknown chars: {unknown_chrs}''')

    # Then replace any excess spaces
    formatted_name = re.sub(" +", " ", formatted_name).strip()
    # Remove multi-dash
    while '--' in formatted_name:
        formatted_name = formatted_name.replace('--', '-')

    return formatted_name

def limit_list(l, limit):
    return l if len(l) <= limit else l[0:limit]

noneify = lambda x: x if x is not None else ''
noneify_func = lambda x, func, *args, **kwargs: func(x, *args, **kwargs) if x else ''

ROOT = get_git_root(get_current_file())

class HTML_Adder():
    bolden = lambda x: f'<strong>{x}</strong>'
    italicise = lambda x: f'<i>{x}</i>'
    link = lambda x, y: f'<a href="{x}">{y}</a>'


if __name__ == '__main__':
    ''' Testing '''
    pass

