"""
Custom pagination classes for API endpoints.
Optimized for performance and user experience.
"""
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardPageNumberPagination(PageNumberPagination):
    """
    Standard pagination with page size limits.
    Optimized defaults for mobile applications:
    - Default: 20 items per page (good balance for mobile screens)
    - Maximum: 100 items per page (for map views and bulk operations)
    - Allows client to request custom page sizes
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_paginated_response(self, data):
        """
        Return a paginated style Response object with metadata.
        Includes performance hints for clients.
        """
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
            'page_size': self.page_size,
            'current_page': self.page.number,
            'total_pages': self.page.paginator.num_pages,
            # Performance hints
            'has_next': self.page.has_next(),
            'has_previous': self.page.has_previous(),
        })


class LargePageNumberPagination(PageNumberPagination):
    """
    Large page size pagination for map views and bulk operations.
    Use this for endpoints that need to return many items (e.g., map markers).
    """
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200
    
    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
            'page_size': self.page_size,
            'current_page': self.page.number,
            'total_pages': self.page.paginator.num_pages,
            'has_next': self.page.has_next(),
            'has_previous': self.page.has_previous(),
        })

