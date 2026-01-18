"""
Web Search Service.

Service for performing web searches using SerpAPI.
Supports Google, DuckDuckGo, and Bing search engines.
"""
import logging
from typing import Dict, Any, Optional, List
from serpapi import GoogleSearch

logger = logging.getLogger(__name__)


class WebSearchService:
    """
    Service for web search operations using SerpAPI.

    This service provides methods to search various search engines
    and format results for the monitoring system.
    """

    # Supported search engines
    ENGINE_GOOGLE = 'google'
    ENGINE_DUCKDUCKGO = 'duckduckgo'
    ENGINE_BING = 'bing'

    def __init__(self, api_key_model):
        """
        Initialize web search service with API key.

        Args:
            api_key_model: ApiKey model instance containing the SerpAPI token
        """
        self.api_key_model = api_key_model
        self.api_key = api_key_model.get_api_key()

    def search_google(self, query: str, num_results: int = 10,
                      language: str = 'es', country: str = 'es') -> Dict[str, Any]:
        """
        Perform a Google search.

        Args:
            query: Search query string
            num_results: Maximum number of results to return (default 10)
            language: Language code for results (default 'es' for Spanish)
            country: Country code for localized results (default 'es' for Spain)

        Returns:
            dict: Search results with success status and formatted results
        """
        try:
            params = {
                "engine": "google",
                "q": query,
                "num": num_results,
                "hl": language,
                "gl": country,
                "api_key": self.api_key
            }

            search = GoogleSearch(params)
            results = search.get_dict()

            if 'error' in results:
                logger.error(f"Google search error: {results['error']}")
                return {
                    'success': False,
                    'error': results['error'],
                    'query': query,
                    'engine': self.ENGINE_GOOGLE
                }

            formatted_results = self._format_google_results(results, query)
            return formatted_results

        except Exception as e:
            logger.error(f"Error performing Google search for '{query}': {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'query': query,
                'engine': self.ENGINE_GOOGLE
            }

    def search_duckduckgo(self, query: str, num_results: int = 10,
                          region: str = 'es-es') -> Dict[str, Any]:
        """
        Perform a DuckDuckGo search.

        Args:
            query: Search query string
            num_results: Maximum number of results to return (default 10)
            region: Region code (default 'es-es' for Spain Spanish)

        Returns:
            dict: Search results with success status and formatted results
        """
        try:
            params = {
                "engine": "duckduckgo",
                "q": query,
                "kl": region,
                "api_key": self.api_key
            }

            search = GoogleSearch(params)
            results = search.get_dict()

            if 'error' in results:
                logger.error(f"DuckDuckGo search error: {results['error']}")
                return {
                    'success': False,
                    'error': results['error'],
                    'query': query,
                    'engine': self.ENGINE_DUCKDUCKGO
                }

            formatted_results = self._format_duckduckgo_results(results, query)
            return formatted_results

        except Exception as e:
            logger.error(f"Error performing DuckDuckGo search for '{query}': {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'query': query,
                'engine': self.ENGINE_DUCKDUCKGO
            }

    def search_bing(self, query: str, num_results: int = 10,
                    market: str = 'es-ES') -> Dict[str, Any]:
        """
        Perform a Bing search.

        Args:
            query: Search query string
            num_results: Maximum number of results to return (default 10)
            market: Market code (default 'es-ES' for Spain)

        Returns:
            dict: Search results with success status and formatted results
        """
        try:
            params = {
                "engine": "bing",
                "q": query,
                "count": num_results,
                "mkt": market,
                "api_key": self.api_key
            }

            search = GoogleSearch(params)
            results = search.get_dict()

            if 'error' in results:
                logger.error(f"Bing search error: {results['error']}")
                return {
                    'success': False,
                    'error': results['error'],
                    'query': query,
                    'engine': self.ENGINE_BING
                }

            formatted_results = self._format_bing_results(results, query)
            return formatted_results

        except Exception as e:
            logger.error(f"Error performing Bing search for '{query}': {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'query': query,
                'engine': self.ENGINE_BING
            }

    def search(self, query: str, engine: str = 'google',
               num_results: int = 10) -> Dict[str, Any]:
        """
        Perform a search using the specified engine.

        Args:
            query: Search query string
            engine: Search engine to use ('google', 'duckduckgo', 'bing')
            num_results: Maximum number of results to return

        Returns:
            dict: Search results with success status and formatted results
        """
        engine = engine.lower()

        if engine == self.ENGINE_GOOGLE:
            return self.search_google(query, num_results)
        elif engine == self.ENGINE_DUCKDUCKGO:
            return self.search_duckduckgo(query, num_results)
        elif engine == self.ENGINE_BING:
            return self.search_bing(query, num_results)
        else:
            return {
                'success': False,
                'error': f"Motor de búsqueda no soportado: {engine}",
                'query': query,
                'engine': engine
            }

    def _format_google_results(self, raw_results: Dict[str, Any],
                                query: str) -> Dict[str, Any]:
        """
        Format Google search results into a standardized structure.

        Args:
            raw_results: Raw API response from SerpAPI
            query: Original search query

        Returns:
            dict: Formatted results
        """
        formatted = {
            'success': True,
            'query': query,
            'engine': self.ENGINE_GOOGLE,
            'results': [],
            'total_results': raw_results.get('search_information', {}).get('total_results', 0),
            'search_time': raw_results.get('search_information', {}).get('time_taken_displayed', 0)
        }

        organic_results = raw_results.get('organic_results', [])

        for idx, result in enumerate(organic_results, 1):
            formatted['results'].append({
                'position': result.get('position', idx),
                'title': result.get('title', ''),
                'link': result.get('link', ''),
                'displayed_link': result.get('displayed_link', ''),
                'snippet': result.get('snippet', ''),
                'date': result.get('date'),
                'thumbnail': result.get('thumbnail'),
                'source': result.get('source'),
                'cached_page_link': result.get('cached_page_link'),
                'rich_snippet': result.get('rich_snippet')
            })

        # Include news results if present
        news_results = raw_results.get('news_results', [])
        for news in news_results:
            formatted['results'].append({
                'position': len(formatted['results']) + 1,
                'title': news.get('title', ''),
                'link': news.get('link', ''),
                'displayed_link': news.get('source', ''),
                'snippet': news.get('snippet', ''),
                'date': news.get('date'),
                'thumbnail': news.get('thumbnail'),
                'source': news.get('source'),
                'is_news': True
            })

        return formatted

    def _format_duckduckgo_results(self, raw_results: Dict[str, Any],
                                    query: str) -> Dict[str, Any]:
        """
        Format DuckDuckGo search results into a standardized structure.

        Args:
            raw_results: Raw API response from SerpAPI
            query: Original search query

        Returns:
            dict: Formatted results
        """
        formatted = {
            'success': True,
            'query': query,
            'engine': self.ENGINE_DUCKDUCKGO,
            'results': [],
            'total_results': 0
        }

        organic_results = raw_results.get('organic_results', [])
        formatted['total_results'] = len(organic_results)

        for idx, result in enumerate(organic_results, 1):
            formatted['results'].append({
                'position': result.get('position', idx),
                'title': result.get('title', ''),
                'link': result.get('link', ''),
                'displayed_link': result.get('displayed_link', result.get('link', '').split('/')[2] if result.get('link') else ''),
                'snippet': result.get('snippet', ''),
                'date': result.get('date'),
                'favicon': result.get('favicon')
            })

        return formatted

    def _format_bing_results(self, raw_results: Dict[str, Any],
                              query: str) -> Dict[str, Any]:
        """
        Format Bing search results into a standardized structure.

        Args:
            raw_results: Raw API response from SerpAPI
            query: Original search query

        Returns:
            dict: Formatted results
        """
        formatted = {
            'success': True,
            'query': query,
            'engine': self.ENGINE_BING,
            'results': [],
            'total_results': raw_results.get('search_information', {}).get('total_results', 0)
        }

        organic_results = raw_results.get('organic_results', [])

        for idx, result in enumerate(organic_results, 1):
            formatted['results'].append({
                'position': result.get('position', idx),
                'title': result.get('title', ''),
                'link': result.get('link', ''),
                'displayed_link': result.get('displayed_link', ''),
                'snippet': result.get('snippet', ''),
                'date': result.get('date'),
                'thumbnail': result.get('thumbnail'),
                'sitelinks': result.get('sitelinks', [])
            })

        return formatted

    def test_connection(self) -> Dict[str, Any]:
        """
        Test the API connection by performing a simple search.

        Returns:
            dict: Connection test result with success status
        """
        try:
            result = self.search_google("test", num_results=1)
            if result['success']:
                return {
                    'success': True,
                    'message': 'Conexión con SerpAPI exitosa'
                }
            else:
                return {
                    'success': False,
                    'message': f"Error de conexión: {result.get('error', 'Unknown error')}"
                }
        except Exception as e:
            return {
                'success': False,
                'message': f"Error de conexión: {str(e)}"
            }
