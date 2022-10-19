""" 
    For working with Letterboxd lists. 
        - LetterboxdList (general class for lists on Letterboxd)
        - MyList (subclass for lists owned by the user)
   
    NOTE: throughout this module, 'entries' denotes 'films within a list'. 
"""

## Imports
import re
from typing import Type
import requests
import pendulum

## Local Imports
from session import SESSION
from user_and_network import get_psuedo_username
import util
from util import lists_merge, make_soup
from film_info import FilmInfo

def format_entries(entries):
    """ When updating lists, entries are required to be formatted as follows
    in this return statement 
    """
    return [{"filmId": i} for i in entries]


class Studio():
    """
    Info about Studios listed on Letterboxd (e.g. 'Wownow Entertainment')
    """

    def __init__(self, name):
        self.name = name
        self.soup = make_soup(SESSION.request('GET', self.suburl))

    def __repr__(self):
        cls_name = self.__class__.__name__
        return f'{cls_name} ({self})'

    def __str__(self):
        return f'''\
        == Studio ==\
        \n\tName: {self.name}\
        '''

    @property
    def formatted_name(self):
        """ Functions as the suburl when making requests """
        return self.name.lower().replace(' ', '-')

    @property
    def suburl(self):
        return f'studio/{self.formatted_name}/'

    @property
    def num_pages(self):
        """ Return the number of pages in the soup 
        (i.e. how many pages of films are there for this studio?).
        r-type: int """

        try:
            pagination = self.soup.find_all('li', class_='paginate-page')[-1]
        except IndexError:
            return 1
        else:
            return int(pagination.find('a').text)

    @staticmethod
    def page_of_entries(soup):
        div_list = soup.find('ul', class_='poster-list').find_all('div')
        return [int(i.get('data-film-id')) for i in div_list]

    @property
    def entries(self):
        """ Return list of ALL entries for the studio
        r-type: list
        """

        entries = []
        page = 1
        soup = self.soup

        while True:
            entries += self.page_of_entries(soup)
            
            if page == self.num_pages: 
                return entries
            else:
                page += 1
                soup = make_soup(SESSION.request('GET', f'{self.suburl}/page/{page}'))


class Individual():
    """
    Info about individuals listed on Letterboxd (e.g. Eric Roberts)
    """

    all_roles = ['producer', 'director', 'actor', 'writer', 'editor', 'composer', 'cinematography']

    def __init__(self, name, roles=[]):
        """
        Params:
        - Roles (list):
            producer / director / actor / writer / editor / composer / cinematography
            E.g. if ['producer', 'writer'] -> get_entries() will return these by default
        """
        self.name = name

        if not roles: 
            roles = self.all_roles
        else:
            if any(invalid_roles:= [i not in self.all_roles for i in roles]): raise ValueError(f"invalid roles: {invalid_roles}")
        
        ## NOTE: I'm not using a property for entries in this class because self.roles is already a property
        final_roles = {role: self.__get_entries_for_role(role) for role in roles}
        self.entries = final_roles

    def __repr__(self):
        cls_name = self.__class__.__name__
        return f'{cls_name} ({self})'

    def __str__(self):
        return f'''\
        == Studio ==\
        \n\tName: {self.name}\
        \n\tRoles: {self.roles}\
        '''
        
    @property
    def last_name(self):
        return self.name.split(' ')[-1]

    @property
    def merged_entries(self):
        """ Returns a list of entries regardless of role
        r-type: list """
        return util.lists_merge([i for i in self.entries.values()])

    @property
    def roles(self):
        """ Why is this not set during __init__?
        Well, some individuals only have one role 
            (e.g. Tara Lynne Barr is only an actress, not a director, producer, etc.)
        This list of roles = set(roles) - set(roles_for_which_there_are_no_entries)
        """
        return list(self.entries.keys())

    @property
    def formatted_name(self):
        """ Functions as the suburl when making requests 
        r-type: str
        """
        return self.name.lower().replace(' ', '-')
    
    def __get_entries_for_role(self, role):
        response = SESSION.request('GET', f'{role}/{self.formatted_name}/')
        soup = make_soup(response)

        poster_list = soup.find('ul', class_='poster-list')

        if not poster_list:
            # There are no entries for the page
            entries = []
        else:
            div_list = poster_list.find_all('div')
            entries = [int(i.get('data-film-id')) for i in div_list]

        return entries
        

class LetterboxdList():
    """ For working with lists in Letterboxd
    For lists owned by the you, use instead MyList subclass instead, for modify/delete etc."""

    def __init__(self, name, username, filters=[]):
        """
        Parameters:
            - name (str) - the name of the list
            - username (str)
            - filters (list) - list of filters (e.g. 'show-liked')
        """

        ## Edge cases
        if not name or not isinstance(name, str):
            raise TypeError(f"name must be valid non-empty str, not {name}")
        if username == SESSION.username and self.__class__.__name__ == "LetterboxdList":
            raise Exception("You should use MyList for your own lists!")

        ## User defined name
        # This is original name passed to the instance, as opposed to the one grabbed from the property
        self.user_defined_name = name
        self.username = username
        self.filters = SESSION.get_valid_filters(filters)

        self.load()
        
    def __repr__(self):
        cls_name = self.__class__.__name__
        return f'{cls_name} ({self})'

    def __str__(self):
        return f'''\
        == LetterboxdList ==\
        \n\tName: {self.name}\
        \n\tUsername: {self.username}\
        \n\tFilters: {self.filters}\
        \n\tNumber of Films: {len(self.entries)}\
        '''

    def __len__(self):
        """ Returns the number of entries in the list. """
        if not self.entries:
            return 0
        return len(self.entries)

    @property 
    def formatted_name(self):
        """
        Produces a formatted_name based on self.name
        The formatted_name is the expected URL for the list.
        r-type: str
        """
        return util.format_name(self.user_defined_name)

    def load(self):
        """ load an instance for an existing list, given its name. """
        ## Cookies
        requests_jar = requests.cookies.RequestsCookieJar()
        requests_jar.set('filmFilter', self.filters)

        ## Set self.soup to soup of view_url of list
        self.soup = make_soup(SESSION.request("GET", self.view_url, cookies=requests_jar))

    def get_id_name_link_dict(self, page=None):
        """ 
        Returns each id in the film list together with the corresponding film_name and link
        Retains list order

        Example: {534194: {'name': '#FollowMe', 'link': '/film/followme-2019/'}, 65519: {'name': '11/11/11', 'link': '/film/11-11-11-2011/'}
        r-type: dict nested
        """
        
        def get_page_of_film_names(page_num):
            """ Returns a dictionary 
                key: film_id
                value: film_name
            for all the films on that page of the list. 
                
            Example: {534194: {'name': '#FollowMe', 'link': '/film/followme-2019/'}, 65519: {'name': '11/11/11', 'link': '/film/11-11-11-2011/'}
            r-type: dict nested
            """
            response = SESSION.request("GET", f"{self.view_url}page/{page_num}/")
            soup = make_soup(response)

            ul = soup.find('ul', class_='film-list')

            extract_link = lambda x: re.findall(r"\/film\/(.*)/$", x)[0]

            page_results = {
                int(li.find('div').get('data-film-id')): 
                    {'name': li.find('img').get('alt'), 'link': extract_link(li.find('div').get('data-target-link'))} 
                    for li in ul.find_all('li')
                } 
            return page_results

        response = SESSION.request("GET", self.view_url)
        soup = make_soup(response)

        if page:
            return get_page_of_film_names(page)

        if not ( page_navigator := soup.find('div', class_='pagination') ):
            last_page = 1
        else:
            last_page = int(page_navigator.find_all('li', class_='paginate-page')[-1].find('a').text)

        current_page = 1
        results = {}
        while current_page <= last_page:
            page_results = get_page_of_film_names(current_page)
            if not page_results:
                break
            results.update(page_results)
            current_page += 1

        return results

    """
    ** Misc. **
    """

    @staticmethod
    def remove_notes(entries):
        """ Removes notes from a given list of entries. """
        return [{k:v for k,v in i.items() if k=="filmId"} for i in entries]

    @property
    def view_url(self):
        return f"{self.username}/list/{self.formatted_name}/"

    @property
    def url(self):
        return f"{SESSION.MAIN_URL}{self.view_url}"

    @property
    def data(self):
        """ Creates a dictionary of list attributes using the instance's properties
        grabbed from the soup. """
        try:
            data_dict = {
                'list_id': self._id,
                'name': self.name,
                'tags': self.tags,
                'ranked': self.ranked,
                'description': self.description,
                'entries': self.entries
            }
        except Exception as e:
            raise Exception(f"Could not get data\n{e}")
        else:
            return data_dict

    @property
    def psuedo_username(self):
        return get_psuedo_username(self.username)

    """
    ** List Attributes **
    """

    @property
    def _id(self):
        """ Returns the list_id
        NOTE: the list_id cannot be set; it is assigned upon creation of the list. 
        r-type: int
        """
        list_id_string = self.soup.select_one("div[id*=report]").get('id') # *= means: contains
        pattern = r"-(\d+)$"
        try:
            match = int(re.findall(pattern, list_id_string)[0])
        except IndexError:
            raise Exception("Could not get id")
        else:
            return match

    @property
    def name(self):
        """ Returns the name of the list.
        This should correspond exactly with the name you used when creating the list. 
        r-type: str
        """
        return self.soup.find('meta', attrs={'property': 'og:title'}).get('content')

    @property
    def tags(self):
        """ Returns the list of tags the list has.
        If the list has no tags, returns the empty list.
        r-type: list. """
        if not (tags_ul := self.soup.find('ul', class_='tags')):
            # The tags list could not be found - there are no tags
            return []
        tags_list = tags_ul.find_all('li')
        return [i.text.strip() for i in tags_list]

    @property
    def ranked(self):
        """ Returns a bool value based on if the list is ranked.
        r-type: bool """
        if not self.entries:
            return False
        entries_list = self.soup.find('ul', class_='poster-list')
        numbered_entry = entries_list.find('li', class_='numbered-list-item')
        return bool(numbered_entry)

    @property
    def description(self):
        """ Returns the list's description; keeps all whitespacing.
        r-type: str. """
        full_description = self.soup.find('meta', attrs={'name': 'description'}).get('content')

        """ For public lists the description in HTML starts with the following:
        "A list of <15> films compiled on Letterboxd, including (up to 5 films). About this list:"
        So we'll remove it """
        try:
            return full_description.split('About this list: ')[1]
        except IndexError:
            return full_description

    @property
    def num_entries(self):
        """ Returns the number of entires in the list. """
        progress_panel = self.soup.find_all('section', class_='progress-panel')[0]
        return int(progress_panel.get('data-total', 0))

    @property
    def entries(self):
        """ Returns the list's entries
        NOTE: this also includes any notes that have been added for each film. 
        r-type: list
        Example:
        [290472, 531904] """

        def get_entries_from_page(soup):
            entry_list_items = soup.find('ul', class_='poster-list').find_all('div')
            # Convert list to entries dict
            return [int(i.get('data-film-id')) for i in entry_list_items]

        if self.num_entries <= 100:
            return get_entries_from_page(self.soup)

        i = 1
        entries = []
        while len(entries) < self.num_entries:
            request = SESSION.request('GET', f"{self.view_url}/page/{i}/")
            soup = make_soup(request)
            entries_on_page = get_entries_from_page(soup)
            entries.extend(entries_on_page)
            i += 1
        
        return entries        

    @property
    def entries_links(self):
        entry_list_items = self.soup.find('ul', class_='poster-list').find_all('div')

        # Convert list to entries dict
        links_filmname_only = lambda x: re.findall(r'/film/([a-z0-9-]+)/', x)
        return [{"filmId": int(i.get('data-film-id')), "link": links_filmname_only(i.get('data-target-link'))} for i in entry_list_items]


class MyList(LetterboxdList):
    """ Subclass for Letterboxd Lists owned by the user.

    # Create 
        To Create a new list:
            use the new_list() constructor 
    Otherwise, MyList expects list_name to already exist
    # Delete 
    # Edit 
        # Set individual attribute (e.g. description) 
        # Change multiple attributes (e.g. description, tags) #TODO test
        # Append entries (add entries) 
        # Remove (subtract entries) 
        # Replace (replace entries)
        # Clear entries
    # Comment
        # Add TODO
        # Delete TODO
    """

    ## This url is used when making the request to make changes to a list
    save_url = 's/save-list'

    def __init__(self, name, separator=f"{'='*15}"):
        """ Initialise using the parent __init__ method,
        but pass the username as the session's username. """
        super().__init__(name, username=SESSION.username)
        self.separator = separator
        self.remove_duplicates()

    def __repr__(self):
        cls_name = self.__class__.__name__
        return f'{cls_name} ({self})'

    def __str__(self):
        return f'''\
        == MyList ==\
        \n\tName: {self.name}\
        \n\tNumber of Films: {len(self.entries)}\
        '''

    @property
    def edit_url(self):
        return f"{SESSION.username}/list/{self.formatted_name}/edit"

    def load(self):
        self.soup = make_soup(SESSION.request('GET', self.edit_url))

    def remove_duplicates(self):
        """ Occasionally duplicates will randomly appear in list. So remove upon __init__"""
        entries = self.entries
        if len(entries) == len(n:= set(entries)):
            # No duplicates to remove
            return
        replacement_entries = format_entries(n)
        self.replace(replacement_entries)        

    def delete(self):
        """ XXX Deletes XXX the list from Letterboxd. This cannot be undone!
        NOTE: after deleting a list, the instance will become unusable.   
        """
        if not util.yn("Are you sure you want to delete the list? This cannot be undone!"):
            return
        SESSION.request("POST", self.suburl_delete)
        self.soup = None

    """
    ** Alternative Constructors **
    """
    @classmethod
    def new(cls, name, **kwargs):
        """
        :: Alternative Constructor ::
        Creates a new list, as opposed to initialising this class
        regularly, which expects the name passed to already exist as a list on Letterboxd.
        This method makes a request first to create the list
        It then returns an instance in the regular way by calling the __init__ method(),
        which anticipates an existing list. Since we have already created the list, this is fine.
        Parameters:
            - name (str) - the name of the list 
        
        Optional Parameters
            - tags (list) - e.g. [horror, 1980s]
            - public (bool)
            - ranked (bool)
            - description (str) - e.g. "These are my favourite films"
            - entries (list of dicts) - films in the list and any notes about them
        """ 

        # Default values for the list which will be used
        # in the event that the corresponding keyword arguments are not provided
        default_values = {
            'tags': [],
            'public': False,
            'ranked': False,
            'description': '',
            'entries': []
        }

        ## Add default values for any missing keys
        list_data = {attribute: value if attribute not in kwargs else kwargs[attribute] 
            for attribute, value in default_values.items()}

        ## Add list_name and empty_id
        # (the id_ will be generated automatically when making the list creation request)
        list_data['name'] = name
        list_data['list_id'] = ''

        ## Convert the list_data into values which can be passed to a request
        # This involves changing the types of some of the values
        post_data = cls.make_post_data(list_data)

        # Create list
        SESSION.request('POST', suburl=cls.save_url, data=post_data)
        
        # Since list is created, can now create MyList as normal
        return cls(name)

    """
    ** List Attributes **
    """
    @property
    def public(self):
        """ Returns a bool value based on if the list is public.
        r-type: bool """
        return bool(self.soup.find('input', attrs={'id': 'list-is-public', 'checked':True}))

    """ 
    ** List Attributes (overloaded) **
    
    These properties have to be overloaded because, in MyList, we're working with
    a different soup.
    
    Whereas LetterboxdList makes use of the list view, 
    MyList makes use of the edit list view. 
    
    Initially I considered the edit-list view to be superior.
    The information is more easily grabbed. However, it is possible to grab every necessesary attribute
    using the view-list soup alone (with the exception of the public status of the list)
    """ 

    @property
    def _id(self):
        return int(self.soup.find('input', attrs={'name': 'filmListId'}).get('value'))

    @property
    def name(self):
        return self.soup.find('input', attrs={'name': 'name'}).get('value')

    @property
    def tags(self):
        return [i.get('value') for i in self.soup.find_all('input', attrs={'name': 'tag'})]

    @property
    def ranked(self):
        return bool(self.soup.find('input', attrs={'id': 'show-item-numbers', 'checked':True}))

    @property
    def description(self):
        description = self.soup.find('textarea', attrs={'name': 'notes'}).text
        return '' if not description else description
       
    @property
    def entries_notes(self):
        def get_film_data(soup_part):
            """ Returns the data for an individual film in the entries.
            This consists the film_id
            And, if one exists, the review (notes), and if the review (notes) contain spoilers
            
            r-type: dict
            """
            film_id = int(soup_part.get('data-film-id')) 
            # BUG with update ~2022/10/19, letterboxd changed their film-ids from numbers to letterboxd combinations
            # This breaks this code and the entire program due my frequently converting back and forth to ints and strings

            notes = soup_part.find('input', attrs={'name': 'review', 'value': True}).get('value')
            if not notes:
                return {'filmId': film_id}
            contains_spoilers = bool(soup_part.find('input', attrs={'name': 'containsSpoilers', 'value': 'true'}))
            return {'filmId': film_id, 'review': notes, 'containsSpoilers': contains_spoilers}

        list_items = self.soup.find_all('li', class_='film-list-entry')
        entries = [get_film_data(film) for film in list_items]
        return entries

    @property
    def entries(self):
        return [i['filmId'] for i in self.entries_notes]

    @property
    def entries_links(self):
        """ Returns a dict of filmIds and their links"""

        ## Have to make another request, this time to the VIEW_url, rather than EDIT_url
        ## In order to get link information
        response = SESSION.request("GET", self.view_url)
        soup = make_soup(response)
        entry_list_items = soup.find('ul', class_='poster-list').find_all('div')

        if soup.find('a', class_='next'):
            page_num = 2

            while True:

                print("Scanning page", page_num)
                
                response = SESSION.request("GET", f"{self.view_url}page/{page_num}/")
                soup = make_soup(response)
                entry_list_items += soup.find('ul', class_='poster-list').find_all('div')

                if not soup.find('a', class_='next'):
                    break
                page_num += 1

        # Convert list to entries dict
        links_filmname_only = lambda x: re.findall(r'/film/([a-z0-9-]+)/', x)
        return [{"filmId": int(i.get('data-film-id')), "link": links_filmname_only(i.get('data-target-link'))} for i in entry_list_items]


    """
    ** List Manipulation and Setters
    """

    def update(self, show_changes=False, **kwargs):
        """ Modify one or more attributes of the list, including entries.
        It is also called by methods which deal strictly with modifying entries,
        namely replace, add and subtract. """

        ## Check for invalid keys
        if any(unknown_keys := [k for k in kwargs if k not in self.data.keys()]): 
            raise KeyError(f"Unknown keys: {unknown_keys}")

        ## Create dictionary of updated attributes
        new_attrs = {k:v if k not in kwargs else kwargs[k] for k,v in self.data.items()}

        if show_changes and 'entries' in new_attrs.keys():
            new_description = self.__show_changes(new_attrs['entries'])
            if new_description: 
                new_attrs['description'] = new_description

        post_data = self.make_post_data(new_attrs)

        ## Update list
        SESSION.request('POST', suburl=self.save_url, data=post_data)

        ## Update user-defined name to allow loading to work if list has been renamed
        if (new_list_name := new_attrs.get('name')): self.user_defined_name = new_list_name

        ## Update soup
        self.load()

    def clear(self):
        """ 
        A -> []
        Clears all entries in a list. """
        self.public = False
        self.update(entries=[])

    def replace(self, *args, show_changes=False):
        """ 
        A, B -> B        
        Replace any existing entries with the passed list(s) of entries. """
        merged_entries = self.__merge_entries(*args)
        if not merged_entries: 
            return False
        
        if not isinstance(merged_entries[0], dict):
            # Then assume to be in format [14515, 15643, ...]
            # So change to [{'filmId': 14515}, {'filmId': 15643}, ...]
            merged_entries = format_entries(merged_entries)

        self.update(entries=merged_entries, show_changes=show_changes)

    def append(self, *args, show_changes=False):
        """ 
        A, B -> A + B
        Add to any existing entries with the passed list(s) of entries. """
        # Merge entires passed to method
        merged_entries = self.__merge_entries(*args)
        # Get current entries prior to changes 
        entries_notes = self.entries_notes
        # Add new entries to current
        [entries_notes.append({'filmId': i}) for i in merged_entries if i not in self.entries]
        
        # Finally, update
        self.update(entries=entries_notes, show_changes=show_changes)

    def remove(self, *args, show_changes=False):
        """
        A, B -> A - B
        Subtract passed list(s) of entries from any entries which exist in the list currently. """
        # Merge entires passed to method
        merged_entries = self.__merge_entries(*args)
        # Subtract said passed entries from current ones 
        remaining_entries = [i for i in self.entries_notes if i['filmId'] not in merged_entries]
        self.update(entries=remaining_entries, show_changes=show_changes)

    @name.setter
    def name(self, name):
        assert isinstance(name, str)
        self.update(name=name)

    @tags.setter
    def tags(self, tags):
        assert isinstance(tags, list)
        self.update(tags=tags)

    @public.setter
    def public(self, value):

        if not self.entries:
            print("Cannot make empty list public")
            return False

        assert isinstance(value, bool)
        if value is self.public: 
            print(f"List was already {self.public}")
            return
        self.update(public=value)

    @ranked.setter
    def ranked(self, value):
        assert isinstance(value, bool)
        if value is self.ranked: 
            print(f"List was already {self.public}")
            return
        self.update(ranked=value)

    @description.setter
    def description(self, text):
        assert isinstance(text, str)
        self.update(description=text)
    
    """
    ** List Manipulation and Setters - utility **
    """

    @staticmethod
    def __merge_entries(*entries_lists):
        """ . """
        if not all( [isinstance(i, list) for i in entries_lists] ):
            raise TypeError(f"All arguments must be lists, not {entries_lists}")
        results = util.lists_merge(entries_lists)
        unique_results = []
        for i in results:
            if i in unique_results:
                continue
            unique_results.append(i)
        return unique_results
        

    def __show_changes(self, new_entries):
        
        ## Get sets of new entries, and old (prior to changes)
        extract_ids = lambda entries: set([e['filmId'] for e in entries]) if entries else set()
        new = extract_ids(new_entries)
        old = set(self.entries)

        if set(new) == set(old):
            print("No changes")
            return
        
        # Get the ids of films to be added/removed
        added_ids = new - old
        removed_ids = old - new

        removed_films = [] if not removed_ids else get_id_name_link_dict(removed_ids)
        added_films = [] if not added_ids else get_id_name_link_dict(added_ids)

        bolden = util.HTML_Adder.bolden

        newly_added = ''
        if added_ids:
            newly_added += f"{bolden('Last Added')}:"
            newly_added += ''.join([f"\n<a href=\"{SESSION.MAIN_URL}/film/{i['link']}/\">{i['name']}</a>" for i in util.limit_list(list(added_films.values()),25)])
            newly_added += "\n\n"

        if removed_ids:
            newly_added += f"{bolden('Last Removed')}:"
            newly_added += ''.join([f"\n<a href=\"{SESSION.MAIN_URL}/film/{i['link']}/\">{i['name']}</a>" for i in util.limit_list(list(removed_films.values()), 25)])

        newly_added = newly_added.strip()

        if not newly_added:
            raise Exception("Could not get newly added!")
        else:    
            before = self.description.split(self.separator)[0].rstrip() + "\n\n"
            new_description = before + self.separator + "\n\n" + newly_added
            return new_description
        
    """
    ** Misc **
    """
    
    @property
    def data(self):
        """ Creates a dictionary of list attributes using the instance's properties
        grabbed from the soup. """
        try:
            data_dict = {
                'list_id': self._id,
                'name': self.name,
                'tags': self.tags,
                'public': self.public,
                'ranked': self.ranked,
                'description': self.description,
                'entries': self.entries_notes
            }
        except Exception as e:
            raise Exception(f"Could not get data\n{e}")
        else:
            return data_dict

    @staticmethod
    def make_post_data(data):
        """ Converts data to a dictionary that can be passed directly
        a save-list request.
        Parameters:
        - data (dict)
        
        r-type: dict
        """
        bool_to_str = lambda x: str(x).lower()

        # Try to ensure that filmIds are in {'filmId': x} format
        if (entries := data.get('entries')):
            assert isinstance(entries, list)
            if isinstance(entries[0], int):
                data['entries'] = [{'filmId': x} for x in entries]
            
        return {
            'filmListId': str(data['list_id']),
            'name': data['name'],
            'tags': '',
            'tag': data['tags'],
            'publicList': bool_to_str(data['public']),
            'numberedList': bool_to_str(data['ranked']),
            'notes': data['description'],
            'entries': str(data['entries'])
        }

    """
    ** Comment Manipulation **
    """
    @property
    def add_comment_url(self):
        """ Returns the suburl for adding a comment to a list. """
        return f's/filmlist:{self._id}/add-comment'
    
    @property
    def comment_soup(self):
        """ Returns the soup containing information about the list's existing comments."""
        response = SESSION.request(
            "GET", f"csi/list/{self._id}/comments-section/?", 
            params={'esiAllowUser': True}
            )
        soup = make_soup(response)
        return soup

    @property
    def comments(self):
        """ Returns a dictionary of comments on the list. 
        Example: [{'username': 'LostInStyle', 'comment': 'Hello World', 'date_created':2020-11-15}]
        """
        body = self.comment_soup.find('div', class_='body')
        valid_comments = [i for i in body.find_all('li', attrs={'data-person': True})]
        
        if not valid_comments:
            return None

        def get_comment_text(suburl):
            """ Returns the body of the comment. """
            response = SESSION.request("GET", suburl)
            return make_soup(response).get_text()

        def convert_timestamp(timestamp):
            """ Convert the timestamp 'data-creation-timestamp' into a valid pendulum timestamp. """
            return pendulum.from_timestamp(timestamp)

        comments = [
            {
            'id': int(i['id'].split('-')[1]),
            'username': i['data-person'],
            'date_created': convert_timestamp( int(i['data-creation-timestamp'][:-3]) ),
            'comment': get_comment_text(i.find('div', class_='comment-body').get('data-full-text-url')),
            }
            for i in valid_comments]
        return comments

    @property
    def num_comments(self):
        """ Returns the number of comments a list has received, not included any that have been removed. """
        if not self.comments:
            return 0
        data_comments_link = f"/{self.username.lower()}/list/{self.get_formatted_name()}/#comments"
        num_comments_text = self.comment_soup.find('h2', attrs={'data-comments-link': data_comments_link}).text.strip()
        pattern = r"^\d+"
        try:
            match = re.findall(pattern, num_comments_text)[0]
        except IndexError:
            return 0
        else:
            return int(match)

    def add_comment(self, comment):
        """ Adds a comment to the list. """
        SESSION.request("POST", self.add_comment_url, data={'comment': comment})

    def delete_comment(self, comment_id):
        """ Deletes a comment on a list, given that comment's id. """
        # Edge cases
        if not (comments := self.comments):
            raise Exception("No comments to delete!")
        if type(comment_id) not in (str, int):
            raise TypeError(f"Invalid type for comment_id: {type(comment_id)}. Should be int")
        if isinstance(comment_id, str):
            comment_id = int(comment_id)

        if comment_id not in [i['id'] for i in comments]:
            raise Exception(f"Unable to locate id: {comment_id}")

        delete_comment_url = f"ajax/filmListComment:{comment_id}/delete-comment/"

        # Make post request to delete comment
        SESSION.request("POST", suburl=delete_comment_url)



def get_id_name_link_dict(film_ids):
    """ Creates or edits a list used by the program which 
    is then used by this function to determine the names which
    correspond to the given ids. """

    ## Try to ensure correct format of data
    # If not list of dicts, change list into dicts
    if not all([type(x) is dict for x in film_ids]):
        if not all(type(x) is int for x in film_ids):
            raise TypeError(f"Invalid input: {film_ids}. Expected list of dicts or list.")

        # If list of ints, convert to entries format (list of dicts)
        film_ids = [{'filmId': film_id} for film_id in film_ids]
    
    temp_list = MyList(name="test003")
    temp_list.update(entries=film_ids)

    film_name_links = temp_list.get_id_name_link_dict()
    
    ## Change temp_list back to being empty
    temp_list.clear()

    return film_name_links   


class MyMasterList(MyList):
    """ A master list works as follows:
    Every time it runs, it imports all entries (films) from the sources you give it.
    These sources can be other lists, individuals (e.g. directors), studios, and films rated by a given user.
    You can also pass an exclude list. This is just a stanard letterboxd list - any films in here will not be added to the main list.
    """
    
    def __init__(self, name, child_lists=[], individuals=[], studios=[], users=[], exclude=None, separator=f"{'='*15}"):
        """
        Parameters:
        - child_lists (type: LetterboxdList)
        - individuals (type: Individual)
        - studios (type: Studio)
        - users (type: #TODO)
        - include (type: LetterboxdList) - these entries will always be included even if 
        - exclude (type: LetterboxdList)
        """

        super().__init__(name, separator)
        
        ## Set vars
        self.child_lists = sorted(child_lists, key=lambda cl: cl.name) # sort child lists alphabetically
        self.individuals = sorted(individuals, key=lambda i: i.last_name) # sort by individual's last name
        self.studios = sorted(studios, key=lambda s: s.name) # sort studios alphabetically
        self.users = sorted(users, key=lambda u: u[0]) # sort by username
        
        self.exclude_list = [] if not exclude else exclude.entries

        get_entries = lambda x: [] if not x else util.lists_merge([y.entries for y in x])
        ## Get entries
        # entries_child_lists = [] if not child_lists else util.lists_merge([cl.entries for cl in child_lists])
        # entries_individuals = [] if not individuals else util.lists_merge([i.entries for i in individuals])
        e_cl = get_entries(child_lists) 
        e_i = [] if not individuals else util.lists_merge([i.merged_entries for i in individuals])
        e_s = get_entries(studios)
        e_u = [] if not users else util.lists_merge(u[-1] for u in users)

        pre_format = set([i for i in util.lists_merge([e_cl, e_i, e_s, e_u]) if i not in self.exclude_list])
        pre_format = sorted(pre_format, reverse=True)

        self.final_entries = format_entries(list(pre_format))
        
        # import json
        # with open("../data/test.json", "w") as jf:
        #     json.dump(self.final_entries, jf)


    @property
    def absent_from_sources(self):
        return set(self.entries).difference(set(self.entries_sources)) 

    def master_update(self):

        if self.separator not in (d := self.description):
            before = d + "\n\n" + self.separator + "\n\n" 
        else:
            before = self.description.split(self.separator)[0].rstrip() + "\n\n" + self.separator + "\n\n"
        
        after = ''

        if self.child_lists:
            after += f"{util.HTML_Adder.bolden('-- Lists --')}"
            after += ''.join([f'\n{i+1}. {util.HTML_Adder.link(SESSION.MAIN_URL + j.view_url, j.name)} ( by {j.psuedo_username} )' for i, j in enumerate(self.child_lists)])
            after += "\n\n"

        if self.individuals:
            after += f"{util.HTML_Adder.bolden('-- Individuals --')}"
            individual_suburl = lambda i: f"{i.roles[0]}/{i.formatted_name}/"
            after += ''.join([f'\n{i+1}. {util.HTML_Adder.link(SESSION.MAIN_URL + individual_suburl(j), j.name)}' for i, j in enumerate(self.individuals)])
            # after += ''.join([f'\n{i+1}. {util.HTML_Adder.link(SESSION.MAIN_URL + individual_suburl(j), j.name)} ( as {", ".join(j.roles)})' for i, j in enumerate(self.individuals)])
            after += "\n\n"

        if self.studios:
            after += f"{util.HTML_Adder.bolden('-- Studios --')}"
            after += ''.join([f'\n{i+1}. {util.HTML_Adder.link(SESSION.MAIN_URL + j.suburl, j.name)}' for i, j in enumerate(self.studios)])
            after += "\n\n"

        if self.users:
            after += f"{util.HTML_Adder.bolden('-- Users --')}"
            after += ''.join([f'\n{i+1}. {util.HTML_Adder.link(SESSION.MAIN_URL + j[1], j[0])}' for i, j in enumerate(self.users)])
            after += "\n\n"

        description = before + after
        self.update(show_changes=False, description=description, entries=self.final_entries)


if __name__ == '__main__':

    x = MyList("Animation 1960")

    # x = FilmInfo('titanic-666')
    # print(x.letterboxd_rating)
    # print(x.true_avg_rating)

    # ml = MyList('posters')
    # print(len(ml.entries))

    # pass 
    # l = LetterboxdList('nightmare-list', 'kaseyclouds')


    










    

        


