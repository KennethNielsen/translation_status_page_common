#!/usr/bin/env python3

from collections import OrderedDict
import quopri
from nntplib import decode_header, NNTP
from datetime import date
from email import message_from_string
import pickle
from os import path
import logging
logging.basicConfig(name='archive', level=logging.DEBUG)


class DanskGruppenArchive(object):

    def __init__(self, article_cache_size=300, cache_file=None):
        self.nntp = NNTP('news.gmane.org')
        # Setting the group returns information, which right now we ignore
        self.nntp.group('gmane.comp.internationalization.dansk')
        # Keep a local cache
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
        """Return the last ID"""
        return self.nntp.group('gmane.comp.internationalization.dansk')[3]

    def _get_article(self, message_spec):
        """Get an article (cached)"""
        # Clear excess cache
        if len(self.article_cache) > self.article_cache_size:
            self.article_cache.popitem(last=False)

        # Check if article is in cache and if not, put it there
        if message_spec not in self.article_cache:
            # nntp.article() returns: response, information
            g, info = self.nntp.article(message_spec)
            self.article_cache[message_spec] = info
        return self.article_cache[message_spec]

    def get_subject(self, message_spec):
        """Get the subject of an message"""
        article = self._get_article(message_spec)
        # article lines are a list of byte strings
        decoded_lines = [line.decode('ascii') for line in article.lines]
        article_string = '\n'.join(decoded_lines)
        email = message_from_string(article_string)
        return decode_header(email['Subject'])

    def get_body(self, message_spec):
        """Get the body of a message"""
        article = self._get_article(message_spec)
        # article lines are a list of byte strings
        decoded_lines = [line.decode('ascii') for line in article.lines]
        article_string = '\n'.join(decoded_lines)
        email = message_from_string(article_string)

        for part in email.walk():

            if part.get_content_maintype() == 'text':
                body = part.get_payload(decode=True)
                # Find the text encoding
                for type_part in part['Content-Type'].split(';'):
                    if type_part.strip().startswith('charset='):
                        encoding = type_part.replace('charset=', '')
                        break
                else:
                    message = 'Looking for the character encoding in the '\
                      'string "%s" went wrong'
                    logging.warning(message, part['Content-Type'])
                    return None

                try:
                    body = body.decode(encoding)
                except LookupError:
                    message = 'Do not know how to handle a body with '\
                      'charset: %s'
                    logging.warning(message, encoding)
                    return None

                return body


if __name__ == '__main__':
    dga = DanskGruppenArchive(cache_file='dga_cache')
    last = dga.last
    #print(dga.get_body(last - 3))
    for n in range(last-100, last):
        body = dga.get_body(n)

    dga.close()
