#!/usr/bin/env python3

"""This module contains the DanskGruppenArchive class which is used access
Dansk-gruppens email archive on gmane
"""

from collections import OrderedDict
# pylint: disable=no-name-in-module
from nntplib import decode_header, NNTP
import email
import pickle
from os import path
import logging
logging.basicConfig(name='archive', level=logging.DEBUG)


class DanskGruppenArchive(object):
    """Class that provides an interface to Dansk-gruppens emails archive on
    gmane
    """

    def __init__(self, article_cache_size=300, cache_file=None):
        """Initialize local variables"""
        # Connect to news.gmane.org
        self.nntp = NNTP('news.gmane.org')
        # Setting the group returns information, which right now we ignore
        self.nntp.group('gmane.comp.internationalization.dansk')

        # Keep a local cache in an OrderedDict, transferred across session
        # in a pickled version in a file
        self.article_cache_size = article_cache_size
        self.cache_file = cache_file
        if cache_file and path.isfile(cache_file):
            with open(cache_file, 'rb') as file_:
                self.article_cache = pickle.load(file_)
            logging.info('Loaded %i items from file cache',
                         len(self.article_cache))
        else:
            self.article_cache = OrderedDict()

    def close(self):
        """Quit the NNTP session and save the cache"""
        self.nntp.quit()
        if self.cache_file:
            with open(self.cache_file, 'wb') as file_:
                pickle.dump(self.article_cache, file_)
                logging.info('Wrote %i items to cache file',
                             len(self.article_cache))

    @property
    def last(self):
        """Return the last NNTP ID as an int"""
        return self.nntp.group('gmane.comp.internationalization.dansk')[3]

    def _get_article(self, message_id):
        """Get an article (cached)

        Args:
            message_id (int): The NNTP ID of the message

        Returns:
            list: List of byte strings in the message
        """
        # Clear excess cache
        if len(self.article_cache) > self.article_cache_size:
            self.article_cache.popitem(last=False)

        # Check if article is in cache and if not, put it there
        if message_id not in self.article_cache:
            # nntp.article() returns: response, information
            # pylint: disable=unbalanced-tuple-unpacking
            _, info = self.nntp.article(message_id)
            self.article_cache[message_id] = info
        return self.article_cache[message_id]

    @staticmethod
    def _article_to_email(article):
        """Convert a raw article to an email object

        Args:
            article (namedtuple): An article named tuple as returned by NNTP

        Returns:
            email.message: An email message object
        """
        # article lines are a list of byte strings
        decoded_lines = [line.decode('ascii') for line in article.lines]
        article_string = '\n'.join(decoded_lines)
        # Make an email object
        return email.message_from_string(article_string)

    def get_subject(self, message_id):
        """Get the subject of an message

        Args:
            message_id (int): The NNTP ID of the the message

        Returns:
            str: The subject of the article
        """
        article = self._get_article(message_id)
        mail = self._article_to_email(article)
        # The subject may be encoded by NNTP, so decode it
        return decode_header(mail['Subject'])

    def get_body(self, message_id):
        """Get the body of a message

        Args:
            message_id (int): The NNTP ID of the the message

        Returns:
            str: The body of the article as a str or None if no body could be
                found or succesfully decoded
        """
        article = self._get_article(message_id)
        mail = self._article_to_email(article)

        # Walk parts of the email and look for text/plain content type
        for part in mail.walk():
            if part.get_content_type() == 'text/plain':
                body = part.get_payload(decode=True)
                # Find the text encoding from lines like:
                # text/plain; charset=UTF-8
                # text/plain; charset=utf-8; format=flowed
                # Encoding sometimes has "" around it, decode is OK with that
                for type_part in part['Content-Type'].split(';'):
                    if type_part.strip().startswith('charset='):
                        encoding = type_part.replace('charset=', '')
                        break
                else:
                    message = 'Looking for the character encoding in the '\
                        'string "%s" went wrong'
                    logging.warning(message, part['Content-Type'])
                    return None

                # Decode and return the body
                try:
                    body = body.decode(encoding)
                except LookupError:
                    message = 'Do not know how to handle a body with '\
                        'charset: %s'
                    logging.warning(message, encoding)
                    return None

                return body


if __name__ == '__main__':
    DGA = DanskGruppenArchive(cache_file='dga_cache')
    LAST = DGA.last
    DGA.get_body(33253)
    for n in range(LAST-100, LAST):
        BODY = DGA.get_body(n)

    DGA.close()
