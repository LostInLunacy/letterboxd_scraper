""" 
    Custom-made Exceptions for the program. 
"""

class LetterboxdException(Exception):
    """ Exceptions that relate to the site itself.
    e.g. cannot create comment on private list.
    """
    def __init__(self, msg=''):
        super().__init__(msg)

class LoginException(LetterboxdException):
    """ Raises if incorrect credentials given for login. """
    def __init__(self, msg=''):
        super().__init__(msg)