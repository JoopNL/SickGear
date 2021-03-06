# coding=utf-8
#
# This file is part of SickGear.
#
# SickGear is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SickGear is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SickGear.  If not, see <http://www.gnu.org/licenses/>.

import re
import traceback

from . import generic
from sickbeard import logger, tvcache
from sickbeard.bs4_parser import BS4Parser
from sickbeard.helpers import tryInt
from lib.unidecode import unidecode


class TorrentBytesProvider(generic.TorrentProvider):

    def __init__(self):
        generic.TorrentProvider.__init__(self, 'TorrentBytes')

        self.url_base = 'https://www.torrentbytes.net/'
        self.urls = {'config_provider_home_uri': self.url_base,
                     'login': self.url_base + 'takelogin.php',
                     'search': self.url_base + 'browse.php?search=%s&%s',
                     'get': self.url_base + '%s'}

        self.categories = {'shows': [41, 33, 38, 32, 37]}

        self.url = self.urls['config_provider_home_uri']

        self.username, self.password, self.minseed, self.minleech = 4 * [None]
        self.freeleech = False
        self.cache = TorrentBytesCache(self)

    def _authorised(self, **kwargs):

        return super(TorrentBytesProvider, self)._authorised(post_params={'login': 'Log in!'})

    def _search_provider(self, search_params, **kwargs):

        results = []
        if not self._authorised():
            return results

        items = {'Cache': [], 'Season': [], 'Episode': [], 'Propers': []}

        rc = dict((k, re.compile('(?i)' + v)) for (k, v) in {'info': 'detail', 'get': 'download', 'fl': '\[\W*F\W?L\W*\]'
                                                             }.items())
        for mode in search_params.keys():
            for search_string in search_params[mode]:
                search_string = isinstance(search_string, unicode) and unidecode(search_string) or search_string
                search_url = self.urls['search'] % (search_string, self._categories_string())

                html = self.get_url(search_url, timeout=90)

                cnt = len(items[mode])
                try:
                    if not html or self._has_no_results(html):
                        raise generic.HaltParseException

                    with BS4Parser(html, features=['html5lib', 'permissive'], attr='border="1"') as soup:
                        torrent_table = soup.find('table', attrs={'border': '1'})
                        torrent_rows = [] if not torrent_table else torrent_table.find_all('tr')

                        if 2 > len(torrent_rows):
                            raise generic.HaltParseException

                        for tr in torrent_rows[1:]:
                            try:
                                info = tr.find('a', href=rc['info'])
                                seeders, leechers, size = [tryInt(n, n) for n in [
                                    tr.find_all('td')[x].get_text().strip() for x in (-2, -1, -4)]]
                                if self.freeleech and (len(info.contents) < 2 or not rc['fl'].search(info.contents[1].string.strip())) \
                                        or self._peers_fail(mode, seeders, leechers):
                                    continue

                                title = 'title' in info.attrs and info.attrs['title'] or info.contents[0]
                                title = (isinstance(title, list) and title[0] or title).strip()
                                download_url = self.urls['get'] % str(tr.find('a', href=rc['get'])['href']).lstrip('/')
                            except (AttributeError, TypeError, ValueError):
                                continue

                            if title and download_url:
                                items[mode].append((title, download_url, seeders, self._bytesizer(size)))

                except generic.HaltParseException:
                    pass
                except Exception:
                    logger.log(u'Failed to parse. Traceback: %s' % traceback.format_exc(), logger.ERROR)

                self._log_search(mode, len(items[mode]) - cnt, search_url)

            self._sort_seeders(mode, items)

            results = list(set(results + items[mode]))

        return results


class TorrentBytesCache(tvcache.TVCache):

    def __init__(self, this_provider):
        tvcache.TVCache.__init__(self, this_provider)

        self.update_freq = 20  # cache update frequency

    def _cache_data(self):

        return self.provider.cache_data()


provider = TorrentBytesProvider()
