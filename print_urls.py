import os
import sys
import django
from django.urls import get_resolver

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'deliv_ST.settings')
django.setup()

def show_urls(urllist, depth=0):
    for entry in urllist:
        if hasattr(entry, 'url_patterns'):
            print("  " * depth + str(entry.pattern))
            show_urls(entry.url_patterns, depth + 1)
        else:
            print("  " * depth + str(entry.pattern) + " - " + entry.callback.__name__)

resolver = get_resolver()
show_urls(resolver.url_patterns)
